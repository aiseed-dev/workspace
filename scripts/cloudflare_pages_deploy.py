#!/usr/bin/env python3
"""Cloudflare Pages へ直接アップロードする（wrangler 不要・npm 不要）。

wrangler が内部で使っている Direct Upload API（半公式）を Python で実装したもの。
API が変わって動かなくなったら、wrangler か Git 連携へ退避する（退路）。

使い方:
  export CLOUDFLARE_API_TOKEN=...    # 「Cloudflare Pages: 編集」権限のトークン
  export CLOUDFLARE_ACCOUNT_ID=...   # ダッシュボード右下などに表示される ID
  python3 cloudflare_pages_deploy.py ./公開ディレクトリ --project aiseed-dev
  # 初回はプロジェクトも作る場合: --create

依存: pip install httpx blake3
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path

import httpx
from blake3 import blake3

API = "https://api.cloudflare.com/client/v4"
MAX_FILE_SIZE = 25 * 1024 * 1024  # Pages の 1 ファイル上限（25MiB）
BATCH_BYTES = 30 * 1024 * 1024  # 1 回のアップロード呼び出しの目安


def file_hash(data: bytes, suffix: str) -> str:
    """wrangler と同じ方式：blake3(base64(中身) + 拡張子) の先頭 32 桁。"""
    b64 = base64.b64encode(data).decode()
    return blake3((b64 + suffix).encode()).hexdigest()[:32]


def collect(root: Path) -> dict[str, Path]:
    files = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part.startswith(".") for part in p.parts):
            continue
        if p.stat().st_size > MAX_FILE_SIZE:
            sys.exit(f"エラー: {p} が 25MiB を超えている（Pages の上限）")
        files["/" + p.relative_to(root).as_posix()] = p
    if not files:
        sys.exit(f"エラー: {root} にファイルがない")
    return files


class Pages:
    def __init__(self, account_id: str, token: str):
        self.base = f"{API}/accounts/{account_id}/pages"
        self.client = httpx.Client(
            timeout=120.0, headers={"Authorization": f"Bearer {token}"}
        )

    def _ok(self, resp: httpx.Response) -> dict:
        body = resp.json()
        if not body.get("success"):
            sys.exit(f"API エラー: {resp.request.url}\n{json.dumps(body.get('errors'), ensure_ascii=False)}")
        return body["result"]

    def project_exists(self, project: str) -> bool:
        resp = self.client.get(f"{self.base}/projects/{project}")
        return resp.status_code == 200 and resp.json().get("success", False)

    def create_project(self, project: str) -> None:
        self._ok(self.client.post(
            f"{self.base}/projects",
            json={"name": project, "production_branch": "main"},
        ))
        print(f"プロジェクトを作成: {project}")

    def upload_token(self, project: str) -> str:
        return self._ok(
            self.client.get(f"{self.base}/projects/{project}/upload-token")
        )["jwt"]

    def deploy(self, project: str, manifest: dict[str, str], branch: str) -> dict:
        return self._ok(self.client.post(
            f"{self.base}/projects/{project}/deployments",
            data={"branch": branch},
            files={"manifest": (None, json.dumps(manifest))},
        ))


def upload_assets(token: str, by_hash: dict[str, Path]) -> None:
    client = httpx.Client(
        timeout=300.0, headers={"Authorization": f"Bearer {token}"}
    )

    def ok(resp: httpx.Response):
        body = resp.json()
        if not body.get("success"):
            sys.exit(f"アップロード API エラー: {json.dumps(body.get('errors'), ensure_ascii=False)}")
        return body.get("result")

    missing = ok(client.post(
        f"{API}/pages/assets/check-missing",
        json={"hashes": list(by_hash)},
    ))
    print(f"アップロード対象: {len(missing)} / {len(by_hash)} ファイル（残りはキャッシュ済み）")

    batch, batch_size = [], 0
    def flush():
        nonlocal batch, batch_size
        if batch:
            ok(client.post(f"{API}/pages/assets/upload", json=batch))
            print(f"  {len(batch)} ファイル送信")
            batch, batch_size = [], 0

    for h in missing:
        p = by_hash[h]
        data = p.read_bytes()
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        batch.append({
            "key": h,
            "value": base64.b64encode(data).decode(),
            "metadata": {"contentType": ctype},
            "base64": True,
        })
        batch_size += len(data)
        if batch_size >= BATCH_BYTES or len(batch) >= 500:
            flush()
    flush()

    # 既存ハッシュも「まだ使っている」と申告（wrangler と同じ）
    ok(client.post(f"{API}/pages/assets/upsert-hashes",
                   json={"hashes": list(by_hash)}))


def main() -> None:
    ap = argparse.ArgumentParser(description="Cloudflare Pages 直接アップロード")
    ap.add_argument("directory", help="公開ディレクトリ（この中身がサイトになる）")
    ap.add_argument("--project", required=True, help="Pages プロジェクト名")
    ap.add_argument("--branch", default="main",
                    help="main = 本番、それ以外はプレビュー URL")
    ap.add_argument("--create", action="store_true",
                    help="プロジェクトがなければ作る")
    args = ap.parse_args()

    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        sys.exit("CLOUDFLARE_API_TOKEN と CLOUDFLARE_ACCOUNT_ID を環境変数に設定すること")

    root = Path(args.directory)
    if not root.is_dir():
        sys.exit(f"エラー: ディレクトリがない: {root}")

    files = collect(root)
    manifest = {}
    by_hash: dict[str, Path] = {}
    for url_path, p in files.items():
        h = file_hash(p.read_bytes(), p.suffix.lstrip("."))
        manifest[url_path] = h
        by_hash[h] = p
    print(f"{len(files)} ファイル（一意 {len(by_hash)}）")

    pages = Pages(account, token)
    if not pages.project_exists(args.project):
        if args.create:
            pages.create_project(args.project)
        else:
            sys.exit(f"プロジェクトがない: {args.project}（--create で作成）")

    jwt = pages.upload_token(args.project)
    upload_assets(jwt, by_hash)
    result = pages.deploy(args.project, manifest, args.branch)
    print(f"デプロイ完了: {result.get('url', '(URL 不明)')}")


if __name__ == "__main__":
    main()

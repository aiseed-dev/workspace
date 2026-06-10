#!/usr/bin/env python3
"""台帳 — ソフトウェア管理台帳のランチャー（自分用の Flet アプリ）。

エディタやブラウザで目的のページに辿り着く時間をゼロにする：
起動 → 打つ → Enter → コピーされて閉じる。URL なら開く。

- 台帳の正体はただの JSON（~/.config/aiseed/daicho.json）。手で編集してよい
- 行の形：{"name": 名前, "category": 分類, "value": コマンドか URL, "note": 補足}
- value が http で始まれば「開く」、それ以外は「クリップボードへコピー」
- 検索は名前・分類・中身の部分一致。Enter は先頭の一件に効く

起動: python3 daicho.py          # デスクトップの窓
      python3 daicho.py --web    # ブラウザ表示（窓が出せない環境用）
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DATA_FILE = Path.home() / ".config" / "aiseed" / "daicho.json"

SAMPLE = [
    {"name": "サイト更新 aiseed.dev", "category": "deploy",
     "value": "cd ~/sites/aiseed.dev && python3 deploy.py"},
    {"name": "サイト更新 timej.net", "category": "deploy",
     "value": "cd ~/sites/timej.net && python3 deploy.py"},
    {"name": "蔵を開く", "category": "url", "value": "https://kura.aiseed.dev"},
    {"name": "Cloudflare ダッシュボード", "category": "url",
     "value": "https://dash.cloudflare.com"},
    {"name": "蔵 サービス状態", "category": "server",
     "value": "systemctl status pocketbase kura-api kura-front"},
    {"name": "蔵 API ログ", "category": "server",
     "value": "journalctl -u kura-api -e"},
    {"name": "バックアップ復元（xattr ごと）", "category": "server",
     "value": "tar --xattrs --xattrs-include='user.*' -xzf workspace-日付.tar.gz",
     "note": "--xattrs を忘れると権限が全部消える"},
    {"name": "権限を直接見る", "category": "server",
     "value": "getfattr -n user.ws.perm -d /srv/workspace/対象"},
    {"name": "Cloudflare トークンの場所", "category": "場所",
     "value": "~/.config/cloudflare/pages.env"},
]


def _bootstrap() -> None:
    """flet がなければ隣に .venv を作って入れ、その Python でやり直す。"""
    try:
        import flet  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get("DAICHO_BOOTSTRAP") == "1":
        sys.exit("flet の導入に失敗。隣の .venv を消してやり直すこと")
    venv = Path(__file__).resolve().parent / ".venv"
    py = venv / "bin" / "python3"
    if not py.exists():
        print("初回準備：.venv を作成して flet を導入する（一度だけ・数分）…")
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        subprocess.run([str(venv / "bin" / "pip"), "install", "--quiet",
                        "flet[all]==0.85.3"], check=True)
    os.environ["DAICHO_BOOTSTRAP"] = "1"
    os.execv(str(py), [str(py)] + sys.argv)


_bootstrap()

import flet as ft  # noqa: E402


def load_entries() -> list[dict]:
    if not DATA_FILE.is_file():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(
            json.dumps(SAMPLE, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"台帳を作った: {DATA_FILE}（中身は手で編集してよい）")
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def matches(entry: dict, q: str) -> bool:
    hay = " ".join([entry.get("name", ""), entry.get("category", ""),
                    entry.get("value", ""), entry.get("note", "")]).lower()
    return all(w in hay for w in q.lower().split())


@ft.component
def Daicho():
    query, set_query = ft.use_state("")
    flash, set_flash = ft.use_state("")
    entries = load_entries()
    hits = [e for e in entries if matches(e, query)] if query else entries

    page = ft.context.page

    def act(entry: dict):
        value = entry["value"]
        if value.startswith(("http://", "https://")):
            page.launch_url(value)
            set_flash(f"開いた: {entry['name']}")
        else:
            page.clipboard.set(value)
            set_flash(f"コピーした: {entry['name']}")

    def on_submit(_):
        if hits:
            act(hits[0])

    tiles = [
        ft.ListTile(
            title=ft.Text(e["name"]),
            subtitle=ft.Text(
                f"[{e.get('category', '')}] {e['value']}"
                + (f"  ※{e['note']}" if e.get("note") else "")),
            on_click=lambda _, e=e: act(e),
        )
        for e in hits[:30]
    ]
    return ft.Column(
        controls=[
            ft.TextField(label="検索（Enter で先頭をコピー / URL は開く）",
                         value=query, autofocus=True,
                         on_change=lambda ev: set_query(ev.control.value),
                         on_submit=on_submit),
            ft.Text(flash, color=ft.Colors.GREEN),
            *tiles,
            ft.Text(f"台帳: {DATA_FILE}", size=11, color=ft.Colors.GREY),
        ],
        scroll=ft.ScrollMode.AUTO, expand=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="ソフトウェア管理台帳ランチャー")
    ap.add_argument("--web", action="store_true", help="ブラウザ表示で起動")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    load_entries()  # 初回起動でも台帳ファイルを先に作っておく

    def app(page: ft.Page):
        page.title = "台帳"
        page.render(Daicho)

    if args.web:
        ft.run(app, view=None, port=args.port)
    else:
        ft.run(app)


if __name__ == "__main__":
    main()

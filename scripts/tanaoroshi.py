#!/usr/bin/env python3
"""棚卸し — 「自分が管理しているもの」の一覧を、現実を走査して生成する。

手で書いた管理台帳は必ず腐る。管理対象には物理的な痕跡があるので、
痕跡を走査して一覧を作る。「なぜ在るか」だけは現実から読めないため、
モノ自身に貼っておく（README の一行目・systemd の Description=・
cron のコメント行）。このツールはそれを拾って並べる。

依存なし（標準ライブラリのみ）。どのマシンでも動き、無いものは黙って飛ばす。

使い方:
    python3 tanaoroshi.py                  # ホーム配下を走査して表示
    python3 tanaoroshi.py ~/work ~/sites   # リポジトリを探す場所を指定
"""

import argparse
import configparser
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HOME = Path.home()


def first_heading(readme: Path) -> str:
    try:
        for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line[:80]
            if line.startswith("#"):
                # 見出しの次の本文一行を説明として使う
                continue
    except OSError:
        pass
    return ""


def git_repos(roots: list[Path], max_depth: int = 3) -> list[dict]:
    """`.git` のあるディレクトリ = 自分のプログラム・サイト・文書。"""
    found = []
    for root in roots:
        root = root.expanduser()
        if not root.is_dir():
            continue
        for dirpath, dirnames, _ in os.walk(root):
            d = Path(dirpath)
            depth = len(d.relative_to(root).parts)
            if depth > max_depth:
                dirnames.clear()
                continue
            # 隠しディレクトリと venv は降りない
            dirnames[:] = [n for n in dirnames
                           if not n.startswith(".") and n != "node_modules"
                           and not n.endswith(".venv") and n != "venv"]
            if (d / ".git").is_dir():
                desc = first_heading(d / "README.md")
                remote = ""
                try:
                    r = subprocess.run(
                        ["git", "-C", str(d), "remote", "get-url", "origin"],
                        capture_output=True, text=True, timeout=5)
                    remote = r.stdout.strip()
                except OSError:
                    pass
                found.append({"path": str(d), "desc": desc, "remote": remote})
                dirnames.clear()  # リポジトリの中は降りない
    return found


def systemd_units() -> list[dict]:
    """/etc/systemd/system にあるのは自分（管理者）が置いたものだけ。"""
    units = []
    base = Path("/etc/systemd/system")
    if not base.is_dir():
        return units
    for unit in sorted(base.glob("*.service")) + sorted(base.glob("*.timer")):
        if unit.is_symlink() and not unit.exists():
            continue
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        desc = ""
        try:
            cp.read(unit)
            desc = cp.get("Unit", "Description", fallback="")
        except (configparser.Error, OSError):
            pass
        state = ""
        try:
            r = subprocess.run(["systemctl", "is-enabled", unit.name],
                               capture_output=True, text=True, timeout=5)
            state = r.stdout.strip()
        except OSError:
            pass
        units.append({"name": unit.name, "desc": desc, "state": state})
    return units


def cron_entries() -> list[str]:
    """crontab の行。コメント行（# 説明）は直後の行の説明として拾う。"""
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True,
                           text=True, timeout=5)
    except OSError:
        return []
    if r.returncode != 0:
        return []
    out, comment = [], ""
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("#"):
            comment = line.lstrip("#").strip()
        elif line:
            out.append(f"{line}" + (f"  ← {comment}" if comment else ""))
            comment = ""
    return out


def cloudflare_pages() -> list[str]:
    """Pages のプロジェクト一覧（トークンがあれば）。"""
    env = HOME / ".config" / "cloudflare" / "pages.env"
    if not env.is_file():
        return []
    vals = {}
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    token = vals.get("CLOUDFLARE_API_TOKEN")
    account = vals.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        return []
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.load(resp)
    except OSError:
        return ["（Cloudflare に届かない）"]
    if not body.get("success"):
        return []
    return [f"{p['name']}  （{', '.join(p.get('domains', []))}）"
            for p in body["result"]]


def secrets_locations() -> list[str]:
    """~/.config 配下の env ファイル = 秘密の置き場の一覧（中身は見ない）。"""
    cfg = HOME / ".config"
    if not cfg.is_dir():
        return []
    return [str(p) for p in sorted(cfg.glob("*/*.env"))]


def main() -> None:
    ap = argparse.ArgumentParser(description="管理対象の棚卸し（走査して生成）")
    ap.add_argument("roots", nargs="*", default=[],
                    help="git リポジトリを探す場所（既定: ホーム直下）")
    args = ap.parse_args()
    roots = [Path(p) for p in args.roots] or [HOME]

    print("# 棚卸し（生成物。編集しない——正は現実の側にある）\n")

    repos = git_repos(roots)
    print(f"## 自分のリポジトリ（{len(repos)}）")
    for r in repos:
        line = f"- {r['path']}"
        if r["desc"]:
            line += f" — {r['desc']}"
        if r["remote"]:
            line += f"  [{r['remote']}]"
        print(line)

    units = systemd_units()
    if units:
        print(f"\n## 自分が置いた systemd ユニット（{len(units)}）")
        for u in units:
            print(f"- {u['name']} ({u['state']}) — {u['desc']}")

    cron = cron_entries()
    if cron:
        print(f"\n## cron（{len(cron)}）")
        for c in cron:
            print(f"- {c}")

    pages = cloudflare_pages()
    if pages:
        print(f"\n## Cloudflare Pages（{len(pages)}）")
        for p in pages:
            print(f"- {p}")

    secrets = secrets_locations()
    if secrets:
        print(f"\n## 秘密の置き場（{len(secrets)}）")
        for s in secrets:
            print(f"- {s}")

    print("\n説明が空のものは、モノ自身に貼ること"
          "（README 一行目 / Description= / cron のコメント）")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""台帳ランチャー — 運用台帳（docs/runbook.md）を直接読んで、即引く。

写しの台帳は持たない。手で写した台帳は必ず腐る——運用の書き場所は
runbook 一つにして、保存してある場所を直接見る。

読み方：
- ```sh ブロック：直前の「# コメント」を名前、次の行をコマンドとして拾う
- 表（| 名前 | 値 |）：場所と値の行をそのまま拾う
- 見出し（##）を分類にする

使い方：起動 → 打って絞る → Enter で先頭をコピー（URL は開く）。
    python3 daicho.py            # デスクトップの窓
    python3 daicho.py --web      # ブラウザ表示（窓が出せない環境用）
    python3 daicho.py 追加.md …  # 他の markdown も読ませる
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# 既定の正：このスクリプトと同じリポジトリの docs/runbook.md
DEFAULT_SOURCES = [Path(__file__).resolve().parent.parent / "docs" / "runbook.md"]


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


def parse_markdown(text: str, source: str) -> list[dict]:
    """markdown からコマンド・値の行を拾う。"""
    entries: list[dict] = []
    category = ""
    comment = ""
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            comment = ""
            continue
        if in_code:
            if stripped.startswith("#"):
                # ブロックコメントは小見出し。空行か次のコメントまで後続行に効く
                comment = stripped.lstrip("#").strip()
            elif stripped:
                # 行末コメント（コマンド  # 説明）は名前に回し、コピーする値から外す
                parts = re.split(r"\s{2,}#\s*", stripped, maxsplit=1)
                command = parts[0].strip()
                inline = parts[1].strip() if len(parts) > 1 else ""
                entries.append({
                    "name": inline or comment or command,
                    "category": category,
                    "value": command,
                    "source": source,
                })
            else:
                comment = ""
            continue
        if stripped.startswith("#"):
            category = stripped.lstrip("#").strip()
            continue
        # 表の行：バッククォート入りのセルを探し、最初のコード片を値にする
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            name = re.sub(r"[*`]", "", cells[0]) if cells else ""
            if len(cells) >= 2 and name and name not in ("何", "やりたいこと"):
                for cell in cells[1:]:
                    codes = re.findall(r"`([^`]+)`", cell)
                    if codes:
                        entries.append({"name": name, "category": category,
                                        "value": codes[0], "source": source})
                        break
    return entries


def load_entries(sources: list[Path]) -> list[dict]:
    entries: list[dict] = []
    for path in sources:
        if path.is_file():
            entries += parse_markdown(
                path.read_text(encoding="utf-8"), path.name)
        else:
            print(f"注意: 見つからない: {path}", file=sys.stderr)
    return entries


def matches(entry: dict, q: str) -> bool:
    hay = " ".join([entry["name"], entry["category"], entry["value"]]).lower()
    return all(w in hay for w in q.lower().split())


@ft.component
def Daicho(sources: tuple):
    query, set_query = ft.use_state("")
    flash, set_flash = ft.use_state("")
    # 毎描画で読み直す——正（チートシート）の更新が即反映される
    entries = load_entries(list(sources))
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
            subtitle=ft.Text(f"[{e['category']}] {e['value']}"),
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
            ft.Text("正: " + ", ".join(str(s) for s in sources),
                    size=11, color=ft.Colors.GREY),
        ],
        scroll=ft.ScrollMode.AUTO, expand=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="チートシートを直接引くランチャー")
    ap.add_argument("extra", nargs="*", help="追加で読む markdown")
    ap.add_argument("--web", action="store_true", help="ブラウザ表示で起動")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    sources = DEFAULT_SOURCES + [Path(p) for p in args.extra]

    def app(page: ft.Page):
        page.title = "台帳"
        page.render(Daicho, tuple(sources))

    if args.web:
        ft.run(app, view=None, port=args.port)
    else:
        ft.run(app)


if __name__ == "__main__":
    main()

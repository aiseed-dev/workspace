"""フロント（spec 4.5）：Flet の宣言的スタイル（Component API）で統一。

- @ft.component + use_state で、状態から UI を返す。page.update() は呼ばない
- 認可の判定はコアエンジンを通る（口が二つでも、判定は一つ——spec 4.4 v3.1）
- 認証は PocketBase へのログイン。得た Identity の user_id でエンジンを呼ぶ

最初の画面は三つ：ログイン → 入口一覧（自分が見える場所）→ フォルダ閲覧。
"""

from pathlib import Path

import flet as ft

from ..auth import pocketbase
from ..auth.base import Identity
from ..core.engine import Engine
from ..core.errors import KuraError


@ft.component
def LoginView(pb_url: str, on_login):
    email, set_email = ft.use_state("")
    password, set_password = ft.use_state("")
    error, set_error = ft.use_state("")

    def submit(_=None):
        result = pocketbase.login(pb_url, email, password)
        if result is None:
            set_error("ログインできない。メールとパスワードを確かめて")
            return
        _token, identity = result
        on_login(identity)

    return ft.Column(
        controls=[
            ft.Text("蔵", size=40, weight=ft.FontWeight.BOLD),
            ft.Text("aiseed workspace"),
            ft.TextField(label="メール", value=email, autofocus=True,
                         width=320, on_change=lambda e: set_email(e.control.value)),
            ft.TextField(label="パスワード", value=password, password=True,
                         width=320, on_submit=submit,
                         on_change=lambda e: set_password(e.control.value)),
            ft.FilledButton(content=ft.Text("ログイン"), on_click=submit),
            ft.Text(error, color=ft.Colors.RED),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
    )


@ft.component
def HelpView(is_admin: bool, on_back):
    """使い方の早見表。やり方を探す場所をアプリの中に置く（docs/runbook.md の利用者版）。"""
    sections: list[ft.Control] = [
        ft.FilledButton(content=ft.Text("戻る"), on_click=lambda _: on_back()),
        ft.Text("使い方", size=24, weight=ft.FontWeight.BOLD),
        ft.Text("入口", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("「自分の入口」は、あなたが見られる場所の一覧。"
                "上の階層が見えなくても、権限のある場所はここに必ず出る。"),
        ft.Text("権限", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("r = 閲覧（読める・ダウンロードできる）\n"
                "w = 編集（書ける・作れる・消せる）\n"
                "a = 管理（フォルダを作り、グループに権限を割り当て、共有を出せる）"),
        ft.Text("権限はフォルダごと。権限のない子フォルダは、名前ごと見えない。"
                "見えるはずの場所が見えないときは、管理者にグループの所属を確認。"),
        ft.Text("ファイル", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("フォルダ内のファイルは、そのフォルダの権限に従う。"
                "新しいフォルダを作れるのは、その場所に a を持つ人だけ。"),
    ]
    if is_admin:
        sections += [
            ft.Text("管理者向け", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("グループの作成・所属と権限の割り当ては API から行う"
                    "（画面は今後追加）。サーバーの運用・バックアップ・復元は"
                    " docs/runbook.md（作業台帳）を参照。"),
        ]
    return ft.Column(controls=sections, scroll=ft.ScrollMode.AUTO,
                     expand=True, spacing=12)


@ft.component
def EntriesView(engine: Engine, identity: Identity, on_open, on_help):
    entries = engine.entry_points(identity.user_id)
    tiles = [
        ft.ListTile(
            leading=ft.Icon(ft.Icons.FOLDER_SHARED),
            title=ft.Text(e["path"] or "（ルート）"),
            subtitle=ft.Text(f"権限: {e['bits']}"),
            on_click=lambda _, p=e["path"]: on_open(p),
        )
        for e in entries
    ]
    if not tiles:
        tiles = [ft.ListTile(title=ft.Text("見える場所がまだない。管理者に共有を頼んで"))]
    return ft.Column(
        controls=[
            ft.Row(controls=[
                ft.Text("自分の入口", size=20, weight=ft.FontWeight.BOLD),
                ft.TextButton(content=ft.Text("使い方"),
                              on_click=lambda _: on_help()),
            ]),
            *tiles,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


@ft.component
def DirView(engine: Engine, identity: Identity, path: str, on_open, on_entries,
            on_open_file):
    error, set_error = ft.use_state("")
    new_dir, set_new_dir = ft.use_state("")
    refresh, set_refresh = ft.use_state(0)

    try:
        listing = engine.list_dir(identity.user_id, path)
    except KuraError as e:
        return ft.Column(controls=[
            ft.Text(str(e), color=ft.Colors.RED),
            ft.FilledButton(content=ft.Text("入口へ"), on_click=lambda _: on_entries()),
        ])

    def mkdir(_=None):
        if not new_dir:
            return
        try:
            engine.mkdir(identity.user_id, f"{path}/{new_dir}" if path else new_dir)
            set_new_dir("")
            set_refresh(refresh + 1)
        except KuraError as e:
            set_error(str(e))

    rows: list[ft.Control] = [
        ft.Row(controls=[
            ft.FilledButton(icon=ft.Icons.HOME, content=ft.Text("入口"),
                            on_click=lambda _: on_entries()),
            ft.Text(f"/{path}" if path else "/（ルート）",
                    size=18, weight=ft.FontWeight.BOLD),
            ft.Text(f"権限: {listing['bits']}"),
        ]),
    ]
    for d in listing["dirs"]:
        rows.append(ft.ListTile(
            leading=ft.Icon(ft.Icons.FOLDER),
            title=ft.Text(d["name"]),
            subtitle=ft.Text(f"権限: {d['bits']}"),
            on_click=lambda _, p=d["path"]: on_open(p),
        ))
    for f in listing["files"]:
        readable = "." in f["name"] and \
            "." + f["name"].rsplit(".", 1)[-1].lower() in TEXT_SUFFIXES
        rows.append(ft.ListTile(
            leading=ft.Icon(ft.Icons.DESCRIPTION),
            title=ft.Text(f["name"]),
            subtitle=ft.Text(f"{f['size']} bytes"),
            on_click=(lambda _, p=f["path"]: on_open_file(p)) if readable else None,
        ))
    if "a" in listing["bits"]:
        rows.append(ft.Row(controls=[
            ft.TextField(label="新しいフォルダ", value=new_dir, width=240,
                         on_change=lambda e: set_new_dir(e.control.value),
                         on_submit=mkdir),
            ft.FilledButton(content=ft.Text("作る"), on_click=mkdir),
        ]))
    if error:
        rows.append(ft.Text(error, color=ft.Colors.RED))
    return ft.Column(controls=rows, scroll=ft.ScrollMode.AUTO, expand=True)


TEXT_SUFFIXES = {".md", ".txt", ".ics", ".log", ".json", ".csv"}
MAX_PREVIEW = 512 * 1024  # 表示はテキスト 512KB まで。それ以上はダウンロードで


@ft.component
def FileView(engine: Engine, identity: Identity, path: str, on_back):
    """テキスト系ファイルの中身を表示する。.md は整形、その他は等幅でそのまま。
    チートシートや手順書を「蔵の中の一ファイル」として読むための汎用ビュー。"""
    header = ft.Row(controls=[
        ft.FilledButton(content=ft.Text("戻る"), on_click=lambda _: on_back()),
        ft.Text(path.rsplit("/", 1)[-1], size=18, weight=ft.FontWeight.BOLD),
    ])
    try:
        p = engine.file_path(identity.user_id, path)
        if p.stat().st_size > MAX_PREVIEW:
            body: ft.Control = ft.Text("大きすぎるので表示しない。ダウンロードして開くこと")
        else:
            text = p.read_bytes().decode("utf-8", errors="replace")
            if p.suffix == ".md":
                body = ft.Markdown(value=text, selectable=True)
            else:
                body = ft.Text(text, selectable=True, font_family="monospace")
    except KuraError as e:
        body = ft.Text(str(e), color=ft.Colors.RED)
    return ft.Column(controls=[header, body],
                     scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)


@ft.component
def App(engine: Engine, pb_url: str):
    identity, set_identity = ft.use_state(None)
    # None = 入口一覧、文字列 = そのパスを閲覧中
    path, set_path = ft.use_state(None)
    file, set_file = ft.use_state(None)
    show_help, set_show_help = ft.use_state(False)

    if identity is None:
        return LoginView(pb_url, on_login=set_identity)
    if show_help:
        return HelpView(engine.groups.is_admin(identity.user_id),
                        on_back=lambda: set_show_help(False))
    if file is not None:
        return FileView(engine, identity, file, on_back=lambda: set_file(None))
    if path is None:
        return EntriesView(engine, identity, on_open=set_path,
                           on_help=lambda: set_show_help(True))
    return DirView(engine, identity, path,
                   on_open=set_path, on_entries=lambda: set_path(None),
                   on_open_file=set_file)


def run(data_root: str, pb_url: str, host: str = "127.0.0.1", port: int = 8500):
    engine = Engine(Path(data_root))

    def main(page: ft.Page):
        page.title = "蔵 (aiseed workspace)"
        page.render(App, engine, pb_url)

    ft.run(main, view=None, host=host, port=port)

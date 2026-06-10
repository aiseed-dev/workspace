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
def EntriesView(engine: Engine, identity: Identity, on_open):
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
        controls=[ft.Text("自分の入口", size=20, weight=ft.FontWeight.BOLD), *tiles],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


@ft.component
def DirView(engine: Engine, identity: Identity, path: str, on_open, on_entries):
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
        rows.append(ft.ListTile(
            leading=ft.Icon(ft.Icons.DESCRIPTION),
            title=ft.Text(f["name"]),
            subtitle=ft.Text(f"{f['size']} bytes"),
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


@ft.component
def App(engine: Engine, pb_url: str):
    identity, set_identity = ft.use_state(None)
    # None = 入口一覧、文字列 = そのパスを閲覧中
    path, set_path = ft.use_state(None)

    if identity is None:
        return LoginView(pb_url, on_login=set_identity)
    if path is None:
        return EntriesView(engine, identity, on_open=set_path)
    return DirView(engine, identity, path,
                   on_open=set_path, on_entries=lambda: set_path(None))


def run(data_root: str, pb_url: str, host: str = "127.0.0.1", port: int = 8500):
    engine = Engine(Path(data_root))

    def main(page: ft.Page):
        page.title = "蔵 (aiseed workspace)"
        page.render(App, engine, pb_url)

    ft.run(main, view=None, host=host, port=port)

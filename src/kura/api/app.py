"""連携の口：Python API サーバー（spec 4.4）。

フロントも外部システムも、同じ口を通る。認証はトークン検証関数一つ（差し替え式）。
認可の判定はコアエンジンに委ね、ここでは行わない。
"""

from pathlib import Path
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from ..auth.base import Identity, TokenVerifier
from ..core.engine import Engine
from ..core.errors import KuraError
from ..core.groups import ADMIN_GROUP


def create_app(engine: Engine, verifier: TokenVerifier) -> FastAPI:
    app = FastAPI(title="蔵 (aiseed workspace)", version="0.1.0")

    def me(authorization: Annotated[str | None, Header()] = None) -> Identity:
        if not authorization:
            raise HTTPException(401, "認証が要る")
        token = authorization.removeprefix("Bearer ").strip()
        identity = verifier.verify(token)
        if identity is None:
            raise HTTPException(401, "トークンが無効")
        return identity

    def admin(identity: Annotated[Identity, Depends(me)]) -> Identity:
        if not engine.groups.is_admin(identity.user_id):
            raise HTTPException(403, f"{ADMIN_GROUP} のメンバーだけができる")
        return identity

    @app.exception_handler(KuraError)
    async def kura_error(_req: Request, exc: KuraError):
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    # --- 自分 ---

    @app.get("/api/me")
    def get_me(identity: Annotated[Identity, Depends(me)]):
        return identity

    @app.get("/api/entries")
    def entries(identity: Annotated[Identity, Depends(me)]):
        return engine.entry_points(identity.user_id)

    # --- ディレクトリ ---

    @app.get("/api/dir")
    def list_dir(identity: Annotated[Identity, Depends(me)], path: str = ""):
        return engine.list_dir(identity.user_id, path)

    @app.post("/api/dir", status_code=201)
    def mkdir(identity: Annotated[Identity, Depends(me)], path: str):
        engine.mkdir(identity.user_id, path)
        return {"path": path}

    @app.delete("/api/dir", status_code=204)
    def rmdir(identity: Annotated[Identity, Depends(me)], path: str,
              recursive: bool = False):
        engine.rmdir(identity.user_id, path, recursive=recursive)

    @app.get("/api/perm")
    def get_perm(identity: Annotated[Identity, Depends(me)], path: str = ""):
        return engine.get_perm(identity.user_id, path)

    @app.put("/api/perm")
    def set_perm(identity: Annotated[Identity, Depends(me)], path: str = "",
                 perm: dict[str, str] = Body(...)):
        engine.set_perm(identity.user_id, path, perm)
        return {"path": path, "perm": perm}

    # --- ファイル ---

    @app.get("/api/file")
    def download(identity: Annotated[Identity, Depends(me)], path: str):
        p = engine.file_path(identity.user_id, path)
        return FileResponse(p, filename=p.name)

    @app.put("/api/file", status_code=204)
    async def upload(identity: Annotated[Identity, Depends(me)], path: str,
                     request: Request):
        data = await request.body()
        engine.write_file(identity.user_id, path, data)

    @app.delete("/api/file", status_code=204)
    def delete_file(identity: Annotated[Identity, Depends(me)], path: str):
        engine.delete_file(identity.user_id, path)

    @app.post("/api/move")
    def move(identity: Annotated[Identity, Depends(me)],
             body: dict = Body(...)):
        engine.move(identity.user_id, body["src"], body["dst"])
        return {"src": body["src"], "dst": body["dst"]}

    # --- グループ（g_admin のみ）---

    @app.get("/api/groups")
    def list_groups(identity: Annotated[Identity, Depends(me)]):
        # 一覧は全員。割り当て UI が要るため。メンバーの ID 列も含む
        return engine.groups.load()

    @app.post("/api/groups", status_code=201)
    def create_group(_admin: Annotated[Identity, Depends(admin)],
                     body: dict = Body(...)):
        gid = engine.groups.create(body["name"])
        return {"id": gid, "name": body["name"]}

    @app.put("/api/groups/{gid}")
    def update_group(_admin: Annotated[Identity, Depends(admin)], gid: str,
                     body: dict = Body(...)):
        if "name" in body:
            engine.groups.rename(gid, body["name"])
        if "members" in body:
            engine.groups.set_members(gid, body["members"])
        return engine.groups.load()[gid] | {"id": gid}

    @app.delete("/api/groups/{gid}", status_code=204)
    def delete_group(_admin: Annotated[Identity, Depends(admin)], gid: str):
        engine.groups.delete(gid)

    # --- 共有リンク ---

    @app.post("/api/links", status_code=201)
    def create_link(identity: Annotated[Identity, Depends(me)],
                    body: dict = Body(...)):
        link_id, token = engine.create_link(
            identity.user_id, body["path"], body.get("perm", "r"),
            body.get("expires_at"))
        # トークン平文を返すのはこの一度だけ。保存はハッシュ
        return {"id": link_id, "token": token, "url": f"/share/{token}"}

    @app.get("/api/links")
    def list_links(identity: Annotated[Identity, Depends(me)]):
        links = engine.links.list_all()
        if not engine.groups.is_admin(identity.user_id):
            links = {k: v for k, v in links.items()
                     if v["created_by"] == identity.user_id}
        return {k: {kk: vv for kk, vv in v.items() if kk != "token_sha256"}
                for k, v in links.items()}

    @app.delete("/api/links/{link_id}", status_code=204)
    def revoke_link(identity: Annotated[Identity, Depends(me)], link_id: str):
        links = engine.links.list_all()
        link = links.get(link_id)
        if link and not (engine.groups.is_admin(identity.user_id)
                         or link["created_by"] == identity.user_id):
            raise HTTPException(403, "自分の出したリンクだけ取り消せる")
        engine.links.revoke(link_id)

    # --- 共有リンクの公開口（認証なし、リンク自体が権限）---

    @app.get("/share/{token}")
    def open_share(token: str):
        p, _link = engine.open_link(token)
        if p.is_dir():
            raise HTTPException(501, "ディレクトリ共有の閲覧 UI は未実装")
        return FileResponse(Path(p), filename=p.name)

    # --- ICS 購読フィード（spec 4.6。認可は URL 内トークン＝共有リンク）---

    @app.get("/feed/{token}.ics")
    def ics_feed(token: str):
        from urllib.parse import quote

        name, body = engine.ics_feed(token)
        # HTTP ヘッダは latin-1 のみ。日本語名は RFC 5987 の filename* で渡す
        disposition = (f"inline; filename=\"calendar.ics\"; "
                       f"filename*=UTF-8''{quote(name)}.ics")
        return Response(
            content=body,
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": disposition},
        )

    return app

import pytest
from fastapi.testclient import TestClient

from kura.api.app import create_app
from kura.auth.base import Identity
from kura.auth.static import StaticTokenVerifier

from conftest import ADMIN, STAFF

TOKENS = {
    "tok-admin": Identity(ADMIN, "管理者", "admin@example.jp"),
    "tok-staff": Identity(STAFF, "職員", "staff@example.jp"),
}


@pytest.fixture
def client(engine):
    app = create_app(engine, StaticTokenVerifier(TOKENS))
    return TestClient(app)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_requires_auth(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=auth("bad")).status_code == 401


def test_me(client):
    r = client.get("/api/me", headers=auth("tok-admin"))
    assert r.status_code == 200
    assert r.json() == {"user_id": ADMIN, "display_name": "管理者",
                        "email": "admin@example.jp"}


def test_file_roundtrip(client):
    h = auth("tok-admin")
    assert client.post("/api/dir", params={"path": "資料"}, headers=h).status_code == 201
    assert client.put("/api/file", params={"path": "資料/予定.txt"},
                      content="中身".encode(), headers=h).status_code == 204
    r = client.get("/api/file", params={"path": "資料/予定.txt"}, headers=h)
    assert r.status_code == 200 and r.content == "中身".encode()

    listing = client.get("/api/dir", params={"path": "資料"}, headers=h).json()
    assert [f["name"] for f in listing["files"]] == ["予定.txt"]
    assert listing["files"][0]["creator"] == ADMIN


def test_permission_enforced_via_api(client, engine):
    h_admin, h_staff = auth("tok-admin"), auth("tok-staff")
    client.post("/api/dir", params={"path": "d"}, headers=h_admin)
    client.put("/api/file", params={"path": "d/f"}, content=b"x", headers=h_admin)

    assert client.get("/api/file", params={"path": "d/f"},
                      headers=h_staff).status_code == 403

    r = client.put("/api/perm", params={"path": "d"},
                   json={"g_admin": "rwa", engine.staff_gid: "r"}, headers=h_admin)
    assert r.status_code == 200
    assert client.get("/api/file", params={"path": "d/f"},
                      headers=h_staff).status_code == 200
    # r だけでは書けない
    assert client.put("/api/file", params={"path": "d/f"}, content=b"y",
                      headers=h_staff).status_code == 403


def test_path_traversal_rejected(client):
    r = client.get("/api/file", params={"path": "../etc/passwd"},
                   headers=auth("tok-admin"))
    assert r.status_code == 400


def test_entries(client, engine):
    h = auth("tok-admin")
    client.post("/api/dir", params={"path": "x"}, headers=h)
    client.put("/api/perm", params={"path": "x"},
               json={"g_admin": "rwa", engine.staff_gid: "r"}, headers=h)
    r = client.get("/api/entries", headers=auth("tok-staff"))
    assert [e["path"] for e in r.json()] == ["x"]


def test_groups_admin_only(client):
    assert client.post("/api/groups", json={"name": "経理"},
                       headers=auth("tok-staff")).status_code == 403
    r = client.post("/api/groups", json={"name": "経理"}, headers=auth("tok-admin"))
    assert r.status_code == 201
    gid = r.json()["id"]
    r = client.put(f"/api/groups/{gid}", json={"members": [STAFF]},
                   headers=auth("tok-admin"))
    assert r.json()["members"] == [STAFF]
    assert client.delete(f"/api/groups/{gid}",
                         headers=auth("tok-admin")).status_code == 204


def test_share_link_public_download(client):
    h = auth("tok-admin")
    client.post("/api/dir", params={"path": "d"}, headers=h)
    client.put("/api/file", params={"path": "d/公開.txt"}, content=b"open",
               headers=h)
    r = client.post("/api/links", json={"path": "d/公開.txt", "perm": "r"},
                    headers=h)
    assert r.status_code == 201
    url = r.json()["url"]
    # 認証なしで取れる（リンク自体が権限）
    assert client.get(url).content == b"open"
    # 取り消すと死ぬ
    client.delete(f"/api/links/{r.json()['id']}", headers=h)
    assert client.get(url).status_code == 404


def test_staff_cannot_revoke_others_link(client, engine):
    h = auth("tok-admin")
    client.post("/api/dir", params={"path": "d"}, headers=h)
    client.put("/api/file", params={"path": "d/f"}, content=b"x", headers=h)
    link_id = client.post("/api/links", json={"path": "d/f"}, headers=h).json()["id"]
    assert client.delete(f"/api/links/{link_id}",
                         headers=auth("tok-staff")).status_code == 403

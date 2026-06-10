import time

import pytest

from kura.core.errors import NotFound, PermissionDenied

from conftest import ADMIN, STAFF


def test_link_roundtrip(engine):
    engine.mkdir(ADMIN, "d")
    engine.write_file(ADMIN, "d/f.txt", b"shared")
    link_id, token = engine.create_link(ADMIN, "d/f.txt", "r")
    p, link = engine.open_link(token)
    assert p.read_bytes() == b"shared"
    assert link["perm"] == "r"
    # 平文トークンはディスクに置かない
    assert token not in (engine.root / "links").read_text()


def test_link_requires_a(engine):
    engine.mkdir(ADMIN, "d")
    engine.write_file(ADMIN, "d/f", b"x")
    grant = engine.get_perm(ADMIN, "d") | {engine.staff_gid: "rw"}
    engine.set_perm(ADMIN, "d", grant)
    with pytest.raises(PermissionDenied):
        engine.create_link(STAFF, "d/f", "r")


def test_link_expiry(engine):
    engine.mkdir(ADMIN, "d")
    engine.write_file(ADMIN, "d/f", b"x")
    _, token = engine.create_link(ADMIN, "d/f", "r",
                                  expires_at=time.time() - 1)
    with pytest.raises(NotFound):
        engine.open_link(token)


def test_link_revoke(engine):
    engine.mkdir(ADMIN, "d")
    engine.write_file(ADMIN, "d/f", b"x")
    link_id, token = engine.create_link(ADMIN, "d/f", "r")
    engine.links.revoke(link_id)
    with pytest.raises(NotFound):
        engine.open_link(token)


def test_link_breaks_on_move(engine):
    """v3.1 の割り切り：移動・改名でリンクは切れる。"""
    engine.mkdir(ADMIN, "d")
    engine.write_file(ADMIN, "d/f", b"x")
    _, token = engine.create_link(ADMIN, "d/f", "r")
    engine.move(ADMIN, "d/f", "d/g")
    with pytest.raises(NotFound):
        engine.open_link(token)

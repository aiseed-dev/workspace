import os

import pytest

from kura.core import perms
from kura.core.errors import Conflict, NotFound, PermissionDenied

from conftest import ADMIN, OUTSIDER, STAFF


def grant(engine, rel, gid, bits):
    engine.set_perm(ADMIN, rel, engine.get_perm(ADMIN, rel) | {gid: bits})


def test_root_initialized(engine):
    assert engine.bits(ADMIN, engine.root) == {"r", "w", "a"}
    assert engine.bits(STAFF, engine.root) == set()


def test_mkdir_copies_parent_perm_and_records_creator(engine):
    engine.mkdir(ADMIN, "総務")
    d = engine.root / "総務"
    assert perms.read_perm(d) == {"g_admin": "rwa"}
    assert perms.get_creator(d) == ADMIN


def test_mkdir_requires_a(engine):
    with pytest.raises(PermissionDenied):
        engine.mkdir(STAFF, "勝手")


def test_traversal_judged_by_target_dir_only(engine):
    """v3.1 決定：/a に権限がなくても /a/b に r があれば到達できる。"""
    engine.mkdir(ADMIN, "親")
    engine.mkdir(ADMIN, "親/子")
    grant(engine, "親/子", engine.staff_gid, "r")
    assert engine.bits(STAFF, engine.root / "親") == set()
    listing = engine.list_dir(STAFF, "親/子")
    assert listing["bits"] == "r"


def test_listing_hides_unreadable_subdirs(engine):
    """帰結 1：r を持たない子ディレクトリは名前ごと見えない。ファイルは入れ物に従い全部見える。"""
    engine.mkdir(ADMIN, "共有")
    engine.mkdir(ADMIN, "共有/公開")
    engine.mkdir(ADMIN, "共有/秘密")
    grant(engine, "共有", engine.staff_gid, "r")
    grant(engine, "共有/公開", engine.staff_gid, "r")
    engine.write_file(ADMIN, "共有/お知らせ.txt", b"hello")

    listing = engine.list_dir(STAFF, "共有")
    assert [d["name"] for d in listing["dirs"]] == ["公開"]
    assert [f["name"] for f in listing["files"]] == ["お知らせ.txt"]

    admin_listing = engine.list_dir(ADMIN, "共有")
    assert [d["name"] for d in admin_listing["dirs"]] == ["公開", "秘密"]


def test_entry_points(engine):
    """帰結 2：入口 = r を持ち、親には持たないディレクトリ。"""
    engine.mkdir(ADMIN, "親")
    engine.mkdir(ADMIN, "親/子")
    engine.mkdir(ADMIN, "親/子/孫")
    grant(engine, "親/子", engine.staff_gid, "rw")
    grant(engine, "親/子/孫", engine.staff_gid, "r")

    assert [e["path"] for e in engine.entry_points(STAFF)] == ["親/子"]
    assert [e["path"] for e in engine.entry_points(ADMIN)] == [""]
    assert engine.entry_points(OUTSIDER) == []


def test_file_rw_and_deny(engine):
    engine.mkdir(ADMIN, "d")
    grant(engine, "d", engine.staff_gid, "r")
    engine.write_file(ADMIN, "d/メモ.txt", "内容".encode())

    # r では読めるが書けない・消せない
    assert engine.file_path(STAFF, "d/メモ.txt").read_bytes() == "内容".encode()
    with pytest.raises(PermissionDenied):
        engine.write_file(STAFF, "d/メモ.txt", b"x")
    with pytest.raises(PermissionDenied):
        engine.delete_file(STAFF, "d/メモ.txt")

    # w を足すと書ける・消せる
    grant(engine, "d", engine.staff_gid, "rw")
    engine.write_file(STAFF, "d/メモ.txt", "上書き".encode())
    engine.delete_file(STAFF, "d/メモ.txt")

    # 部外者は読むことすらできない
    with pytest.raises(PermissionDenied):
        engine.file_path(OUTSIDER, "d/メモ.txt")


def test_creator_kept_on_overwrite(engine):
    engine.mkdir(ADMIN, "d")
    grant(engine, "d", engine.staff_gid, "rw")
    engine.write_file(ADMIN, "d/f", b"1")
    engine.write_file(STAFF, "d/f", b"2")
    assert perms.get_creator(engine.root / "d" / "f") == ADMIN


def test_set_perm_requires_a_on_dir_itself(engine):
    engine.mkdir(ADMIN, "d")
    grant(engine, "d", engine.staff_gid, "rw")
    with pytest.raises(PermissionDenied):
        engine.set_perm(STAFF, "d", {engine.staff_gid: "rwa"})
    with pytest.raises(PermissionDenied):
        engine.get_perm(STAFF, "d")
    # a を持てば自分のディレクトリとして管理できる（現場完結、spec 5 章）
    grant(engine, "d", engine.staff_gid, "rwa")
    engine.set_perm(STAFF, "d", {engine.staff_gid: "rwa"})


def test_set_perm_rejects_unknown_group(engine):
    with pytest.raises(NotFound):
        engine.set_perm(ADMIN, "", {"g_nope": "r"})


def test_move_keeps_xattr(engine):
    engine.mkdir(ADMIN, "a")
    engine.mkdir(ADMIN, "b")
    engine.mkdir(ADMIN, "a/sub")
    grant(engine, "a/sub", engine.staff_gid, "r")
    engine.move(ADMIN, "a/sub", "b/sub")
    assert engine.staff_gid in perms.read_perm(engine.root / "b" / "sub")


def test_move_file_requires_w_both_sides(engine):
    engine.mkdir(ADMIN, "src")
    engine.mkdir(ADMIN, "dst")
    grant(engine, "src", engine.staff_gid, "rw")
    grant(engine, "dst", engine.staff_gid, "r")
    engine.write_file(ADMIN, "src/f", b"x")
    with pytest.raises(PermissionDenied):
        engine.move(STAFF, "src/f", "dst/f")
    grant(engine, "dst", engine.staff_gid, "rw")
    engine.move(STAFF, "src/f", "dst/f")


def test_rmdir(engine):
    engine.mkdir(ADMIN, "d")
    engine.mkdir(ADMIN, "d/sub")
    with pytest.raises(Conflict):
        engine.rmdir(ADMIN, "d")  # 空でない
    engine.rmdir(ADMIN, "d", recursive=True)
    assert not (engine.root / "d").exists()
    with pytest.raises(PermissionDenied):
        engine.rmdir(STAFF, "")  # ルートは消せない（権限以前に拒否）


def test_reserved_files_not_listed(engine):
    listing = engine.list_dir(ADMIN, "")
    names = [f["name"] for f in listing["files"]]
    assert "groups" not in names and "groups.lock" not in names


def test_group_deletion_leaves_dangling_xattr_harmless(engine):
    """グループを消しても xattr に残骸が残るが、所属者がいないので効かない。"""
    engine.mkdir(ADMIN, "d")
    grant(engine, "d", engine.staff_gid, "r")
    engine.groups.delete(engine.staff_gid)
    assert engine.bits(STAFF, engine.root / "d") == set()

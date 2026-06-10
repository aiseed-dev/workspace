import pytest

from kura.core.errors import Conflict, NotFound
from kura.core.groups import ADMIN_GROUP, GroupStore

from conftest import ADMIN, STAFF


def test_init_creates_admin_group(engine):
    assert engine.groups.is_admin(ADMIN)
    assert not engine.groups.is_admin(STAFF)


def test_init_twice_fails(engine):
    with pytest.raises(Conflict):
        engine.groups.init(ADMIN)


def test_membership(engine):
    assert engine.staff_gid in engine.groups.groups_of(STAFF)
    assert engine.groups.groups_of("nobody") == set()


def test_set_members_dedupes(engine):
    engine.groups.set_members(engine.staff_gid, [STAFF, STAFF, ADMIN])
    assert engine.groups.load()[engine.staff_gid]["members"] == [STAFF, ADMIN]


def test_admin_group_cannot_be_deleted(engine):
    with pytest.raises(Conflict):
        engine.groups.delete(ADMIN_GROUP)


def test_unknown_group_operations(engine):
    with pytest.raises(NotFound):
        engine.groups.set_members("g_nope", [])
    with pytest.raises(NotFound):
        engine.groups.delete("g_nope")


def test_groups_file_is_json_on_disk(engine, root):
    text = (root / "groups").read_text(encoding="utf-8")
    assert ADMIN_GROUP in text


def test_missing_file_means_no_groups(tmp_path):
    store = GroupStore(tmp_path)
    assert store.load() == {}

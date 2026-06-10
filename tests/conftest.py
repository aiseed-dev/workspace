import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kura.core.engine import Engine  # noqa: E402

ADMIN = "u_admin"
STAFF = "u_staff"
OUTSIDER = "u_outsider"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def engine(root: Path) -> Engine:
    """g_admin=[u_admin] で初期化し、g_staff=[u_staff] を足した状態。"""
    e = Engine(root)
    e.init_root(ADMIN)
    gid = e.groups.create("職員")
    e.groups.set_members(gid, [STAFF])
    e.staff_gid = gid  # テストから参照する
    return e

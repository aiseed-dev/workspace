import unicodedata

import pytest

from kura.core import paths
from kura.core.errors import InvalidPath


def test_traversal_rejected():
    for bad in ["../etc", "a/../../b", "..", "a/..", "./a", "a//b"]:
        with pytest.raises(InvalidPath):
            paths.normalize(bad)


def test_reserved_names_rejected():
    for bad in ["groups", "links", "groups.lock", "groups/x"]:
        with pytest.raises(InvalidPath):
            paths.normalize(bad)
    # ルート直下以外なら groups という名前は使える
    assert paths.normalize("a/groups") == "a/groups"


def test_nfc_normalization():
    nfd = unicodedata.normalize("NFD", "パンフレット")
    assert paths.normalize(nfd) == "パンフレット"


def test_symlink_rejected(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(InvalidPath):
        paths.resolve(tmp_path, "link/x")


def test_root_is_empty_string(tmp_path):
    assert paths.resolve(tmp_path, "") == tmp_path
    assert paths.resolve(tmp_path, "/") == tmp_path

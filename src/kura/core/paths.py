"""パス安全（spec 7 章・v3.1）。

- データルート配下への解決を強制する（`..` 拒否）
- シンボリックリンクは作らせない・辿らない
- ファイル名は NFC に正規化（日本語名の NFC/NFD 揺れを吸収）
- ルート直下の管理ファイル名は予約語
"""

import unicodedata
from pathlib import Path

from .errors import InvalidPath

RESERVED_NAMES = {"groups", "groups.lock", "links", "links.lock"}


def normalize(rel: str) -> str:
    """利用者から受けた相対パスを検証し、NFC 正規化した相対パスを返す。"" はルート。"""
    rel = unicodedata.normalize("NFC", rel).strip("/")
    if rel == "":
        return ""
    parts = rel.split("/")
    for part in parts:
        if part in ("", ".", "..") or "\x00" in part:
            raise InvalidPath(f"不正なパス: {rel!r}")
    if parts[0] in RESERVED_NAMES:
        raise InvalidPath(f"予約された名前: {parts[0]!r}")
    return "/".join(parts)


def resolve(root: Path, rel: str) -> Path:
    """相対パスをルート配下の実パスに解決する。途中にシンボリックリンクがあれば拒否。"""
    rel = normalize(rel)
    p = root
    for part in rel.split("/") if rel else []:
        p = p / part
        if p.is_symlink():
            raise InvalidPath(f"シンボリックリンクは辿らない: {rel!r}")
    return p


def to_rel(root: Path, p: Path) -> str:
    return str(p.relative_to(root))

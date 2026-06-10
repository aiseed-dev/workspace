"""権限の正 = ディレクトリの xattr（spec 4.2・5 章）。

- `user.ws.perm`（ディレクトリのみ）: グループ ID → 権限ビットの JSON。一キーに畳んで
  更新の原子性を setxattr 一回に閉じる。
- `user.ws.creator`（ファイル・ディレクトリ両方）: 作成者の利用者 ID。表示・記録用であり
  権限判定の入力ではない。
- 権限ビットは r（閲覧）/ w（編集）/ a（管理）。判定は当該ディレクトリの xattr だけで行い、
  祖先は見ない（v3.1 traversal 決定）。
"""

import errno
import json
import os
from pathlib import Path

from .errors import GroupLimitExceeded, InvalidPath

PERM_XATTR = "user.ws.perm"
CREATOR_XATTR = "user.ws.creator"
BITS = frozenset("rwa")


def read_perm(d: Path) -> dict[str, str]:
    try:
        raw = os.getxattr(d, PERM_XATTR)
    except OSError as e:
        if e.errno in (errno.ENODATA, getattr(errno, "ENOATTR", errno.ENODATA)):
            return {}
        raise
    return json.loads(raw)


def write_perm(d: Path, perm: dict[str, str]) -> None:
    for gid, bits in perm.items():
        if not gid or not set(bits) <= BITS or bits == "":
            raise InvalidPath(f"不正な権限指定: {gid!r}: {bits!r}")
    data = json.dumps(perm, ensure_ascii=False, separators=(",", ":")).encode()
    try:
        os.setxattr(d, PERM_XATTR, data)
    except OSError as e:
        if e.errno == errno.ENOSPC:
            raise GroupLimitExceeded(
                "このフォルダに設定できるグループ数の上限を超えた"
            ) from e
        raise


def effective_bits(perm: dict[str, str], user_groups: set[str]) -> set[str]:
    """利用者の所属グループに付いたビットの和。個人には直接貼らない（spec 5 章）。"""
    bits: set[str] = set()
    for gid, b in perm.items():
        if gid in user_groups:
            bits |= set(b)
    return bits


def set_creator(p: Path, user_id: str) -> None:
    os.setxattr(p, CREATOR_XATTR, user_id.encode())


def get_creator(p: Path) -> str | None:
    try:
        return os.getxattr(p, CREATOR_XATTR).decode()
    except OSError as e:
        if e.errno in (errno.ENODATA, getattr(errno, "ENOATTR", errno.ENODATA)):
            return None
        raise

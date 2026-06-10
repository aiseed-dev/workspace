"""グループの定義と所属はルート直下の groups ファイルに持つ（spec 4.2・7 章）。

/etc/group は使わない——OS アカウントと Workspace 利用者を絡めない。
更新は flock（別ロックファイル）+ atomic rename。
"""

import json
import secrets
from pathlib import Path
from typing import Callable

from .atomic import atomic_write, locked
from .errors import Conflict, NotFound

ADMIN_GROUP = "g_admin"

# {gid: {"name": 表示名, "members": [利用者ID, ...]}}
Groups = dict[str, dict]


class GroupStore:
    def __init__(self, root: Path):
        self.path = root / "groups"
        self.lock_path = root / "groups.lock"

    def load(self) -> Groups:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _update(self, fn: Callable[[Groups], None]) -> Groups:
        with locked(self.lock_path):
            groups = self.load()
            fn(groups)
            atomic_write(
                self.path,
                json.dumps(groups, ensure_ascii=False, indent=1).encode(),
            )
            return groups

    def init(self, admin_user_id: str) -> None:
        def fn(groups: Groups) -> None:
            if ADMIN_GROUP in groups:
                raise Conflict("初期化済み")
            groups[ADMIN_GROUP] = {"name": "管理者", "members": [admin_user_id]}

        self._update(fn)

    def groups_of(self, user_id: str) -> set[str]:
        return {gid for gid, g in self.load().items() if user_id in g["members"]}

    def is_admin(self, user_id: str) -> bool:
        return ADMIN_GROUP in self.groups_of(user_id)

    def create(self, name: str) -> str:
        gid = f"g_{secrets.token_hex(4)}"

        def fn(groups: Groups) -> None:
            groups[gid] = {"name": name, "members": []}

        self._update(fn)
        return gid

    def set_members(self, gid: str, members: list[str]) -> None:
        def fn(groups: Groups) -> None:
            if gid not in groups:
                raise NotFound(f"グループがない: {gid}")
            groups[gid]["members"] = list(dict.fromkeys(members))

        self._update(fn)

    def rename(self, gid: str, name: str) -> None:
        def fn(groups: Groups) -> None:
            if gid not in groups:
                raise NotFound(f"グループがない: {gid}")
            groups[gid]["name"] = name

        self._update(fn)

    def delete(self, gid: str) -> None:
        def fn(groups: Groups) -> None:
            if gid == ADMIN_GROUP:
                raise Conflict("管理者グループは消せない")
            if gid not in groups:
                raise NotFound(f"グループがない: {gid}")
            del groups[gid]

        self._update(fn)

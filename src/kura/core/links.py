"""共有リンク（spec 5 章・7 章 v3.1）。

リンク = トークン + 対象 + 権限（閲覧/編集）+ 期限、をルート直下の links ファイルに持つ。
トークンはハッシュで保存する（平文を置かない）。対象はパス参照——移動・改名でリンクは
切れると割り切る（観察項目）。
"""

import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Callable

from .atomic import atomic_write, locked
from .errors import InvalidPath, NotFound

# {link_id: {"target": 相対パス, "perm": "r"|"rw", "token_sha256": hex,
#            "created_by": 利用者ID, "created_at": epoch, "expires_at": epoch|None}}
Links = dict[str, dict]


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LinkStore:
    def __init__(self, root: Path):
        self.path = root / "links"
        self.lock_path = root / "links.lock"

    def load(self) -> Links:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _update(self, fn: Callable[[Links], None]) -> None:
        with locked(self.lock_path):
            links = self.load()
            fn(links)
            atomic_write(
                self.path,
                json.dumps(links, ensure_ascii=False, indent=1).encode(),
            )

    def create(
        self,
        target: str,
        perm: str,
        created_by: str,
        expires_at: float | None = None,
    ) -> tuple[str, str]:
        """リンクを作り (link_id, トークン平文) を返す。平文はこの一度しか得られない。"""
        if perm not in ("r", "rw"):
            raise InvalidPath(f"リンクの権限は r か rw: {perm!r}")
        link_id = f"l_{secrets.token_hex(4)}"
        token = secrets.token_urlsafe(32)

        def fn(links: Links) -> None:
            links[link_id] = {
                "target": target,
                "perm": perm,
                "token_sha256": _hash(token),
                "created_by": created_by,
                "created_at": time.time(),
                "expires_at": expires_at,
            }

        self._update(fn)
        return link_id, token

    def resolve(self, token: str) -> dict | None:
        """トークンから有効なリンクを引く。期限切れ・不在は None。"""
        h = _hash(token)
        for link in self.load().values():
            if secrets.compare_digest(link["token_sha256"], h):
                exp = link.get("expires_at")
                if exp is not None and exp < time.time():
                    return None
                return link
        return None

    def list_all(self) -> Links:
        return self.load()

    def revoke(self, link_id: str) -> None:
        def fn(links: Links) -> None:
            if link_id not in links:
                raise NotFound(f"リンクがない: {link_id}")
            del links[link_id]

        self._update(fn)

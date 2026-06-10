"""トークン検証関数——API が認証について持つ唯一のもの（spec 4.4）。

型は v3.1 で固定：トークン文字列 → Identity{user_id, display_name, email} | None。
表示名まで返すことで「ID → 表示名の解決」がこの関数に畳まれ、差し替え先でも同じ型で済む。
権限判定（xattr + グループ）は検証の後ろにあり、認証方式が何であっても変わらない。
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Identity:
    user_id: str
    display_name: str
    email: str


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Identity | None: ...

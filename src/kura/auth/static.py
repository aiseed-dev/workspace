"""固定トークンの検証器。テストと、検証実装が差し替え式であることの最小の証明。"""

from .base import Identity


class StaticTokenVerifier:
    def __init__(self, tokens: dict[str, Identity]):
        self._tokens = dict(tokens)

    def verify(self, token: str) -> Identity | None:
        return self._tokens.get(token)

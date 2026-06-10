"""標準実装：PocketBase への introspection + 短 TTL キャッシュ（v3.1 案 B）。

PB のトークンは署名鍵が利用者レコードごと（tokenKey）で公開鍵ローカル検証ができない。
内部実装に依存せず auth-refresh で問い合わせ、短 TTL キャッシュで往復を消す。
失効（パスワード変更による tokenKey 回転）の遅れは TTL 分のみ。
"""

import time

import httpx

from .base import Identity


class PocketBaseVerifier:
    def __init__(
        self,
        base_url: str,
        collection: str = "users",
        ttl: float = 60.0,
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.ttl = ttl
        self._client = client or httpx.Client(timeout=5.0)
        self._cache: dict[str, tuple[float, Identity]] = {}

    def verify(self, token: str) -> Identity | None:
        now = time.monotonic()
        cached = self._cache.get(token)
        if cached and cached[0] > now:
            return cached[1]
        try:
            resp = self._client.post(
                f"{self.base_url}/api/collections/{self.collection}/auth-refresh",
                headers={"Authorization": token},
            )
        except httpx.HTTPError:
            # PB に届かないときは検証失敗（キャッシュが生きていればそちらで通る）
            return None
        if resp.status_code != 200:
            self._cache.pop(token, None)
            return None
        record = resp.json().get("record", {})
        identity = Identity(
            user_id=record.get("id", ""),
            display_name=record.get("name") or record.get("email", ""),
            email=record.get("email", ""),
        )
        if not identity.user_id:
            return None
        if len(self._cache) > 10_000:
            self._cache.clear()
        self._cache[token] = (now + self.ttl, identity)
        return identity

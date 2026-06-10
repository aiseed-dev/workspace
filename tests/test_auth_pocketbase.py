import httpx

from kura.auth.pocketbase import PocketBaseVerifier


def make_verifier(handler, ttl=60.0):
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, timeout=5.0)
    return PocketBaseVerifier("http://pb.local", ttl=ttl, client=client)


def test_valid_token():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        assert request.url.path == "/api/collections/users/auth-refresh"
        assert request.headers["authorization"] == "tok"
        return httpx.Response(200, json={"token": "tok2", "record": {
            "id": "u_1", "name": "山田", "email": "y@example.jp"}})

    v = make_verifier(handler)
    identity = v.verify("tok")
    assert identity.user_id == "u_1"
    assert identity.display_name == "山田"
    # キャッシュが効き、二度目は PB に行かない
    assert v.verify("tok") is identity
    assert calls["n"] == 1


def test_cache_expiry():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"record": {
            "id": "u_1", "name": "", "email": "y@example.jp"}})

    v = make_verifier(handler, ttl=0.0)
    v.verify("tok")
    v.verify("tok")
    assert calls["n"] == 2
    # name が空ならメールを表示名に使う
    assert v.verify("tok").display_name == "y@example.jp"


def test_invalid_token():
    v = make_verifier(lambda req: httpx.Response(401, json={}))
    assert v.verify("bad") is None


def test_pb_unreachable():
    def handler(request):
        raise httpx.ConnectError("down")

    v = make_verifier(handler)
    assert v.verify("tok") is None

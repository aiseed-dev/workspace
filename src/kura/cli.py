"""CLI：ブートストラップ（spec 6 章 v3.1）とサーバー起動。

初期化はサーバー上で CLI 一発。サーバーに入れる人（=運用者）だけが実行でき、
Web に「未初期化状態の窓」を晒さない。

PocketBase スーパーユーザーの作成は PB 自身の CLI を借りる：
    ./pocketbase superuser upsert <email> <password>
kura init は、(任意) PB に最初の利用者を作り、groups ファイルと
ルート xattr を初期化する。
"""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from .core.engine import Engine


def _pb_create_first_user(pb_url: str, superuser_email: str,
                          superuser_password: str, email: str,
                          password: str, name: str) -> str:
    """PB API でスーパーユーザー認証し、最初の利用者を作って ID を返す。"""
    import httpx

    base = pb_url.rstrip("/")
    with httpx.Client(timeout=10.0) as client:
        auth = client.post(
            f"{base}/api/collections/_superusers/auth-with-password",
            json={"identity": superuser_email, "password": superuser_password},
        )
        auth.raise_for_status()
        headers = {"Authorization": auth.json()["token"]}
        resp = client.post(
            f"{base}/api/collections/users/records",
            headers=headers,
            json={"email": email, "password": password,
                  "passwordConfirm": password, "name": name, "verified": True},
        )
        resp.raise_for_status()
        return resp.json()["id"]


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.data_root)
    if args.pb_url:
        password = args.password or secrets.token_urlsafe(12)
        user_id = _pb_create_first_user(
            args.pb_url, args.pb_superuser_email, args.pb_superuser_password,
            args.email, password, args.name or args.email)
        print(f"PocketBase に最初の利用者を作成: {args.email} (id={user_id})")
        if not args.password:
            print(f"初期パスワード（変更を促すこと）: {password}")
    elif args.admin_user_id:
        user_id = args.admin_user_id
    else:
        print("--pb-url か --admin-user-id のどちらかが要る", file=sys.stderr)
        return 2

    engine = Engine(root)
    engine.init_root(user_id)
    print(f"初期化完了: {root}（g_admin = [{user_id}], ルート権限 rwa）")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .api.app import create_app

    engine = Engine(Path(args.data_root))
    if args.auth == "pocketbase":
        from .auth.pocketbase import PocketBaseVerifier

        verifier = PocketBaseVerifier(args.pb_url, ttl=args.token_ttl)
    else:
        from .auth.base import Identity
        from .auth.static import StaticTokenVerifier

        tokens = json.loads(Path(args.static_tokens).read_text(encoding="utf-8"))
        verifier = StaticTokenVerifier(
            {t: Identity(**v) for t, v in tokens.items()})

    uvicorn.run(create_app(engine, verifier), host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kura",
                                     description="蔵 (aiseed workspace)")
    sub = parser.add_subparsers(dest="command", required=True)

    env = os.environ.get

    p_init = sub.add_parser("init", help="データルートと最初の管理者を初期化")
    p_init.add_argument("--data-root", default=env("KURA_DATA_ROOT", "/srv/workspace"))
    p_init.add_argument("--admin-user-id",
                        help="PB を使わず、既存の利用者 ID で初期化")
    p_init.add_argument("--pb-url", help="PocketBase の URL（最初の利用者を作る）")
    p_init.add_argument("--pb-superuser-email")
    p_init.add_argument("--pb-superuser-password")
    p_init.add_argument("--email", help="最初の管理者のメール")
    p_init.add_argument("--password", help="省略時は生成して表示")
    p_init.add_argument("--name", help="表示名")
    p_init.set_defaults(func=cmd_init)

    p_serve = sub.add_parser("serve", help="API サーバーを起動")
    p_serve.add_argument("--data-root", default=env("KURA_DATA_ROOT", "/srv/workspace"))
    p_serve.add_argument("--host", default=env("KURA_HOST", "127.0.0.1"))
    p_serve.add_argument("--port", type=int, default=int(env("KURA_PORT", "8400")))
    p_serve.add_argument("--auth", choices=["pocketbase", "static"],
                         default=env("KURA_AUTH", "pocketbase"))
    p_serve.add_argument("--pb-url", default=env("KURA_PB_URL", "http://127.0.0.1:8090"))
    p_serve.add_argument("--token-ttl", type=float,
                         default=float(env("KURA_TOKEN_TTL", "60")))
    p_serve.add_argument("--static-tokens", default=env("KURA_STATIC_TOKENS"),
                         help="開発用：トークン → 利用者の JSON ファイル")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

# 蔵（aiseed workspace）

Microsoft 365 / Google Workspace の代わりを、自前で持つ。握られず、現場で動かす。

設計は [docs/aiseed-workspace-spec.md](docs/aiseed-workspace-spec.md)（v3.1）を参照。
権限の正はディレクトリの xattr、グループはファイル、認証は PocketBase（差し替え式）、
連携の口は FastAPI。権限のためのデータベースは持たない。

## 構成

```
src/kura/
  core/      コアエンジン（権限判定・ファイル操作。口が何であれ判定はここを通る）
    atomic.py   flock（別ロックファイル）+ atomic rename
    paths.py    パス安全（.. 拒否・シンボリックリンク拒否・NFC 正規化・予約語）
    perms.py    xattr（user.ws.perm / user.ws.creator）の読み書きと判定
    groups.py   ルート直下の groups ファイル（グループ定義・所属）
    links.py    共有リンク（トークンはハッシュ保存・期限・取り消し）
    engine.py   操作と要求ビットの対応（traversal は当該ディレクトリのみで判定）
  auth/      トークン検証（差し替え式）
    base.py        型：トークン → {user_id, display_name, email} | 失敗
    pocketbase.py  標準実装：introspection + 短 TTL キャッシュ
    static.py      固定トークン（テスト・開発用）
  api/       連携の口（FastAPI）
  cli.py     kura init（ブートストラップ）/ kura serve
```

## ブートストラップ（spec 6 章）

```sh
# 1. インストール（OS root）：サービスアカウントとデータルートを作る
useradd -r workspace
mkdir -m 700 /srv/workspace && chown workspace:workspace /srv/workspace

# 2. PocketBase スーパーユーザー（PB 自身の CLI を借りる）
./pocketbase superuser upsert admin@example.jp <パスワード>

# 3. 初期化（CLI 一発）：最初の管理者・groups・ルート xattr
kura init --pb-url http://127.0.0.1:8090 \
  --pb-superuser-email admin@example.jp --pb-superuser-password <パスワード> \
  --email 管理者のメール

# 4. 起動
kura serve --data-root /srv/workspace --pb-url http://127.0.0.1:8090
```

## 開発

```sh
pip install -e '.[dev]'
pytest

# PocketBase なしで動かす（固定トークン）
echo '{"tok1": {"user_id": "u_demo", "display_name": "デモ", "email": "d@example.jp"}}' > /tmp/tokens.json
kura init --data-root /tmp/kura --admin-user-id u_demo
kura serve --data-root /tmp/kura --auth static --static-tokens /tmp/tokens.json
curl -H 'Authorization: Bearer tok1' http://127.0.0.1:8400/api/me
```

## 実装の現在地（spec 8 章の実装順序）

- [x] 1. 認証 — PocketBase 0.36 実機で結合確認済み（kura init の PB 連携、
      auth-with-password → auth-refresh introspection → API フルスタック）
- [x] 2. ファイルと権限（xattr・原子性・パス安全・共有リンク）。
      実機検証は `kura fscheck` で実行（ext4 既定で 212 グループ/ディレクトリ、
      超過は原子的、tar --xattrs 保全 OK——spec 7 章に記録）
- [x] 3. API の口（トークン検証は差し替え式、標準は PocketBase introspection + キャッシュ）
- [ ] 4. ファイル共有のフロント（Flet 0.85 系・宣言的スタイル）
- [ ] 5. ONLYOFFICE Docs 連携（JWT・保存コールバック・document key）
- [x] 6. カレンダーのバックエンド（イベント＝.ics は既存のファイル API で読み書き、
      購読フィード `/feed/{token}.ics` は共有リンクに畳んだ認可）。予定の UI は 4. と一緒に

バックアップは `scripts/backup.sh`（xattr を落とさない tar、PB データ込み）。

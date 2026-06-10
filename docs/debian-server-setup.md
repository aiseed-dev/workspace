# Debian サーバー構築マニュアル — 蔵（aiseed workspace）の台

Ubuntu 24.04 のサーバーを Debian にクリーンインストールし、蔵の台として立てる手順。
静的サイト（aiseed.dev / timej.net）は先に Cloudflare Pages へ移してあること
（docs/cloudflare-pages-migration.md）。サイトが切り離れていれば、この作業に
ダウンタイムの心配はない。

## 決定済みの構成

- **接続は直接 HTTPS**。Cloudflare は DNS-only（灰色雲）で名前解決だけ。
  TLS はサーバー側で終端（Let's Encrypt 自動）——**データ経路に第三者を入れない**。
  根拠：グローバル IPv4 がある・招待で利用者を増やす（VPN 必須にできない）・
  Tunnel はエッジで TLS 終端＝中身を見られる上に無料プランは 100MB/リクエスト上限
- OS は **Debian 安定版**、ファイルシステムは**標準の ext4 のまま**（spec 7 章）
- リバースプロキシは **Caddy**（証明書の取得・更新が自動で設定 2 行。最小依存）
- PocketBase は **localhost のみ**で待ち受け、外に出さない（ログインも検証も
  サーバー側 Python が叩くため、外部公開が不要）
- 公開するポートは **80/443（Caddy）と SSH だけ**

```
インターネット ──443──▶ Caddy（TLS 終端）
                          ├─ /api/* /share/* /feed/* ──▶ kura serve   (127.0.0.1:8400)
                          └─ それ以外（画面）       ──▶ kura front   (127.0.0.1:8500)
                                                              │ どちらも localhost で
                                                              ▼
                                                        PocketBase (127.0.0.1:8090)
データ：/srv/workspace（共有ツリー・xattr が権限の正）、/srv/pocketbase（認証 DB）
```

---

## 1. インストール前に（旧サーバーで）

```sh
# 残っているデータの退避（サイトは Pages 移行済みのはず。それ以外の自分のデータを確認）
ls /var/www /home /etc/nginx/sites-enabled
# 必要なものを手元か別ディスクに rsync しておく
```

## 2. Debian のインストール

- Debian 安定版の netinst イメージで通常インストール
- パーティションは**ガイド付き・ext4 のまま**でよい（特別な指定は不要——spec 7 章。
  /srv が同一パーティションに含まれていればよい）
- ソフトウェア選択は「SSH サーバー」と「標準システムユーティリティ」だけ。デスクトップは入れない
- インストール後、SSH は鍵認証にして パスワード認証を切る：
  `/etc/ssh/sshd_config` → `PasswordAuthentication no`

## 3. 基礎固め（OS root で）

```sh
apt update && apt install -y caddy python3-venv rsync curl unzip ufw unattended-upgrades

# ファイアウォール：SSH と HTTP/HTTPS だけ
ufw allow OpenSSH && ufw allow 80,443/tcp && ufw enable

# 自動セキュリティ更新
dpkg-reconfigure -plow unattended-upgrades
```

## 4. サービスアカウントとデータ領域（spec 6 章の三層：OS root の仕事はここまで）

```sh
useradd -r -m -d /opt/kura -s /usr/sbin/nologin workspace
mkdir -m 700 /srv/workspace /srv/pocketbase /srv/backups
chown workspace:workspace /srv/workspace /srv/pocketbase /srv/backups
```

## 5. PocketBase と kura の配置

```sh
# PocketBase（バイナリ一つ。バージョンは動作確認済みのものに固定）
cd /opt/kura
curl -sLO https://github.com/pocketbase/pocketbase/releases/download/v0.36.0/pocketbase_0.36.0_linux_amd64.zip
unzip pocketbase_0.36.0_linux_amd64.zip pocketbase && rm pocketbase_0.36.0_linux_amd64.zip

# kura（リポジトリから。配布物を作るまでは git clone で）
python3 -m venv venv
./venv/bin/pip install "kura[front] @ git+https://github.com/aiseed-dev/workspace.git"
chown -R workspace:workspace /opt/kura
```

## 6. systemd ユニット（三つ）

`/etc/systemd/system/pocketbase.service`：

```ini
[Unit]
Description=PocketBase (kura auth)
After=network.target

[Service]
User=workspace
ExecStart=/opt/kura/pocketbase serve --dir /srv/pocketbase --http 127.0.0.1:8090
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/kura-api.service`：

```ini
[Unit]
Description=kura API
After=pocketbase.service

[Service]
User=workspace
ExecStart=/opt/kura/venv/bin/kura serve --data-root /srv/workspace \
  --pb-url http://127.0.0.1:8090 --host 127.0.0.1 --port 8400
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/kura-front.service`：

```ini
[Unit]
Description=kura front (Flet)
After=pocketbase.service

[Service]
User=workspace
ExecStart=/opt/kura/venv/bin/kura front --data-root /srv/workspace \
  --pb-url http://127.0.0.1:8090 --host 127.0.0.1 --port 8500
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```sh
systemctl daemon-reload
systemctl enable --now pocketbase kura-api kura-front
```

## 7. ブートストラップ（CLI 一発、spec 6 章）

```sh
# PB スーパーユーザー（運用資格。Workspace の利用者ではない）
sudo -u workspace /opt/kura/pocketbase superuser upsert 運用者@example.jp '強いパスワード' --dir /srv/pocketbase

# 最初の Workspace 管理者 + groups + ルート xattr
sudo -u workspace /opt/kura/venv/bin/kura init \
  --data-root /srv/workspace --pb-url http://127.0.0.1:8090 \
  --pb-superuser-email 運用者@example.jp --pb-superuser-password '強いパスワード' \
  --email 管理者のメール --name '表示名'

# ファイルシステムの実機検証（xattr 上限・バックアップ保全）
sudo -u workspace /opt/kura/venv/bin/kura fscheck --data-root /srv/workspace
```

## 8. DNS と Caddy（ここで外に出る）

Cloudflare ダッシュボード → aiseed.dev の DNS → レコード追加：

- Type `A`、Name `kura`、IPv4 = サーバーのグローバル IP、**Proxy status は DNS only（灰色雲）**
  ——オレンジ雲にすると Cloudflare が TLS を終端して中身を見られる。ここは必ず灰色

`/etc/caddy/Caddyfile`：

```
kura.aiseed.dev {
    handle /api/* {
        reverse_proxy 127.0.0.1:8400
    }
    handle /share/* {
        reverse_proxy 127.0.0.1:8400
    }
    handle /feed/* {
        reverse_proxy 127.0.0.1:8400
    }
    handle {
        reverse_proxy 127.0.0.1:8500
    }
}
```

```sh
systemctl reload caddy
# 証明書は Caddy が Let's Encrypt から自動取得・自動更新する。何もしなくてよい
curl -sI https://kura.aiseed.dev | head -3
```

ルーターで 80/443 をこのサーバーへポートフォワードしておくこと
（80 は証明書の取得・更新と HTTPS への転送に使う）。

## 9. バックアップ（毎日）

```sh
# リポジトリの scripts/backup.sh を /opt/kura/backup.sh に置き、cron へ
sudo -u workspace crontab -e
# 3:00 に毎日。xattr を落とさない tar + PB データ
0 3 * * * /opt/kura/backup.sh /srv/workspace /srv/pocketbase /srv/backups
```

/srv/backups は**別の場所にも**写すこと（外付けディスクや他拠点へ rsync。
xattr はアーカイブ内に保全済みなので、tar.gz の転送は普通の rsync でよい）。

## 10. 利用者を増やすとき

- 招待：管理者が PB に利用者を作り（将来は招待メール機能）、グループに入れて
  ディレクトリに権限を付けるだけ。**経路は HTTPS なので相手に何も入れさせない**
- 規模の限界はこの一台の回線（特に上り帯域）と資源。spec の思想は一台のスケールアップ
  ではなく**現場分散**——組織や用途が分かれたら台を分けて、招待・共有リンクでまたぐ
- DocSpace / ONLYOFFICE Docs を同じ台に載せる場合は別サブドメイン
  （docspace.aiseed.dev 等）を同様に A レコード + Caddy で足す。手順は別途

## 確認リスト

- [ ] `https://kura.aiseed.dev` でログイン画面が出て、管理者でログインできる
- [ ] `kura fscheck` が全項目 OK
- [ ] `ufw status` が 22/80/443 のみ
- [ ] PB（8090）・API（8400）・front（8500）が外から直接見えない（`nmap` か `curl 公開IP:8090` で確認）
- [ ] バックアップが /srv/backups にでき、tar の中に xattr が入っている
      （`tar --xattrs -tvf` か、復元テストで `getfattr -d`）
- [ ] 再起動して全サービスが自動で上がる（`systemctl reboot` 後に確認）

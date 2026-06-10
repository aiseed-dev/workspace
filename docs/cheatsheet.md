# チートシート — 手が打つやつだけ、値は埋めてある

説明なし。説明が要るときは [runbook.md](runbook.md) へ。

## 毎度

```sh
# サイト更新（それぞれのリポジトリで）
python3 deploy.py                    # aiseed.dev / timej.net 共通

# 蔵の開発
pytest                               # テスト一式
python3 -m kura.cli serve --data-root /tmp/kura --auth static --static-tokens /tmp/tokens.json
```

## サーバー（蔵の台）

```sh
systemctl status pocketbase kura-api kura-front     # 状態
journalctl -u kura-api -e                           # ログ（直近）
systemctl restart kura-api kura-front               # 再起動
sudo -u workspace /opt/kura/venv/bin/kura fscheck --data-root /srv/workspace
```

## 滅多にないが、迷ったら困るやつ

```sh
# バックアップから戻す（xattr ごと）
tar --xattrs --xattrs-include='user.*' -xzf workspace-日付.tar.gz

# 手動バックアップ
/opt/kura/backup.sh /srv/workspace /srv/pocketbase /srv/backups

# PB スーパーユーザーのパスワード再設定
sudo -u workspace /opt/kura/pocketbase superuser upsert メール 新パスワード --dir /srv/pocketbase

# 権限の中身を直接見る（デバッグ）
getfattr -n user.ws.perm -d /srv/workspace/対象ディレクトリ
cat /srv/workspace/groups
```

## 場所と値

| 何 | どこ |
|---|---|
| Cloudflare トークン | `~/.config/cloudflare/pages.env`（chmod 600） |
| Pages プロジェクト名 | `aiseed-dev` / `timej-net` |
| 蔵の URL | `https://kura.aiseed.dev` |
| データの正 | `/srv/workspace`（xattr が権限）・`/srv/pocketbase`（認証） |
| バックアップ | `/srv/backups`（毎日 3:00 cron） |
| DNS の決まり | 蔵の A レコードは**必ず灰色雲（DNS only）**。MX も灰色 |
| ポートの決まり | 公開は 80/443 のみ。22 は LAN のみ・転送しない。25 は出も止めてある |

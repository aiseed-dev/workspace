# 作業台帳（runbook）— 運用の書き場所はここ一つ

「どうやるんだったか」と思ったら、まずこの表。詳細は右端のリンク先にある。
最速で引くには `python3 scripts/daicho.py`——この台帳を直接読むランチャー
（打って絞って Enter でコピー。写しは作らない、正はこのファイル）。
**道具や手順が増えたら、説明を増やす前にこの表へ行を足すこと。**

## 日常の作業

| やりたいこと | どこで | コマンド | 詳細 |
|---|---|---|---|
| サイトを更新する（aiseed.dev / timej.net） | 手元の PC | サイトのリポジトリで `python3 deploy.py` | [cloudflare-pages-migration.md](cloudflare-pages-migration.md) |
| 蔵を使う（ファイル・共有・予定） | ブラウザ | `https://kura.aiseed.dev` | — |
| 利用者・グループ・権限を変える | ブラウザ | 蔵のフロント（管理(a) を持つ人） | [spec 5 章](aiseed-workspace-spec.md) |
| 共有リンク / カレンダー購読 URL を出す | ブラウザ | 蔵のフロント | [spec 4.6 章](aiseed-workspace-spec.md) |

## サーバーの運用（蔵の台）

| やりたいこと | どこで | コマンド | 詳細 |
|---|---|---|---|
| 新しい台を立てる | サーバー | マニュアル通り（インストール → `kura init`） | [debian-server-setup.md](debian-server-setup.md) |
| サービスの状態を見る | サーバー | `systemctl status pocketbase kura-api kura-front` | 同 6 章 |
| ログを見る（直近） | サーバー | `journalctl -u kura-api -e` | — |
| サービスを再起動する | サーバー | `systemctl restart kura-api kura-front` | — |
| バックアップ（自動・毎日 3:00） | サーバー | 手動は `/opt/kura/backup.sh /srv/workspace /srv/pocketbase /srv/backups` | 同 9 章 |
| バックアップから戻す（xattr ごと） | サーバー | `tar --xattrs --xattrs-include='user.*' -xzf workspace-日付.tar.gz` ※`--xattrs` を忘れると権限が全部消える | [scripts/backup.sh](../scripts/backup.sh) |
| ファイルシステムの検証 | サーバー | `kura fscheck --data-root /srv/workspace` | [spec 7 章](aiseed-workspace-spec.md) |
| PB スーパーユーザーの再設定 | サーバー | `sudo -u workspace /opt/kura/pocketbase superuser upsert メール 新パスワード --dir /srv/pocketbase` | — |
| 権限を直接見る（デバッグ） | サーバー | `getfattr -n user.ws.perm -d /srv/workspace/対象` | [spec 7 章](aiseed-workspace-spec.md) |
| グループ定義を直接見る | サーバー | `cat /srv/workspace/groups` | — |

## 開発

| やりたいこと | どこで | コマンド | 詳細 |
|---|---|---|---|
| テストを回す | 手元 | `pytest` | [README](../README.md) |
| PocketBase なしで動かす | 手元 | `kura serve --data-root /tmp/kura --auth static --static-tokens /tmp/tokens.json` | [README](../README.md) |
| Python プログラム一般の動かし方 | — | venv の三行の型 | [python-howto.md](python-howto.md) |
| 台帳ランチャー | 手元 | `python3 scripts/daicho.py`（この runbook を直接読む。写しの台帳は持たない） | [scripts/daicho.py](../scripts/daicho.py) |

## 場所と値

| 何 | 値 |
|---|---|
| Cloudflare トークン | `~/.config/cloudflare/pages.env`（chmod 600） |
| Pages プロジェクト名 | `aiseed-dev` / `timej-net` |
| 蔵の URL | `https://kura.aiseed.dev` |
| データの正 | `/srv/workspace`（xattr が権限）・`/srv/pocketbase`（認証） |
| バックアップ置き場 | `/srv/backups`（毎日 3:00 cron） |

## 決めごと（探さなくていいようにする規約）

- **入口の名前は固定**：どのサイトリポジトリも、デプロイの入口は常に `deploy.py`。迷ったら `python3 deploy.py`
- **置き場所は固定**：手順書は `docs/`、道具は `scripts/`、秘密はホームの `~/.config/`（chmod 600。リポジトリ・公開ディレクトリに置かない）
- **DNS とポート**：蔵の A レコード・MX は必ず灰色雲（DNS only）。公開ポートは 80/443 のみ、22 は LAN のみ・転送しない、25 は出る方も止めてある
- **計算の置き場所は三種類**：口（サーバー常駐）/ 働き手（サーバーのタイマー起動）/ 手元の道具（使うときだけ）。新しい仕組みを作るときは、まずどれかを決める
- **API を挟むのは境界を越えるときだけ**（別マシン・別人・別システム）。同じマシンで自分のデータを触る道具は直接アクセスでよい。ただし他人のデータの権限判定だけは常にコアエンジンを通す
- **設計の理由を探すとき**は [aiseed-workspace-spec.md](aiseed-workspace-spec.md)。「なぜこうなっているか」は全部そこにある

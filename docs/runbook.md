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
| 棚卸し（何を管理しているかの一覧） | 手元/サーバー | `python3 scripts/tanaoroshi.py`（現実を走査して生成。手で書く台帳は持たない） | [scripts/tanaoroshi.py](../scripts/tanaoroshi.py) |

## 定期の手作業（蔵のカレンダーに繰り返し予定として登録する）

自動処理（cron・timer）は棚卸しが走査で拾うが、人の手の定期作業は
やり忘れても痕跡が残らない。だからここに書き、繰り返し予定で思い出させる。

| いつ | 何 | やり方 |
|---|---|---|
| 月一 | バックアップが実際にできているか見る | `ls -lh /srv/backups` で日付とサイズを確認 |
| 月一 | ディスク残量を見る | `df -h /srv` |
| 月一 | 別の場所への複製が動いているか見る | 複製先の日付を確認 |
| 半年 | **復元テスト**（テストしていないバックアップはバックアップではない） | 別ディレクトリに `tar --xattrs --xattrs-include='user.*' -xzf` で展開し、`getfattr -d` で xattr を確認 |
| 半年 | 依存の版上げ（Flet・PocketBase・pip）を検討 | 移行ガイドを読んでから。配布物の固定版も更新 |
| 年一 | Cloudflare トークンの棚卸し・作り直し | ダッシュボード → API Tokens |
| 年一 | ドメイン更新と支払い手段の確認 | レジストラの自動更新と期限 |
| 年一 | 送信 IP がブロックリストに載っていないか | mxtoolbox 等で固定 IP を検索 |
| 年一 | 棚卸しを回して全体を見る | `python3 scripts/tanaoroshi.py` |

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
- **説明はモノに貼る**：リポジトリは README の一行目、systemd は `Description=`、cron はコメント行。一覧（棚卸し）は走査で生成する——手で書いた管理台帳は腐る
- **走査できるのは痕跡のあるものだけ**：人の手の定期作業は痕跡を残さない唯一の例外なので、「定期の手作業」の表に書き、蔵のカレンダーの繰り返し予定で思い出させる
- **API を挟むのは境界を越えるときだけ**（別マシン・別人・別システム）。同じマシンで自分のデータを触る道具は直接アクセスでよい。ただし他人のデータの権限判定だけは常にコアエンジンを通す
- **設計の理由を探すとき**は [aiseed-workspace-spec.md](aiseed-workspace-spec.md)。「なぜこうなっているか」は全部そこにある

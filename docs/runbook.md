# 作業台帳（runbook）— やり方を探す場所はここ一枚

「どうやるんだったか」と思ったら、まずこの表。詳細は右端のリンク先にある。
**道具や手順が増えたら、説明を増やす前にこの表へ行を足すこと。**

## 日常の作業

| やりたいこと | どこで | コマンド | 詳細 |
|---|---|---|---|
| サイトを更新する（aiseed.dev / timej.net） | 手元の PC | サイトのリポジトリで `python3 deploy.py` | [cloudflare-pages-migration.md](cloudflare-pages-migration.md) |
| 蔵を使う（ファイル・共有・予定） | ブラウザ | https://kura.aiseed.dev | — |
| 利用者・グループ・権限を変える | ブラウザ | 蔵のフロント（管理(a) を持つ人） | [spec 5 章](aiseed-workspace-spec.md) |
| 共有リンク / カレンダー購読 URL を出す | ブラウザ | 蔵のフロント | [spec 4.6 章](aiseed-workspace-spec.md) |

## サーバーの運用（蔵の台）

| やりたいこと | どこで | コマンド | 詳細 |
|---|---|---|---|
| 新しい台を立てる | サーバー | マニュアル通り（インストール → `kura init`） | [debian-server-setup.md](debian-server-setup.md) |
| サービスの状態を見る | サーバー | `systemctl status pocketbase kura-api kura-front` | 同上 6 章 |
| バックアップ（自動・毎日 3:00） | サーバー | cron 済み。手動は `/opt/kura/backup.sh データ root PBデータ 保存先` | 同上 9 章 |
| バックアップから戻す | サーバー | `tar --xattrs --xattrs-include='user.*' -xzf workspace-*.tar.gz` | [scripts/backup.sh](../scripts/backup.sh) |
| ファイルシステムの検証 | サーバー | `kura fscheck --data-root /srv/workspace` | [spec 7 章](aiseed-workspace-spec.md) |

## 開発

| やりたいこと | どこで | コマンド | 詳細 |
|---|---|---|---|
| テストを回す | 手元 | `pytest` | [README](../README.md) |
| PocketBase なしで動かす | 手元 | `kura serve --auth static --static-tokens トークン.json` | [README](../README.md) |
| Python プログラム一般の動かし方 | — | venv の三行の型 | [python-howto.md](python-howto.md) |

## 決めごと（探さなくていいようにする規約）

- **入口の名前は固定**：どのサイトリポジトリも、デプロイの入口は常に `deploy.py`。迷ったら `python3 deploy.py`
- **置き場所は固定**：手順書は `docs/`、道具は `scripts/`、秘密はホームの `~/.config/`（chmod 600。リポジトリ・公開ディレクトリに置かない）
- **計算の置き場所は三種類**：口（サーバー常駐）/ 働き手（サーバーのタイマー起動）/ 手元の道具（使うときだけ）。新しい仕組みを作るときは、まずどれかを決める
- **設計の理由を探すとき**は [aiseed-workspace-spec.md](aiseed-workspace-spec.md)。「なぜこうなっているか」は全部そこにある

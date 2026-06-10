# Cloudflare Pages 移行マニュアル — aiseed.dev / timej.net

静的サイト 2 つを、自宅サーバーから Cloudflare Pages へ移す手順。

前提：

- 両ドメインのネームサーバーは既に Cloudflare
- HTML は **Python のスクリプトで生成**している（生成物は .gitignore 済み）
- デプロイは**直接アップロード**。ツールは npm（wrangler）を使わず、
  **Python スクリプト**（このリポジトリの `scripts/cloudflare_pages_deploy.py`）で行う

目的：サイトをサーバーから切り離し、サーバーを Debian にクリーンインストールして
蔵（aiseed workspace）/ DocSpace 専用にする。サイトのダウンタイムはゼロにする。

所要時間の目安：**準備〜切り替えまで 1 サイトあたり 30 分程度**。
DNS の切り替え自体は数分で済む（ネームサーバーが既に Cloudflare のため）。

> 注意：Cloudflare の管理画面の文言・配置は変わることがある（本書は 2026-06 時点）。

---

## 1. 準備（一度だけ）

npm は使わない。必要なのは Python と pip パッケージ二つ、それに API トークン：

```sh
pip install httpx blake3
```

API トークンの作成（ブラウザで一度だけ）：

1. Cloudflare ダッシュボード → 右上のプロフィール → **My Profile → API Tokens → Create Token**
2. テンプレート **「Cloudflare Pages を編集する（Edit Cloudflare Pages）」** を選んで作成
3. 表示されたトークンと、アカウント ID（ダッシュボードのドメイン概要ページ右側に表示）を控える

```sh
export CLOUDFLARE_API_TOKEN=控えたトークン
export CLOUDFLARE_ACCOUNT_ID=アカウントID
```

直接アップロードは .gitignore の影響を受けない（手元のディレクトリをそのまま上げる）ので、
生成 HTML は ignore のままでよい。**ただし生成スクリプトと素材（Python・テンプレート・
画像等の正本）は git に置いて守ること**——これが退路の担保になる。

> 注：`cloudflare_pages_deploy.py` は wrangler が内部で使っているのと同じ
> Direct Upload API（半公式）を Python で実装したもの。Cloudflare 側の変更で
> 動かなくなる可能性はゼロではない。そのときは wrangler（npm）か Git 連携に
> 退避できる——どちらも同じ Pages プロジェクトに対して使える。

## 2. プロジェクト作成と初回デプロイ

サイトごとに 1 プロジェクト。例として aiseed.dev：

```sh
cd aiseed.dev のソース
python3 build.py                # いつもの生成コマンド（実際の名前に読み替え）

python3 cloudflare_pages_deploy.py ./出力ディレクトリ --project aiseed-dev --create
```

終わると `https://aiseed-dev.pages.dev` のような確認用 URL が表示される。
timej.net も同様に（例：`--project timej-net`）。
二回目以降は変更のあったファイルだけが送られる（中身のハッシュで差分判定）。

## 3. 確認（DNS を触る前に）

`https://aiseed-dev.pages.dev` を開き、全ページ・リンク・画像・文字化けを確認する。
**この時点では本番 DNS は無変更**。旧サーバーも動いたまま。納得いくまでやり直せる。

## 4. カスタムドメインの割り当て（ここが切り替え）

Cloudflare ダッシュボード → Workers & Pages → プロジェクト →
**Custom domains** → **Set up a custom domain** → `aiseed.dev` を入力。

- ネームサーバーが既に Cloudflare なので、**DNS レコードは自動で書き換わる**
  （旧サーバー向けの A レコード → Pages 向け CNAME。確認画面が出る）
- 反映は実質数分。旧レコードがプロキシ（オレンジ雲）だったなら事実上瞬時。
  DNS-only（灰色雲）だった場合も、世界のキャッシュに残るのは旧 TTL（通常 300 秒）まで
- `www.aiseed.dev` も使っているなら www も Custom domains に追加
- `.dev` は HTTPS 必須だが、証明書は自動発行されるので何もしなくてよい
- timej.net も同様に繰り返す

切り替え確認：

```sh
dig aiseed.dev +short            # Cloudflare の IP に変わっている
curl -sI https://aiseed.dev | head -5
```

## 5. 片付け（当日でよい）

DNS がもう旧サーバーを指していないので、4 の確認が済んだら旧 nginx は当日止めてよい。
心配なら設定を消さず `systemctl stop nginx` に留めておく（戻す手段にはならないが気休めに）。
本当の戻し先は Pages のロールバック（Deployments から旧デプロイに一発）か、
旧 A レコードを手で戻すこと——どちらも数分で済む。

**これでサーバーとサイトが無関係になった。Debian クリーンインストールへ進める。**

## 6. 以後の更新

```sh
python3 build.py
python3 cloudflare_pages_deploy.py ./出力ディレクトリ --project aiseed-dev
```

二行で済む。サイトごとにシェルスクリプト（`deploy.sh`）にしておくと間違いがない：

```sh
#!/bin/sh
set -eu
python3 build.py
python3 cloudflare_pages_deploy.py ./出力ディレクトリ --project aiseed-dev
```

（API トークンを毎回 export したくなければ、`~/.profile` か direnv 等で環境変数を
設定しておく。トークンは Pages 編集権限しか持たないので、漏れたときの被害も
Pages の書き換えに限定される——とはいえ git にはコミットしないこと。）

## 退路

生成スクリプトと素材が git にある限り、Cloudflare をやめる日は
「生成して別のホスト（自前 nginx・GitHub Pages 等）に置き、DNS を向け直す」一手で済む。
保存形式（静的ファイル）と生成手段（自分の Python）がベンダー非依存であることが
退路を担保する——蔵の設計原則と同じ。

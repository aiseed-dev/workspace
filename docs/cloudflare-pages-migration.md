# Cloudflare Pages 移行マニュアル — aiseed.dev / timej.net

静的サイト 2 つを、自宅サーバーから Cloudflare Pages へ移す手順。
前提：両ドメインのネームサーバーは既に Cloudflare。サイトは静的（HTML/CSS/JS のみ）。

目的：サイトをサーバーから切り離し、サーバーを Debian にクリーンインストールして
蔵（aiseed workspace）/ DocSpace 専用にする。サイトのダウンタイムはゼロにする。

> 注意：Cloudflare の管理画面の文言・配置は変わることがある（本書は 2026-06 時点）。
> 新規作成の入口が「Workers & Pages」に統合されているが、静的サイトなら Pages で足りる。

---

## 0. 方式を選ぶ

| | A. Git 連携（推奨） | B. 直接アップロード（wrangler） |
|---|---|---|
| デプロイ | git push だけで自動 | `wrangler pages deploy` を手で実行 |
| 必要なもの | GitHub（等）のリポジトリ | Node.js + wrangler CLI |
| 履歴・ロールバック | コミット履歴 = デプロイ履歴。管理画面から旧版に戻せる | デプロイ履歴は残るがソースの正本は手元だけ |
| .gitignore の影響 | **受ける**（下記 0.1） | 受けない（手元のファイルをそのまま上げる） |

**推奨は A**。ソースの正本が git に残ること自体が退路（任意のホストへ移れる）になる。

### 0.1 「html を .gitignore に入れている」問題

Git 連携はリポジトリの中身を配信する。HTML が ignore されていれば**サイトは空になる**。
自分のサイトがどれに当たるかで対処を選ぶ：

| サイトの作り | 対処 |
|---|---|
| HTML が手書きの正本 | `.gitignore` から `*.html` を外してコミットする。正本が git 管理外なのはバックアップとしても危ういので、この機会に入れる |
| HTML を生成している（SSG・スクリプト） | ソースだけコミットし、Pages のビルドコマンドに生成コマンドを設定（手順 A-3）。生成物は ignore のままでよい |
| どうしても git に入れたくない | 方式 B（直接アップロード）にする |

確認コマンド：

```sh
cd サイトのリポジトリ
git check-ignore -v index.html   # ignore の出どころを表示
git ls-files | grep -c '\.html$' # 追跡中の html の数（0 なら入っていない）
```

外す場合：

```sh
# .gitignore から該当行（*.html など）を削除してから
git add -A && git commit -m "HTML をリポジトリに含める（Pages 移行のため）"
```

---

## 1. 準備：サイトをリポジトリにする（方式 A）

サイトごとに 1 リポジトリ（例：`aiseed-dev/aiseed.dev-site`、`aiseed-dev/timej.net-site`）。

```sh
# 旧サーバーで。公開ディレクトリを手元に取る（場所は nginx の root を確認）
rsync -a サーバー:/var/www/aiseed.dev/ ./aiseed.dev-site/
cd aiseed.dev-site
git init && git add -A && git commit -m "現行サイトを取り込み"
git remote add origin git@github.com:aiseed-dev/aiseed.dev-site.git
git push -u origin main
```

公開ディレクトリがリポジトリ直下でない場合（例：`public/` 配下）は、その構成のままでよい
（手順 A-3 で出力ディレクトリに `public` を指定する）。

## 2. Pages プロジェクトを作る（方式 A）

Cloudflare ダッシュボード → **Workers & Pages** → **Create** → **Pages** →
**Connect to Git** → GitHub を認可 → リポジトリを選択。

## 3. ビルド設定（A-3）

| 項目 | 純静的（HTML をコミット） | 生成あり（例） |
|---|---|---|
| Framework preset | None | 使う SSG を選ぶ（なければ None） |
| Build command | （空欄） | `python3 build.py` や `hugo` 等 |
| Build output directory | `/`（リポジトリ直下）または `public` | 生成物の出力先 |

Save and Deploy → 数十秒で `プロジェクト名.pages.dev` の URL が出る。

## 4. 確認（DNS を触る前に）

`https://プロジェクト名.pages.dev` を開き、全ページ・リンク・画像を確認する。
**この時点では本番 DNS は無変更**。旧サーバーも動いたまま。

## 5. カスタムドメインの割り当てと DNS

Pages プロジェクト → **Custom domains** → **Set up a custom domain** → `aiseed.dev` を入力。

- ネームサーバーが既に Cloudflare なので、**必要な DNS レコード（CNAME）は自動で作成・
  置き換えされる**。既存の A レコード（旧サーバーの IP）は Pages 用 CNAME に置き換わる
  （確認画面が出る）。apex ドメインも CNAME flattening で問題ない
- `www.aiseed.dev` も使っているなら、www も Custom domains に追加（apex への
  リダイレクトは Bulk Redirects か、www を追加して同じ内容を配信でもよい）
- timej.net も同様に繰り返す

反映は通常数分。`.dev` は HTTPS 必須だが、Pages は証明書を自動発行するので何もしなくてよい。

## 6. 切り替え後の確認と片付け

```sh
# 新しい配信元の確認（cloudflare が返るはず）
curl -sI https://aiseed.dev | grep -i server
dig aiseed.dev +short   # Cloudflare の IP（プロキシ）に変わっている
```

- 数日問題なければ、旧サーバーの nginx のサイト設定を止める
- **これでサーバーとサイトが無関係になった。Debian クリーンインストールへ進める**

## 7. 以後の更新

- 方式 A：リポジトリを直して `git push` → 自動デプロイ（main 以外のブランチは
  プレビュー URL が出るので、確認してからマージできる）
- ロールバック：Pages の Deployments から旧デプロイを「Rollback」一発

## 付録：方式 B（直接アップロード）

```sh
npm install -g wrangler        # 初回のみ
wrangler login                 # ブラウザで認可
wrangler pages project create aiseed-dev-site
wrangler pages deploy ./公開ディレクトリ --project-name aiseed-dev-site
```

以後の更新も `wrangler pages deploy` を打つだけ。カスタムドメインは手順 5 と同じ。
.gitignore の影響は受けないが、ソースの正本と履歴は自分で守ること。

## 退路

ソース（または生成前の正本）が git にある限り、Cloudflare をやめる日は
「同じファイルを別のホスト（自前 nginx・GitHub Pages 等）に置き、DNS を向け直す」一手で済む。
保存形式（静的ファイル）がベンダー非依存であることが退路を担保する——蔵の設計原則と同じ。

# Python のプログラムの動かし方（5 分・これだけ）

配布物のスクリプト（deploy.py など）は環境を自動で作るので、この知識がなくても動く。
これは「自動でやっていることの中身」を知りたい人のための一枚。
一度覚えれば、世の中のあらゆる Python プログラムで通用する。

## つまずきは三つしかない

| 症状 | 意味 |
|---|---|
| `python3: command not found` | Python が入っていない → `apt install python3 python3-venv` |
| `ModuleNotFoundError: No module named 'xxx'` | プログラムが使うライブラリが、いま使っている環境に入っていない |
| `pip install` が `externally-managed-environment` で拒否される | OS の Python に直接ライブラリを入れることを、いまの Debian/Ubuntu は禁止している（OS を壊さないため）。**仕様であってエラーではない** |

後ろ二つの答えが「仮想環境（venv）」。

## 仕組みは一つだけ

ライブラリは「環境」に入る。OS の環境は OS のものだから触らない。
**プログラムごとに、専用の小さな環境（venv）を作って、そこに入れる。** それだけ。

## 型は三行

プログラムのあるディレクトリで：

```sh
python3 -m venv .venv                  # 1. 環境を作る（.venv という名前のディレクトリができる）
.venv/bin/pip install ライブラリ名      # 2. その環境にライブラリを入れる
.venv/bin/python プログラム.py          # 3. その環境の Python で動かす
```

この三行が全てで、どんな Python プログラムでもこの型で動く。
README に「requirements.txt」があるなら 2 行目を
`.venv/bin/pip install -r requirements.txt` にするだけ。

## 知っておくと混乱が消える三つのこと

- **activate は要らない**。入門記事は `source .venv/bin/activate` を教えるが、
  あれは「以後の `python` を .venv のものに差し替える」スイッチで、いまどの環境に
  いるのか見えなくなるのが混乱のもと。`.venv/bin/python` とパスで呼べば、
  どの環境で動いているか常に明示的で、事故が起きない
- **.venv は使い捨て**。壊れたら消して三行をやり直せばいい。大事なものは何も入っていない
  （大事なのはプログラムと requirements の方）。同じ理由で **git に入れない**（.gitignore へ）
- **環境はプログラムごと**。プログラム A の .venv にライブラリを足しても B には影響しない。
  「環境を分ける」とはそういう意味

これだけ知っていれば、deploy.py が初回にやっている「自動準備」も
ただこの三行を代行しているだけだと分かる。

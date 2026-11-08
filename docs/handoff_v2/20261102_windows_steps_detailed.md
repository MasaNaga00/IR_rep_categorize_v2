# Windows 側の作業手順(詳細版・担当者向け)

- 作成日: 2026-11-02
- 読み手: Windows PC(実データ環境)で作業する担当者
- GPT 向けのルールと要点は `20261102_windows_handoff.md`。この文書は、同じ流れを**手順ごとに、何をして、何を確認するか**まで詳しく書いたもの。
- 会社PCの GPT はチャットだけで使う(ローカルのファイルの読み書きと、コマンドの実行はできない)。コマンドの実行とファイルの変更は担当者が行い、GPT にはファイルやコマンドの表示をアップロード(貼り付け)して相談する(2026-11-06 改訂)。
- コマンドの例は**コマンドプロンプト(cmd)**で書く。PowerShell の場合の違いは、その都度書く。
- パスの例: コードのフォルダは `C:\work\IR_rep_categorize_v2`、ローカル作業フォルダは `C:\work\repclass_local`。実際の場所に読み替える。

---

## 全体の流れ

| # | 手順 | 主な作業者 | 目安 |
|---|---|---|---|
| 0 | Mac 側でコミットし、GitHub に送る | 担当者(Mac) | 最初だけ |
| 1 | コードをダウンロードして展開する | 担当者 | 最初と、更新のたび |
| 2 | Python の仮想環境を作り、ライブラリを入れる | 担当者 | 最初だけ |
| 3 | テストを実行する | 担当者 | 最初と、更新のたび |
| 4 | ローカル作業フォルダを作る | 担当者 | 最初だけ |
| 5 | Dify ワークフローを作り、API キーを設定する | 担当者 | 最初だけ |
| 6 | 架空データで通しの確認をする | 担当者 | 最初と、プロンプトを変えたとき |
| 7 | 実データを少量で実行する | 担当者 | |
| 8 | 過去の分類結果で精度を評価する | 担当者(不一致の原因は GPT に相談してよい) | |
| 9 | プロンプト・YAML を調整する(7〜9 を繰り返す) | 担当者(変更案は GPT に相談) | 精度に納得できるまで |
| 10 | 全件を実行し、Tableau に取り込む | 担当者 | |
| 11 | 気づいた点を Mac 側に伝える | 担当者 | 随時 |

---

## 手順0: Mac 側で GitHub に登録する(Mac で行う)

Windows 側は GitHub からダウンロードするので、先に Mac 側のリポジトリを GitHub に送る。

**初回(新しいリポジトリを作る)**
1. GitHub で新しいリポジトリを作る。
   - 名前: `IR_rep_categorize_v2`(任意)
   - 公開設定: **Private(非公開)**
   - README・.gitignore は追加しない(空のリポジトリにする)
2. Mac のターミナルで、次を実行する。
   ```
   cd ~/Documents/Python/claude/IR_rep_categorize_v2
   git init -b main
   git add -A
   git commit -m "v2: LLM方式の分類パイプライン一式"
   git remote add origin https://github.com/<ユーザ名>/IR_rep_categorize_v2.git
   git push -u origin main
   ```

**2回目以降(更新を送る)**
```
git add -A
git commit -m "<変更内容>"
git push
```

> 確認: GitHub のページで `src/repclass/` と `docs/handoff_v2/` が見えること。`__pycache__` が上がっていないこと。

---

## 手順1: コードをダウンロードして展開する

1. GitHub のリポジトリのページで「Code」→「Download ZIP」を押す。
2. ZIP を展開する。展開後のフォルダ名は `IR_rep_categorize_v2-main` のようになるので、`C:\work\IR_rep_categorize_v2` に名前を変える(どの名前でも動くが、以下はこの名前で説明する)。

> 確認: `C:\work\IR_rep_categorize_v2\repclass_cli.py` があること。

**更新するとき**: 新しい ZIP をダウンロードし、`C:\work\IR_rep_categorize_v2` を丸ごと置き換える。ローカル作業フォルダ(手順4)は別の場所にあるので、消えない。ただし、手順2の仮想環境(`.venv`)はコードのフォルダの中にあるため、置き換えると作り直しになる(手順2をやり直す)。

---

## 手順2: Python の仮想環境を作り、ライブラリを入れる

1. コマンドプロンプトを開き、コードのフォルダに移動する。
   ```
   cd /d C:\work\IR_rep_categorize_v2
   ```
2. Python 3.15 が使えることを確認する。
   ```
   py -0
   py -3.15 --version
   ```
   > 確認: `Python 3.15.x` と表示されること。
3. 仮想環境を作って有効にする。
   ```
   py -3.15 -m venv .venv
   .venv\Scripts\activate
   ```
   > 確認: 行の先頭に `(.venv)` と表示されること。
   - PowerShell の場合は `.venv\Scripts\Activate.ps1` を使う。「スクリプトの実行が無効」というエラーが出たら、先に `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` を実行する(このウィンドウの中だけ有効)。
4. ライブラリを入れる。
   ```
   python -m pip install -r requirements-dev.txt
   ```
   - 社内プロキシや証明書のエラーが出た場合の例:
     ```
     python -m pip install --proxy http://<プロキシ>:<ポート> --cert C:\path\to\corp-ca.pem -r requirements-dev.txt
     ```
   > 確認: `Successfully installed ... pyyaml ... requests ... python-dotenv ... openpyxl ... pytest ... requests-mock` のように表示されること。
   - Python 3.15 向けにインストールできないライブラリがあった場合は、ライブラリ名を手順11の書式で Mac 側に伝える。

**2回目以降**: コマンドプロンプトを開くたびに、`cd /d C:\work\IR_rep_categorize_v2` と `.venv\Scripts\activate` だけ行う。

---

## 手順3: テストを実行する

```
python -m pytest tests/v2 -q
```

> 確認: 最後の行が **`202 passed`** になること(2026-11-08 時点の件数。更新で増えることがある)。

- 失敗した場合は、`FAILED tests/v2/test_xxx.py::test_r43_...` の行を控えて、手順11の書式で Mac 側に伝える。テスト名の `r43` は要件 ID(R-43)を表す。

---

## 手順4: ローカル作業フォルダを作る

Windows 側で変更するファイル(YAML、プロンプト、接続情報、データ、結果)は、すべてこのフォルダに置く。

1. フォルダを作り、初期値をコピーする。
   ```
   python repclass_cli.py init --local-dir C:\work\repclass_local
   ```
   > 確認: 次のファイルとフォルダができていること。
   > `classification_codes.yaml`、`input_columns.yaml`、`prompts\system_prompt.md`、`comment_preprocess.yaml`、`.env`、`eval_name_map.csv`、`data\`、`outputs\`
   - すでにあるファイルは上書きされないので、何度実行しても安全。
2. 毎回 `--local-dir` を付けるのが面倒な場合は、環境変数に設定しておく(任意)。
   ```
   setx REPCLASS_LOCAL_DIR C:\work\repclass_local
   ```
   - 設定後に開いたコマンドプロンプトから有効になる。以下のコマンド例では、分かりやすさのために `--local-dir` を付けたまま書く。
3. コード体系(YAML)をチェックする。
   ```
   python repclass_cli.py check --local-dir C:\work\repclass_local
   ```
   > 確認: `OK: ... version=0.5.0 製品=ML(51), LENS(42), DC(50)` のように表示されること(2026-11-08 時点。バージョンとコード数は、YAML の更新で変わる)。

---

## 手順5: Dify ワークフローを作り、API キーを設定する

詳しい画面操作は `docs\dify\v2_workflow_setup.md` を見る。ここでは要点とチェックリストだけを書く。

1. Dify で新しいワークフローを作る(例: `repair-classify-v2`)。
2. 開始ノードに、変数を3つ作る。
   - `product_name`(短いテキスト)
   - `code_list`(段落、最大長 30000)
   - `records`(段落、最大長 50000)
3. LLM ノードを設定する。
   - Temperature 0
   - 最大トークン数 8000 以上
   - 出力形式は JSON(Response Format: JSON Object。選べる場合)
4. LLM ノードの SYSTEM に、`C:\work\repclass_local\prompts\system_prompt.md` の `---` より下を貼り付ける。
   - 本文中の `{{product_name}}` と `{{code_list}}` は文字のまま残さず、Dify の変数挿入で開始ノードの変数に置き換える。
5. LLM ノードの USER には、変数 `records` だけを入れる。
6. 終了ノードに出力変数 `result` を作り、値に LLM の出力(text)を選ぶ。
7. 公開して API キーを発行する。
8. `C:\work\repclass_local\.env` をメモ帳で開き、次のように書き換える。
   ```
   DIFY_BASE_URL=https://<Dify のホスト>/v1
   DIFY_API_KEY=app-xxxxxxxx
   ```
   - 社内の証明書が必要な場合は、`REQUESTS_CA_BUNDLE=C:\path\to\corp-ca.pem` の行の先頭の `#` を消して、パスを書く。

チェックリスト:
- [ ] 変数名が `product_name` / `code_list` / `records` / `result` になっている(1文字でも違うと動かない)
- [ ] SYSTEM に `{{product_name}}` などの文字がそのまま残っていない
- [ ] `DIFY_BASE_URL` が `/v1` で終わっている

---

## 手順6: 架空データで通しの確認をする

実データの前に、架空データ(53件。うち2件は除外される想定。2026-11-08 時点)で、Python → Dify → 結果の作成までを通す。

### 6-1. Dify を呼ばずに、送る内容だけを作る(dry-run)
```
python repclass_cli.py run --input tests\fixtures\synthetic\repairs.csv --local-dir C:\work\repclass_local --dry-run
```
> 確認: `dry-run: 入力 53 / 除外 2 / 送信予定 51 / バッチ 6` と、`注記を取り除いた修理: 6 件(マーク: U+25FE, U+2B50, U+203B, U+25A0, U+2605)` が表示されること(マークは初期値の場合)

### 6-2. Dify の画面で1バッチだけ試す
- `C:\work\repclass_local\outputs\<timestamp>\raw\batch_001_request.json` をメモ帳で開く。
- `inputs` の中の3つの値を、Dify のテスト実行画面の3つの入力欄にそれぞれ貼り付けて実行する。
> 確認: 出力が `{"results": [ ... ]}` の形で、10修理分の結果が入っていること。

### 6-3. Python から実行する
```
python repclass_cli.py run --input tests\fixtures\synthetic\repairs.csv --local-dir C:\work\repclass_local
```
> 確認: `入力 53 / 除外 2 / ok … / warning … / error 0` のように表示され、error が 0 件であること。
- error がある場合は、表示されたエラーの種類を見て、`docs\dify\v2_workflow_setup.md` の第4節(トラブルシューティング)を確認する。
  - `api_error`: 接続設定の問題
  - `parse_error`: 出力が JSON になっていない
  - `count_mismatch`: 申告の件数が合わない
  - `unknown_code`: コード一覧にないコードを返している

### 6-4. 期待値と比べる
```
python repclass_cli.py evaluate --gold tests\fixtures\synthetic\expected_claims.csv --run C:\work\repclass_local\outputs\<6-3 の timestamp> --local-dir C:\work\repclass_local
```
> 確認: `user_code` / `reproduction` / `repair_code` の一致率が表示されること。
- 不一致の一覧は `<実行フォルダ>\evaluation\mismatches.csv`。どのシナリオで外れたかを `tests\fixtures\synthetic\README.md` で確認する。
  - 例: T034 で外れていれば、「付随のファーム更新を処置とみなさない」指示が効いていない。
- 架空データは、判断の難しいパターンを集めたもの。最初から 100% にはならなくてよい。外れたパターンが、実データでも重要なものかどうかを見て、調整するか判断する。

---

## 手順7: 実データを少量で実行する

### 7-1. CSV を用意する
- 実データの CSV を `C:\work\repclass_local\data\` に置く。
- **文字コードは UTF-8 にする。** Excel で保存する場合は、「名前を付けて保存」→ ファイルの種類「**CSV UTF-8(コンマ区切り)**」を選ぶ。
  - 通常の「CSV(コンマ区切り)」は Shift-JIS で保存されるため、今のプログラムでは読めない(文字化けやエラーになる)。
- 最初は **50〜100 件程度**に絞ったファイルを作る(例: `C:\work\repclass_local\data\sample_100.csv`)。

### 7-2. 列名と製品種別の値を確認する
- 列名が `ID`、`事業コード`、`user_comment`、`repair_comment`、`Internal_1`、`Internal_2` と違う場合は、`C:\work\repclass_local\input_columns.yaml` の右側を実データの列名に書き換える。
- 製品種別の列の値は、YAML の製品 ID(`ML`、`LENS`、`DC`)と同じである必要がある。違う値の行は「YAML にない製品」として除外される。

### 7-2a. 注記のマークを実データの文字に合わせる(2026-11-08 追加)
修理者コメントの後ろの注記(◾️ファームウエアを更新しました ⭐️バッテリーが劣化しております など)は、Dify に渡す前にプログラムが取り除く(R-64〜R-67)。取り除くマークは `C:\work\repclass_local\comment_preprocess.yaml` に書く。**Mac では実データのマークの文字を確認できないため、Windows 側で合わせる。**

1. 実データの CSV を Excel で開き、マークの文字コードを調べる。例: マークが A2 セルの 15 文字目なら、空いているセルに次を入れる。
   ```
   =DEC2HEX(UNICODE(MID(A2,15,1)))
   ```
   - `25A0` と出たら ■、`2605` なら ★、`203B` なら ※、`25FE` なら ◾、`2B50` なら ⭐。
   - `FE0F` と出た場合は、絵文字の後ろの見えない文字。1つ前の文字を調べる。
2. `comment_preprocess.yaml` をメモ帳で開き、`note_markers:` に `- "\u25A0"` の形で足す(`\u` + 16進4桁。文字そのものは書かない)。使われていないマークは消してもよい。
   - ファイルが無い場合(古いローカル作業フォルダ)は、`python repclass_cli.py init --local-dir C:\work\repclass_local` を実行するとコピーされる(既存のファイルは上書きしない)。
3. dry-run(7-3)を実行し、次を確かめる。
   - 画面の `注記を取り除いた修理: N 件` が 0 件でないこと。0 件なら `注意: ... マークの文字が実データと合っていない可能性があります` と出るので、1 からやり直す。
   - 実行フォルダの `removed_notes.csv` を Excel で開き、`removed`(取り除いた文)に修理内容が入っていないこと、`remaining`(Dify に渡す文)に注記が残っていないことを、10件ほど確かめる。
- 取り除く範囲は、マークから「次のマーク・次の丸数字(①〜⑳)・コメントの終わり」の手前まで。注記の後に②などが続いても、②以降は残る。
- `CSV` の中でマークが `?` に化けている場合は、CSV を「CSV UTF-8」で保存し直す。

### 7-3. dry-run で件数を確認する
```
python repclass_cli.py run --input C:\work\repclass_local\data\sample_100.csv --local-dir C:\work\repclass_local --dry-run
```
> 確認: 除外が想定より多くないこと。
- 画面に、除外の内訳と、YAML にない製品種別の値が表示される(2026-11-06 追加)。
  ```
  除外の内訳: unknown_product 120 / duplicate_id 35(一覧: excluded_rows.csv)
  YAML にない製品種別: 'DC'(100), 'ml'(15), 'ミラーレス'(5)  / YAML の製品ID: ML, LENS
  ```
- 除外された行の一覧は、実行フォルダの `excluded_rows.csv` にある(`excel_row` は Excel で開いたときの行番号)。

| 理由 | 意味 | よくある原因と対処 |
|---|---|---|
| `unknown_product` | 製品種別の値が YAML の製品ID と一致しない | ローカルの YAML にその製品(例: DC)が無い → YAML に追加する。`'ml'`・`'ミラーレス'` のように表記が違う → 入力 CSV 側の値を直す(前後の空白は自動で取り除くので問題ない) |
| `duplicate_id` | 同じ修理IDの2行目以降 | 元データが「1修理=1行」になっていない(部品ごとに行が分かれている等)。**最初の行だけが使われる**ので、元データの取り出し方を確認する |
| `empty_id` | 修理IDが空 | Excel で保存したときにできた末尾の空行なら問題なし |

### 7-4. 実行する
```
python repclass_cli.py run --input C:\work\repclass_local\data\sample_100.csv --local-dir C:\work\repclass_local
```

### 7-5. 結果を目で確認する
- `final.csv` を Excel で開き、10〜20件ほどを、元のコメントと見比べる。
  - **ユーザ申告の故障内容**(`user_claim_names`): 丸数字の数だけ並んでいるか
  - **確認できたもの**(`confirmed_claim_names`): 「再現しなかった」と書かれた申告が入っていないか
  - **メーカー責任修理を含むか**(`manufacturer_repair`): 落下・水没などの修理が NO になっているか
  - **代表故障**(`representative_name`)
- 申告ごとの判定の詳細は `claims.csv` にある(`reproduction` = 再現の判定、`basis` = 同原因かどうか)。

### 7-6. エラーの修理を再実行する
- 表示の最後に `再実行: python repclass_cli.py run ... --resume <timestamp>` と出た場合は、エラーの修理がある。次のコマンドで、エラーの分だけを再実行する。
  ```
  python repclass_cli.py run --input C:\work\repclass_local\data\sample_100.csv --local-dir C:\work\repclass_local --resume <前回の timestamp>
  ```
- 新しい実行フォルダに、前回の結果と合わせた全件の `final.csv` ができる。

---

## 手順8: 過去の分類結果で精度を評価する

### 8-1. 正解ファイルを作る
- 手順7で使ったのと同じ修理について、過去の分類結果から次の2列の CSV(UTF-8)を作る。
  - `repair_id`: 修理ID
  - `representative_name`: 過去に分類した代表故障の名称。メーカー責任でない修理は空欄のまま
- 保存先の例: `C:\work\repclass_local\data\gold_sample_100.csv`

### 8-2. 評価する
```
python repclass_cli.py evaluate --gold C:\work\repclass_local\data\gold_sample_100.csv --run C:\work\repclass_local\outputs\<timestamp> --local-dir C:\work\repclass_local
```
表示の見方:

| 項目 | 意味 |
|---|---|
| YES/NO 一致率 | メーカー責任修理を含むかどうかの判定が、過去の分類と一致した割合 |
| 代表故障 一致率 | 両方が YES の修理のうち、代表故障のコードが一致した割合 |
| コード違い / 正解だけYES / こちらだけYES | 不一致の種類ごとの件数 |
| 名称を変換できず除外 | 過去の名称を YAML のコードに変換できなかった件数 |

### 8-3. 変換できなかった名称を対応表に追加する
- `<実行フォルダ>\evaluation\unresolved_names.csv` に、変換できなかった名称と件数が出る。
- `C:\work\repclass_local\eval_name_map.csv` を Excel で開き、1行ずつ追加する。
  - `product_type`: ML など
  - `past_name`: 過去の名称(そのまま貼り付けてよい。半角カナもそのままでよい)
  - `code`: 対応するコード(例: M001)
- **保存するときは「CSV UTF-8」を選ぶ。**
- 追加したら、8-2 をもう一度実行する。

### 8-4. 不一致の中身を見る
- `<実行フォルダ>\evaluation\mismatches.csv` に、不一致の一覧がある。
- 種類ごとに数件ずつ、元のコメントと `claims.csv` を見て、原因を分ける。
  - LLM の判定の誤り
  - 過去の分類のほうが誤っている
  - ルールの違い(過去の分類方法と v2 の判断ルールが違う)

---

## 手順9: プロンプト・YAML を調整する(手順7〜9を繰り返す)

- **GPT に相談しながら直す場合**は、`20261103_ai_prompt_templates.md` のひな形を使う。アップロードするファイル、GPT に出してもらう変更の形、担当者が変更を当てる手順、当てた後の照合(E)と前後の比較(F)が書いてある。
- **プロンプト**: `C:\work\repclass_local\prompts\system_prompt.md` を直す。
  - 直したら、Dify の SYSTEM に貼り直して公開する(手順5の4)。
  - 判断を誤ったパターンについて、「規則」の該当箇所に具体例を1つ足すのが効きやすい。
- **YAML**: `C:\work\repclass_local\classification_codes.yaml` で、選び間違えやすいコードの説明文を具体的にする。
  - 直したら、必ず `python repclass_cli.py check --local-dir C:\work\repclass_local` を実行する。
  - **Excel で直す場合**(コードの一覧を見ながら直したいとき。R-58〜R-63):
    1. Excel に書き出す。
       ```
       python repclass_cli.py codes-export --local-dir C:\work\repclass_local
       ```
       → `C:\work\repclass_local\classification_codes.xlsx` ができる。すでにある場合は上書きしない(上書きするときは `--force`)。
    2. Excel で直して保存する。
       - シート `ML`・`LENS` は 1行=1コード。記録区分・責任区分・役割はドロップダウンで選ぶ。
       - シート `環境要因` の「常にユーザ起因」は TRUE / FALSE。
       - 各列の意味は、シート `説明` にある。
    3. YAML に戻す。
       ```
       python repclass_cli.py codes-import --local-dir C:\work\repclass_local --xlsx C:\work\repclass_local\classification_codes.xlsx
       ```
       - 問題があれば、YAML は書き換えずに問題の一覧が出る。Excel を直して、もう一度実行する。
       - 成功すると、追加・変更・削除されたコードの一覧が出る。元の YAML は `classification_codes_日時.bak.yaml` として残る。
       - YAML のコメントは作り直しになる(手で書き足したコメントは残らない)。
    4. Excel で書き出した後に YAML を直接直した場合は、古い Excel を戻すと YAML 側の修正が消える。戻す前に、もう一度書き出し直す(`--force`)。
- **比べ方**: 調整の前後で、**同じサンプル**・**同じ正解ファイル**で実行して評価する。
  - どの実行でどのプロンプトを使ったかは、`run_meta.json` の `prompt_sha256` で区別できる。
  - 何を変えたかを、簡単なメモで残しておくとよい。
- **内部コメント**: 内部コメントを読まないと判断できない例が多いと感じたら、`--include-internal` を付けて実行し、結果を比べられる。採用するかどうかは担当者が判断する。

---

## 手順10: 全件を実行し、Tableau に取り込む

1. 全件の CSV(UTF-8)で、`--dry-run` → 本番の順に実行する(手順7と同じ)。
   - 件数が多い場合は、まず1000件程度で所要時間を見る(`run_meta.json` の `elapsed_seconds`)と、全件の時間を見積もれる。
2. エラーがあれば `--resume` で再実行する。
3. Tableau Desktop で `final.csv` を開く(テキストファイルとして接続)。
   - 文字コードは UTF-8(BOM付き)なので、そのまま読める。
   - 複数の値は `;` 区切り(例: `user_claim_codes`)。Tableau で分けて使う場合は、計算フィールドの SPLIT を使う。
   - メーカー責任の故障だけを見る場合は、`manufacturer_repair = YES` でフィルターする。

---

## 手順11: 気づいた点を Mac 側に伝える

- 担当者がメモして、Mac 側のチャットに書き込む。**実データの内容(コメント本文や ID)は書かない。**
- 書式: `[要件ID] 現象(1〜2行)。例: 架空の短い例`
  - `R-09: Python 3.15 で ○○ がインストールできない`
  - `テスト失敗: test_r43_chain`
  - `要望: CSV を Shift-JIS のまま読めるようにしてほしい`
  - `精度: 予防交換の行が「再現」になる例が多い`
- Mac 側で仕様・テスト・コードを直したら、新しい版を GitHub に送る。Windows 側は手順1(更新)と手順2・3をやり直す(必要なライブラリが増えることがあるので、`pip install -r requirements-dev.txt` も毎回実行する)。

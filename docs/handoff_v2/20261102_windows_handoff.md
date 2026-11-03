# 引き継ぎ資料: Windows 側(実データ環境)での作業 — 修理データ分類 v2

- 作成日: 2026-11-02(Mac 側で作成)
- 読み手: Windows 側で作業する AI(GPT)と担当者
- この資料の目的: 実データのある Windows PC で、v2 の環境構築・Dify 構築・実データでの実行・精度評価・調整を行うための手順とルールを示す。

---

## 0. 最初に読む文書

| 文書 | 内容 |
|---|---|
| `docs/20261101_requirements.md` | **要件定義書(正本)**。要件 ID(R-xx)はここで定義している |
| `docs/20261030_llm-classification-spec.md` | 仕様メモ(要件の背景・決定の経緯) |
| `docs/dify/v2_workflow_setup.md` | Dify ワークフローの構築手順 |
| `tests/fixtures/synthetic/README.md` | 架空テストデータのシナリオ一覧 |
| `docs/handoff_v2/20261102_windows_steps_detailed.md` | 担当者向けの詳しい手順(確認ポイント付き) |

## 1. 作業のルール(必ず守る)

### 1.1 変更してはいけないもの(R-01)
- `src/repclass/`(プログラム本体)
- `tests/`(テスト)
- そのほか、リポジトリ内のファイル全般

プログラムの不具合や、仕様と合わない点を見つけても、**コードを直さない**。第7節の書式で報告する。

### 1.2 変更してよいもの(R-02、R-05a)
**ローカル作業フォルダ**(例: `C:\work\repclass_local\`)の中のファイルだけ。

| ファイル | 変更の例 |
|---|---|
| `classification_codes.yaml` | コードの追加、説明文・responsibility・環境要因の調整。**キーの構造は変えない**。変更後は `check` を実行する。Excel で直す場合は `codes-export` → Excel で修正 → `codes-import`(R-58〜R-63) |
| `classification_codes.xlsx` | `codes-export` で書き出した確認・修正用の Excel |
| `prompts/system_prompt.md` | プロンプトの調整(変更後は Dify に貼り直す) |
| `input_columns.yaml` | 入力 CSV の列名が既定と違う場合に合わせる |
| `eval_name_map.csv` | 評価用の、過去の名称とコードの対応表 |
| `.env` | Dify の接続情報(共有しない) |
| `data\`, `outputs\` | 入力データと実行結果 |

### 1.3 情報の流れ(R-03)
- Mac → Windows の一方向。Windows 側の変更内容や実行結果は Mac に戻らない。
- Mac に伝えられるのは、担当者が手でメモできる程度の短い情報だけ(第7節)。
- **実データの内容(コメント本文、ID など)は報告に書かない。**

## 2. 環境構築

### 2.1 コードの取得と更新
- GitHub からリポジトリ全体をダウンロードして展開する(例: `C:\work\IR_rep_categorize_v2\`)。
- 新しい版が届いたら、**コードのフォルダを丸ごと置き換える**。ローカル作業フォルダはコードとは別の場所にあるので、上書きされない。

### 2.2 Python 環境(uv は使わない。R-12)
コードのフォルダで実行する。

```
py -3.15 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

- 社内プロキシや証明書でインストールできない場合は、`pip install --cert <証明書のパス> -r requirements-dev.txt` を試す。
- 必要なライブラリは `pyyaml`、`requests`、`python-dotenv`、`openpyxl`、テスト用に `pytest`、`requests-mock` だけ(R-09、R-11)。
- Python 3.15 でインストールできないライブラリがあれば、第7節の書式で報告する。

### 2.3 テストの実行
```
python -m pytest tests/v2 -q
```
- 期待: **155 passed**(2026-11-03 時点)。
- 失敗した場合は、失敗したテスト名(`test_r43_...` のように要件 ID が入っている)を第7節の書式で報告する。

### 2.4 ローカル作業フォルダの作成
```
python repclass_cli.py init --local-dir C:\work\repclass_local
python repclass_cli.py check --local-dir C:\work\repclass_local
```
- `init` はリポジトリの初期値をコピーする。既存のファイルは上書きしない。
- `check` が `OK` になることを確認する。
- 毎回 `--local-dir` を付ける代わりに、環境変数 `REPCLASS_LOCAL_DIR` に設定してもよい。
- `.env` に Dify の接続情報を書く(第3節)。

## 3. Dify ワークフローの構築
`docs/dify/v2_workflow_setup.md` の手順に従う。プロンプトは、ローカル作業フォルダの `prompts\system_prompt.md` を使う。

## 4. 架空データでの動作確認
実データの前に、架空データ(`tests\fixtures\synthetic\repairs.csv`)で Dify を通して確認する。

```
python repclass_cli.py run --input tests\fixtures\synthetic\repairs.csv --local-dir C:\work\repclass_local
python repclass_cli.py evaluate --gold tests\fixtures\synthetic\expected_claims.csv --run C:\work\repclass_local\outputs\<timestamp> --local-dir C:\work\repclass_local
```

- 期待: 入力 45 / 除外 2 / error 0。
- `user_code`・`reproduction`・`repair_code` の一致率を確認する。
- 不一致は `<実行フォルダ>\evaluation\mismatches.csv` にある。該当シナリオのねらいを `tests/fixtures/synthetic/README.md` で確認し、プロンプトを調整する。

## 5. 実データでの実行

### 5.1 実行
1. 実データの CSV を `C:\work\repclass_local\data\` に置く。
   - 文字コードは UTF-8 にする(Excel では「CSV UTF-8(コンマ区切り)」で保存)。Shift-JIS の CSV は読めない。
2. 列名が既定(`ID`、`事業コード`、`user_comment`、`repair_comment`、`Internal_1`、`Internal_2`)と違う場合は、`input_columns.yaml` を合わせる。
3. まず `--dry-run` で件数とバッチ数を確認する。
4. 最初は 50〜100 件程度で実行し、結果を目で確認してから件数を増やす。

```
python repclass_cli.py run --input C:\work\repclass_local\data\xxx.csv --local-dir C:\work\repclass_local --dry-run
python repclass_cli.py run --input C:\work\repclass_local\data\xxx.csv --local-dir C:\work\repclass_local
```

### 5.2 エラーの修理の再実行(R-35〜R-40)
- エラーがあっても、最終出力(`final.csv`)は全件そろう。エラーの修理は `status=error` になり、判断結果の列は空欄になる。
- エラーの修理だけを再実行するには、次のコマンドを使う。前回の結果と結合した、全件そろった最終出力が新しい実行フォルダにできる。

```
python repclass_cli.py run --input <同じCSV> --local-dir C:\work\repclass_local --resume <前回の timestamp>
```

### 5.3 出力ファイル(R-50)
| ファイル | 内容 |
|---|---|
| `final.csv` | 修理単位の最終出力(Tableau 用) |
| `claims.csv` ほか | 中間データ |
| `validation_issues.csv` | エラーと警告の一覧 |
| `run_meta.json` | 件数、YAML・プロンプトの版(ハッシュ値)など |

## 6. 精度評価と調整

### 6.1 過去の分類結果での評価(簡易版、R-54〜R-55a)
1. 過去の分類結果から、`repair_id` と `representative_name`(代表故障の名称。メーカー責任でない修理は空欄)の2列の CSV を作る。
2. 次のコマンドで評価する。

```
python repclass_cli.py evaluate --gold <正解CSV> --run <実行フォルダ> --local-dir C:\work\repclass_local
```

3. 名称をコードに変換できなかったものは `evaluation\unresolved_names.csv` に出る。`eval_name_map.csv`(列: `product_type`, `past_name`, `code`)に追記して、再度評価する。
4. 確認するのは、YES/NO の一致率と代表故障の一致率。不一致の種類(コード違い / 正解だけ YES / こちらだけ YES)ごとに、原因を見る。

### 6.2 調整の進め方
- **プロンプトの調整**: `prompts\system_prompt.md` を直す → Dify に貼り直す → 同じサンプルで再実行 → 評価する。プロンプトのハッシュ値は `run_meta.json` に自動で記録される。
- **YAML の調整**: コードの説明文を具体的にすると、LLM が選び間違えにくくなる。変更したら `check` を実行する。
- 調整の前後で、同じサンプルを使って比べる。
- **内部コメント**: 内部コメントを読まないと正しく分類できない例があれば、正解ファイルの `needs_internal_comment` に `1` を付けて記録する(詳細版の正解ファイルの場合)。`--include-internal` を付けると内部コメントも LLM に渡せる。ただし、渡すかどうかを決めるのは担当者。

## 7. Mac 側への報告(R-56)

担当者が手でメモして Mac 側に伝えるので、**短く**書く。実データの内容は書かない。

```
[要件ID] 現象(1〜2行)。例: 架空の短い例
```

- 例1: `R-43: 同原因の行の repair_code が空になる。例: ①電源入らない ②①と同原因`
- 例2: `R-09: Python 3.15 で requests-mock がインストールできない`
- 例3: `テスト失敗: test_r27_count_failures(丸数字の扱い)`
- 例4: `要望: 代表故障の一致率が低い。ファーム更新の付随作業を処置と誤認している例が多い`

## 8. 完了条件

- [ ] `python -m pytest tests/v2 -q` がすべて通る
- [ ] `check` が OK
- [ ] Dify ワークフローを構築し、架空データで error 0 件
- [ ] 実データで実行し、`final.csv` が Tableau で読める
- [ ] 過去の分類結果で簡易版の評価を行い、YES/NO と代表故障の一致率を把握している
- [ ] 気づいた点を、第7節の書式で Mac 側に伝えた

---

## 付録: GPT への最初の指示(例)

```
このリポジトリは修理データ分類パイプライン v2 です。
docs/handoff_v2/20261102_windows_handoff.md の手順とルールに従って作業してください。
- src/ と tests/ は変更しないでください。変更してよいのはローカル作業フォルダ(C:\work\repclass_local)の中だけです。
- 不具合や仕様の食い違いを見つけたら、コードを直さず、第7節の書式で短く報告してください。
- 実データの内容は報告に含めないでください。
まず第2節の環境構築とテストの実行から始め、結果を報告してください。
```

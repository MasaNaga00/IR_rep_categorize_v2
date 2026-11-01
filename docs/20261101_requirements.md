# 要件定義書: 修理データ分類パイプライン v2(LLM方式)

- 作成日: 2026-11-01
- 版: 第3版(2026-11-02、Q5〜Q7 の回答を反映)/ 2026-11-02 追記: R-31 に判断の指示を追加(架空データの確認で決定)
- ステータス: 確定(2026-11-02 ユーザ承認)
- 元になる仕様: `docs/20261030_llm-classification-spec.md`(以下「仕様メモ」)
- 要件には ID(R-xx)を付ける。テストは対応する ID をテスト名またはコメントに書く。
- 「要確認」と書いた項目は、ユーザの判断待ち(第11節に一覧)。
- 2026-11-02: v2 専用リポジトリ(IR_rep_categorize_v2)へ移行。旧方式のファイル(`src/*.py`、旧テスト、旧プロンプト等)は含まない。R-06・R-07 と YAML の「既存」の記述は、移行前の経緯として残している。旧方式専用の YAML の項目(`reproduction_statuses` 等)は削除済み。

---

## 1. 目的と範囲

### 1.1 目的

カメラ等の修理データ(ユーザコメント・修理者コメント)を LLM で分類し、修理ごとに次の情報を出力する(仕様メモ第14.5節)。

- ユーザが申告した故障内容
- 申告のうち、修理者が確認できたもの
- 修理者が確認した故障内容
- メーカー責任修理を含むか(YES/NO)
- 代表故障

### 1.2 作業の分担と情報の流れ

| 範囲 | 担当 | 場所 |
|---|---|---|
| 要件定義、架空データ、テスト、ロジック実装、Dify 呼び出し部、評価スクリプト、プロンプト初版、YAML 初版、手順書 | Claude | Mac(実データなし) |
| 環境構築、Dify ワークフロー構築、実データでの実行、正解データ作成、精度評価、プロンプト調整、YAML の内容調整 | GPT(ユーザの指示による) | Windows(実データあり) |

- R-01: Windows 側では `src/repclass/` と `tests/` を変更しない。
- R-02: Windows 側で変更してよいのは、**ローカル作業フォルダ**(R-05a)の中のファイルだけとする。
  - YAML の**内容**: コードの追加・説明文・responsibility・環境要因など
    - ただし、キーの構造(第4節)は変えない。
    - 変更後は `python -m repclass.check_codebook` でチェックが通ること(R-16)。
  - プロンプト
  - 設定(`.env`、列の対応づけ)
  - 入力データ、実行結果、評価用データ
- R-03: 情報は **Mac → Windows の一方向**とする。
  - Windows 側の変更内容(YAML、プロンプト、実行結果)は Mac に戻らない。
  - Windows から Mac へは、人が手でメモできる程度の短い情報だけを伝える(第10.2節)。
- R-04: 引き渡し後は、YAML とプロンプトの正本は Windows 側(ローカル作業フォルダ)とする。
  - Mac 側で YAML の構造変更が必要になった場合は、Windows 側の YAML に対して実行する変換スクリプト、または手順書として渡す。
- R-05a(ローカル作業フォルダ、2026-11-02 追加): Windows 側は、GitHub からリポジトリ全体をダウンロードして更新する(Q7)。そのため、新しい版を展開したときに Windows 側の変更が上書きされないよう、**コードとは別のフォルダ**に、Windows 側で変更するファイルをまとめる。
  - 例: `C:\work\repclass_local\`

| ローカル作業フォルダの中 | 内容 |
|---|---|
| `classification_codes.yaml` | YAML(初回はリポジトリの `config/` からコピーする) |
| `prompts/system_prompt.md` | プロンプト(同上) |
| `input_columns.yaml` | 列の対応づけ(同上) |
| `eval_name_map.csv` | 評価用の名称→コードの対応表(R-55a) |
| `.env` | Dify の接続情報 |
| `data/`, `outputs/` | 入力データ、実行結果 |

  - 場所は、コマンドの `--local-dir` または環境変数 `REPCLASS_LOCAL_DIR` で指定する。
  - 設定ファイルは、次の順で探す: コマンドで個別に指定したパス → ローカル作業フォルダ → リポジトリの `config/`(初期値)
  - 初回用に、リポジトリの初期値をローカル作業フォルダへコピーするコマンド `python repclass_cli.py init --local-dir <path>` を用意する。既存のファイルは上書きしない。
  - コードの更新は、新しい版をダウンロードしてコードのフォルダを置き換えるだけで済む。
- R-05: テストは実際の YAML に依存しない。テスト専用の YAML(`tests/fixtures/codebook_test.yaml`)を使う。
  - そのため、Windows 側で YAML の内容を調整してもテストは壊れない。

### 1.3 既存コードとの関係

- R-06: 新しい方式は新パッケージ `src/repclass/` として作る。既存の `src/*.py`(`split.py` 等)と既存テストは変更しない。
- R-07: 分類コード体系は既存の `config/classification_codes.yaml` を拡張して使う(1ファイルを正本とする)。追加するキーは第4節。
  - 既存の `codes_loader.py` は未知のキーを許容する設定(`extra="allow"`)のため、追加しても既存コードは壊れない(確認済み)。

## 2. 動作環境

- R-08: Python 3.13 以上で動作すること。3.14 以降でだけ使える機能は使わない(Windows 側は 3.15)。
- R-09: 必須の外部ライブラリは `pyyaml`、`requests`、`python-dotenv`。`pandas` は必要な箇所でのみ使ってよい。
  - 判断ロジック(第6〜8節)は標準ライブラリで実装し、Python 3.15 での動作リスクを減らす。
- R-10: Parquet は出力しない。
- R-11: テスト用ライブラリは `pytest`、`requests-mock`。
- R-12: 依存関係は `requirements.txt`(実行用)と `requirements-dev.txt`(テスト用)で管理する。uv は前提にしない。
- R-13: Windows・Mac の両方で動くこと。
  - ファイルは常に UTF-8 を明示して読み書きする。CSV 出力は `utf-8-sig`(Excel と Tableau の両方で読めるようにするため)。
  - パスは `pathlib` で扱う。
  - リポジトリに `.gitattributes` を置き、改行コードの差分を防ぐ。

## 3. 全体の流れ

```
[入力CSV]
  ↓ (1) 読み込み・列の対応づけ             input_loader
  ↓ (2) 故障数・番号の存在の計算            failure_count
  ↓ (3) 製品ごとにバッチ化して Dify 呼び出し   llm_request / dify_client
[層1: 生出力 JSON]
  ↓ (4) パース・検証・エラー時の再試行       llm_response
  ↓ (5) 中間データの作成(引き継ぎ・空の行)  tables
[層2: 中間データ 4表]
  ↓ (6) 判断ルールの適用                    judge
[層3: 最終出力(修理単位)]
  ↓ (7) ファイル出力・実行メタ情報           outputs
```

- R-14: 実行の入口は `python -m repclass.run`(第9節)。

## 4. 分類コード体系(YAML)の拡張

### 4.1 製品セクション

- R-15: 各製品セクション(`product_categories.<製品ID>`)と各故障コードに、次のキーを持たせる。

**製品セクション**

| キー | 必須 | 内容 |
|---|---|---|
| `name` | 必須 | 表示名(例: ミラーレスカメラ)。既存 |
| `code_prefix` | 必須 | コードの接頭文字(例: `M`)。製品間で重複不可 |
| `failure_categories` | 必須 | 故障コード一式。既存 |
| `environment_factors_override` | 任意 | 環境要因の追加・上書き(4.3) |

**故障コード**

| キー | 必須 | 内容 |
|---|---|---|
| `name` | 必須 | 既存 |
| `description` | 必須 | 既存 |
| `record_type` | 必須 | `failure` / `service` / `unknown`。既存 |
| `responsibility` | 必須 | `manufacturer` / `user_or_unknown`。2026-11-01 に全コード設定済み |
| `role` | 任意 | 特別な役割: `connected_device`(接続機器要因)/ `other`(その他)/ `unknown`(判定不能) |

- 既存の ML / LENS には、次の値を追加する。
  - `code_prefix`: ML は `M`、LENS は `L`
  - `role`: M047 / L037 = `connected_device`、M046 / L036 = `other`、M_UNK / L_UNK = `unknown`
- `meta.version` を `0.3.0` にする。

### 4.2 自動チェック(仕様メモ第16.5節)

- R-16: `load_codebook()` は次をチェックし、1つでも違反があれば `CodebookError` を送出する。メッセージには違反をすべて列挙する。
  1. 必須キーがそろっている(R-15)
  2. 各製品に、`role` が `connected_device`・`other`・`unknown` のコードが1つずつある
  3. 各製品に、`record_type: service` のコードが1つ以上ある
  4. 全コードの `responsibility` が `manufacturer` か `user_or_unknown`
  5. `code_prefix` が製品間で重複していない
  6. 各コードが自製品の `code_prefix` で始まる
  7. 環境要因のキーが重複していない。`always_user_caused` は真偽値
- 同じチェックを、コマンド `python -m repclass.check_codebook [--codebook <path>]` でも実行できるようにする。Windows 側で YAML を調整した後の確認に使う。

### 4.3 環境要因

- R-17: 既存のトップレベル `environment_factors` を、全製品共通の既定値とする。各要因に次のキーを追加する。
  - `always_user_caused`: `true` の要因は、LLM の判定に関係なく常にユーザ起因とする。既定値は `false`。
  - `impact`(落下・衝撃)と `water`(水濡れ・浸水、雨を含む)に `true` を設定する(2026-11-02 確定、Q3 案A)。
- R-18: `none` と `unknown` は LLM の出力では使わない。環境要因が無ければ空の配列で表す。
- R-19: 製品の `environment_factors_override` で、要因の追加(新しいキー)や、既存要因のキーの上書きができる。

### 4.4 ユーザ申告再現の値

- R-20: 新しいトップレベル `claim_reproduction_statuses` を追加する。既存の `reproduction_statuses` は旧方式用(v2 リポジトリでは削除済み)。

| 値 | 表示名 | 「確認できた」に含む |
|---|---|---|
| `reproduced` | 再現 | はい |
| `partial` | 一部再現 | はい |
| `not_reproduced` | 再現せず | いいえ |
| `not_mentioned` | 記載なし | いいえ |
| `out_of_scope` | 対象外 | いいえ |
| `request_only` | 依頼のみ | いいえ |

- 各値に `name`(表示名)、`description`、`counts_as_confirmed`(真偽値)を持たせる。
- 判定の指示は第7.2節(R-31)に書く。

### 4.5 API

- R-21: `repclass.codebook` は次を提供する。

```python
def load_codebook(path: str | Path) -> Codebook: ...

class Codebook:
    version: str                 # meta.version
    sha256: str                  # YAML ファイルのハッシュ値(実行メタ情報用)
    def product_ids(self) -> list[str]: ...
    def code(self, product_id: str, code: str) -> CodeInfo | None: ...
    def is_valid_code(self, product_id: str, code: str) -> bool: ...
    def is_manufacturer(self, product_id: str, code: str) -> bool:   # 未定義コードは False
    def is_service(self, product_id: str, code: str) -> bool: ...
    def code_by_role(self, product_id: str, role: str) -> str: ...
    def environment_factors(self, product_id: str) -> dict[str, EnvFactorInfo]: ...  # 既定値 + 上書き
    def claim_statuses(self) -> dict[str, ClaimStatusInfo]: ...
    def code_list_text(self, product_id: str) -> str: ...   # LLM に渡すコード一覧(4.6)
```

### 4.6 LLM に渡すコード一覧

- R-22: `code_list_text()` は、その製品の全コードを1行1コードで出力する。
  - 各行の形式は `コード | 名称 | 説明文`。
  - responsibility は含めない(LLM に責任を判断させないため)。

## 5. 入力

- R-23: 入力は CSV(UTF-8、BOM の有無どちらも可)。
- R-24: 列の対応づけは設定ファイル `config/input_columns.yaml` で指定する。既定値は次のとおり(実データの列名)。

| 内部名 | 既定の列名 | 必須 |
|---|---|---|
| `repair_id` | `ID` | 必須 |
| `product_type` | `事業コード` | 必須 |
| `user_comment` | `user_comment` | 必須(空欄可) |
| `repair_comment` | `repair_comment` | 必須(空欄可) |
| `internal_1` | `Internal_1` | 任意 |
| `internal_2` | `Internal_2` | 任意 |

- R-25: 次の行は処理対象から外し、理由を実行メタ情報に記録する。
  - `repair_id` が空
  - `repair_id` が重複している(2行目以降)
  - `product_type` が YAML にない製品
- R-26: 内部コメントは読み込んで中間データに保持するが、当面は LLM に渡さない(仕様メモ第10節)。渡すかどうかは設定で切り替えられるようにする(既定値: 渡さない)。

## 6. 故障数(Python)

- R-27: `count_failures(user_comment: str) -> FailureCountResult` を提供する。
  - `failure_count`: ユーザコメント中の丸数字(①〜⑳)の最大値。丸数字が無ければ 1。
  - `present_numbers`: ユーザコメントに出現した番号の集合
  - `missing_numbers`: 1〜`failure_count` のうち、出現しない番号(番号飛び)
- R-28: ユーザコメントが空欄でも、`failure_count` は 1 とする。

## 7. LLM の入出力

### 7.1 リクエスト

- R-29: バッチは**製品ごと**に作る(1つのバッチに複数の製品を混ぜない)。既定のバッチサイズは 10 修理。
- R-30: Dify ワークフローへの入力変数は次の3つ。
  - `product_name`: 製品の表示名
  - `code_list`: `code_list_text()` の出力
  - `records`: 次の要素の JSON 配列(文字列にして渡す)

```json
{"repair_id": "R001", "failure_count": 2, "missing_numbers": [],
 "user_comment": "...", "repair_comment": "..."}
```

- プロンプト本文は `config/prompts/v2/system_prompt.md` で管理し、Dify に貼り付ける。判断ルールはプロンプトに固定し、コード一覧だけを変数で渡す(仕様メモ第16.2節)。

### 7.2 プロンプトに含める判断の指示

- R-31: プロンプト初版には、次の判断の指示と、それぞれの短い架空の例を含める。

**ユーザ申告再現(reproduction)**
- 判定はキーワードではなく、文の意味で行う。
- 修理者がその番号について、原因・所見・処置を書いている場合は `reproduced` とする。「再現した」と明記されていなくてもよい。
  - 例: 「hogeにより起こっていました」「○○を交換」
- 「繰り返し確認したが再現しませんでした」「症状確認できず」「異常は認められませんでした」など、症状を確認できなかった記述は `not_reproduced` とする。二重否定などの回りくどい言い回しも含む。
- 条件付きで再現した場合、または一部の症状だけ再現した場合は `partial` とする。
- その番号について再現の有無が読み取れない場合は `not_mentioned` とする。
- 「レンズ側で対応」のように、別の機器や対象外の扱いとされた場合は `out_of_scope` とする。
- 点検・清掃などの依頼で、不具合の訴えがない場合は `request_only` とする。
- ユーザコメント側に「ご指摘外の現象」として書かれたもの(`【ご指摘外の現象】` の表記を含む)は、修理者が見つけた故障なので `reproduced` とする(2026-11-02 確定、Q2)。
- 「予防交換」は、修理者コメントに処置として書かれていても `not_reproduced` とする(2026-11-02 追記)。
- 「関連箇所を点検いたしましたが、異常はございませんでした。」のような定型文は `not_reproduced` の根拠とする。

**前置きと【】(2026-11-02 追記)**
- 丸数字の前の前置きも読む。
  - 例: 修理者コメントの「ショック品」は環境要因(落下・衝撃、記述は修理者)
  - 例: 「メンテナンスで入庫しましたが、修理に移行しました」は、依頼のみではなく通常の申告として扱う
- `【修理上限金額：100000円】` のような事務的な【】は無視する。
- `部品【基板ユニット】を交換` のような【】は、部品名として読む。
- `【オーバーホール】①…②…` のような前置きの【】は、入庫の目的として読む。故障数は丸数字で決まる(R-27)。

**付随作業(2026-11-02 追記)**
- 「※作業に伴いカメラ設定を初期化しました」「※最新ファームウエアに更新しました」のような、修理に付随して行った作業は**処置とみなさない**。修理者視点コードをファームアップ(サービスコード)にしない。
- ファームウエアの更新**そのもの**で症状が改善したと書かれている場合だけ、ファームアップのコードにする。

**同原因(basis)**
- 「②は①と同じ原因」のように他の番号を参照している場合は、`basis` を `same_cause` とし、`ref_sub_id` に参照先の番号を入れる。

**修理者視点コード(repair_code)**
- 修理者が特定した実際の不具合のコードを入れる。
- 確認できなかった行は、次のとおりとする(2026-11-02 確定)。
  - `not_reproduced`・`not_mentioned`: 空(`null`)
  - `request_only`: 行った作業のサービスコード(例: 清掃なら M043)
  - `out_of_scope`: `role` が `connected_device` のコード(接続機器が原因でこの製品に異常がない場合)
- 「①②同じ部品の不良」のようなまとめ書きは、「同原因」と同じ扱いとし、各行の修理者視点コードはその行自身のユーザ視点コードとする(2026-11-02 確定、R-43 と同じ考え方)。
  - LLM には各行を `direct` で出力させ、`repair_code` に各行のユーザ視点コードを入れるよう指示する。

**ユーザ視点コード(user_code、2026-11-02 確定)**
- 依頼のみの行は、依頼の内容のコードとする(例: 清掃依頼なら M043、オーバーホール依頼ならオーバーホールのコード)。
- ユーザコメントが空欄の場合は、`role` が `unknown` のコード(判定不能)とする。

**環境要因**
- 記述があるものだけを出力する。
- 通常では考えづらい使用かどうかを `abnormal_use` に入れる。

**抜き出し(excerpt)**
- 原文からそのまま抜き出す。要約や言い換えはしない。

### 7.3 期待する LLM 出力(1修理あたり)

- R-32: LLM は次の形の JSON を返す。全体は `{"results": [ ... ]}` とする。確信度(confidence)は出力させない(2026-11-02 確定、Q4)。

```json
{
  "repair_id": "R001",
  "claims": [
    {
      "sub_id": 1,
      "user_excerpt": "電源が入らない",
      "user_code": "M001",
      "reproduction": "reproduced",
      "basis": "direct",
      "ref_sub_id": null,
      "repair_code": "M001",
      "repair_excerpt": "電源基板不良"
    }
  ],
  "environment": [
    {"factor": "impact", "source": "user", "abnormal_use": true, "excerpt": "落としてしまった"}
  ],
  "extra_findings": [
    {"description": "別途グリップラバー劣化", "repair_code": "M028", "excerpt": "グリップラバー劣化あり"}
  ]
}
```

| 項目 | 値 |
|---|---|
| `basis` | `direct`(直接確認)/ `same_cause`(他の番号と同原因)/ `none`(根拠なし) |
| `ref_sub_id` | `basis` が `same_cause` のときの参照先の番号。それ以外は `null` |
| `source` | `user` / `repair` / `both` |
| `abnormal_use` | 通常では考えづらい使用か(真偽値) |

### 7.4 検証

- R-33: `parse_llm_response(raw: str | dict) -> ParsedBatch` は、次のいずれの形でも受け付ける。
  - `{"results": [...]}`
  - 配列そのもの
  - コードブロック(```json)で囲まれた JSON 文字列
- R-34: `validate_result(result, request_record, product_id, codebook) -> list[ValidationIssue]` は、次の項目をチェックする。各問題には `repair_id`、`sub_id`、種類、メッセージを持たせる。

| 種類 | 内容 | 扱い |
|---|---|---|
| `count_mismatch` | `claims` の件数が `failure_count` と違う | エラー |
| `sub_id_invalid` | `sub_id` が 1〜`failure_count` の範囲外、または重複している | エラー |
| `unknown_code` | コードがその製品のコード体系にない | エラー |
| `invalid_enum` | `reproduction`、`basis`、`source`、`factor` が定義外の値 | エラー |
| `ref_invalid` | `same_cause` なのに `ref_sub_id` が無い・自分自身・範囲外 | エラー |
| `missing_repair` | 結果に含まれない `repair_id` がある | エラー |
| `parse_error` | 応答が JSON として読めない | エラー(バッチ内の全修理) |
| `api_error` | Dify の呼び出しに失敗した(R-47 のリトライ後) | エラー(バッチ内の全修理) |
| `excerpt_not_found` | 抜き出しが原文に含まれない(空白の違いは無視する) | 警告 |
| `ref_cycle` | 同原因の参照が循環している | 警告 |

### 7.5 エラー時の動作

- R-35: エラーが出ても処理は止めず、**最終出力まで作る**。
- R-36: エラーのあった修理は、自動で1回だけ再試行する。
  - 再試行は、その修理だけを1件ずつ送る形で行う。
  - 再試行でもエラーが残った修理は `status = error` とする。
- R-37: 修理の状態(`status`)は次の3つ。
  - `ok`: 問題なし
  - `warning`: 警告のみ。判断結果は出力する
  - `error`: エラー
    - 判断結果の列(`manufacturer_repair`、`representative_code` など)は**空欄**にする。`NO` とは区別する。
    - `error_reason` に、エラーの種類を入れる。
- R-38: `status = error` の修理も、`final.csv` と `repairs.csv` に1行として出力する。どの修理がエラーかを一覧で分かるようにするためである。
- R-39: エラーの修理の入力を `error_repairs.json` に出力する。
- R-40: `--resume <timestamp>` を指定すると、前回の実行でエラーだった修理だけを再実行する。
  - 結果は新しい実行フォルダに出力する。
  - 前回の `ok` / `warning` の結果と結合して、**全件そろった最終出力**を作る。
  - `run_meta.json` には、再実行元の timestamp を記録する。

## 8. 中間データと判断ルール

### 8.1 中間データ(仕様メモ第14.4節)

- R-41: `build_tables(requests, parsed_results, codebook) -> Tables` は、次の4つの表を作る。各表は dict のリストとして持つ。

| 表 | 列 |
|---|---|
| repairs(修理表) | `repair_id`, `product_type`, `failure_count`, `user_comment`, `repair_comment`, `internal_1`, `internal_2`, `status`, `error_reason` |
| claims(申告表) | `repair_id`, `sub_id`, `user_excerpt`, `user_code`, `reproduction`, `basis`, `ref_sub_id`, `repair_code`, `repair_excerpt`, `inherited`(真偽値) |
| environments(環境要因表) | `repair_id`, `factor`, `source`, `abnormal_use`, `user_caused`, `excerpt` |
| extra_findings(追加の発見表) | `repair_id`, `seq`, `description`, `repair_code`, `excerpt` |

### 8.2 Python 側で機械的に適用するルール

- R-42(番号飛び): `missing_numbers` の番号の行は、LLM の出力に関係なく次の値にする。
  - `user_code` = `NO_CLAIM`(申告なしを表す定数)
  - `reproduction` = `not_mentioned`
  - `repair_code` = 空
- R-43(同原因の引き継ぎ、2026-11-02 修正): `basis` が `same_cause` の行は、次のように扱う。
  - `reproduction` は、`ref_sub_id` の行から引き継ぐ。参照が連鎖する場合(③→②→①)は、最終的な参照先までたどる。
  - `repair_code` には、**その行自身の `user_code`** を入れる。ユーザが申告した現象が実際に起きていた、とみなすためである。
  - `inherited` を真にする。
  - 参照が循環する場合は引き継ぎを行わず、警告(`ref_cycle`)を記録する。
- R-44(ユーザ起因): `user_caused` = その要因の `always_user_caused` が真、**または** `abnormal_use` が真。
- R-45(記録区分): 記録区分は中間データに持たせず、出力時に `repair_code` の `record_type` から求める(仕様メモ第14.4節)。

### 8.3 最終出力(修理単位、仕様メモ第14.5節)

- R-46: `judge_repairs(tables, codebook) -> list[dict]` は、全修理について次の列を作る。
  - 「確認できた行」= `reproduction` の `counts_as_confirmed` が真の行(再現・一部再現)
  - `status = error` の修理は、判断結果の列を空欄にする(R-37)。

| 列 | 内容 |
|---|---|
| `repair_id`, `product_type`, `failure_count`, `status`, `error_reason` | |
| `user_claim_codes` | claims の `user_code` を番号順に `;` で連結(`NO_CLAIM` を含む) |
| `confirmed_claim_codes` | 確認できた行の `user_code` |
| `repair_confirmed_codes` | 確認できた行の `repair_code`(空を除く)+ extra_findings の `repair_code`(2026-11-02 確定、Q1) |
| `user_caused_env` | ユーザ起因の環境要因があるか(真偽値) |
| `user_caused_factors` | ユーザ起因の要因を `;` で連結 |
| `manufacturer_repair` | `YES` / `NO`(R-47) |
| `representative_code` | 代表故障(R-48) |
| `representative_name` | 代表故障のコード名 |

- 名称の列(`user_claim_names` など)も、コード名を YAML から引いて同じ順に並べて出力する。

- R-47(メーカー責任修理を含むか):
  1. `user_caused_env` が真 → `NO`
  2. `repair_confirmed_codes` のうち、`is_manufacturer` が真のものが1つでもある → `YES`
  3. それ以外 → `NO`
- R-48(代表故障):
  1. 確認できた行のうち、`repair_code` がメーカー責任の行の中で、`sub_id` が最小の行の `repair_code`
  2. 1 が無く、`manufacturer_repair` が `YES` の場合は、extra_findings のうちメーカー責任の最初(`seq` 最小)の `repair_code`
  3. `manufacturer_repair` が `NO` の場合は空

## 9. 実行と出力ファイル

- R-49: コマンド

```
python -m repclass.run --input data/xxx.csv [--local-dir <path>]
                       [--codebook <path>] [--columns <path>] [--batch-size 10]
                       [--output-dir <path>] [--resume <timestamp>] [--dry-run]
```

  - `--dry-run`: Dify を呼ばずに、リクエストの内容だけを出力する。
  - `--resume`: R-40 のとおり。
- R-50: 出力先は `<ローカル作業フォルダ>/outputs/{timestamp}/`(timestamp は `YYYYMMDD_HHMMSS`)。ローカル作業フォルダが無い場合は、リポジトリの `outputs/v2/{timestamp}/`。

| ファイル | 内容 |
|---|---|
| `raw/batch_{nnn}_request.json`, `raw/batch_{nnn}_response.json` | 層1(Dify への入力と生の応答。再試行分も含む) |
| `repairs.csv`, `claims.csv`, `environments.csv`, `extra_findings.csv` | 層2 |
| `final.csv` | 層3(Tableau 用) |
| `error_repairs.json` | エラーの修理の入力(再実行用) |
| `validation_issues.csv` | R-34 の問題の一覧 |
| `run_meta.json` | 実行メタ情報(R-51) |

- R-51: `run_meta.json` には次を記録する。
  - 実行日時、入力ファイルのパス、再実行元の timestamp(あれば)
  - YAML の `version` と `sha256`、プロンプトファイルの `sha256`
  - 件数(入力・除外・ok・warning・error)、除外の理由別の件数
  - バッチ数、再試行の件数、所要時間、トークン数(Dify が返す場合)
- R-52: Dify の接続情報は、`.env` の `DIFY_BASE_URL`、`DIFY_API_KEY` から読む。社内の証明書は `REQUESTS_CA_BUNDLE` で指定できるようにする。
- R-53: Dify の呼び出しは、タイムアウト・5xx・接続エラーのときに最大3回リトライする(指数バックオフ)。401/403 はリトライしない。

## 10. 評価と報告

### 10.1 精度評価

- R-54: 正解データは2種類に対応する。

**簡易版(修理単位)**: すぐに用意できる過去の分類結果を使う。

| 列 | 内容 |
|---|---|
| `repair_id` | |
| `representative_name` | 過去に分類した代表故障の**名称**(修理者確認後の修理内容)。メーカー責任でない修理は空欄 |

**詳細版(申告単位)**: 用意できたときに使う。

| 列 | 内容 |
|---|---|
| `repair_id`, `sub_id` | 申告表と同じキー |
| `user_code`, `reproduction`, `repair_code` | 正解値(空欄の項目は評価しない) |
| `needs_internal_comment` | 内部コメントを読まないと正しく分類できない場合に `1`(仕様メモ第10節) |
| `note` | メモ |

- R-55a(名称→コードの変換、2026-11-02 追加): 過去の分類結果の名称は、YAML のコード名と表記が少し違う(半角カナなど)。そのため、次の順でコードに変換する。
  1. 両方の名称を正規化して比べる。
     - Unicode の NFKC 正規化(半角カナ→全角、全角英数→半角)
     - 空白の除去
     - 記号のゆれの統一(`/`・`／`・`・` など)
  2. 正規化しても一致しない名称は、対応表 `eval_name_map.csv`(列: `product_type`, `past_name`, `code`)で変換する。対応表は Windows 側で人が作る。
  3. どちらでも変換できない名称は、評価から外す。あわせて、「変換できなかった名称と件数」の一覧を出力する。人はこの一覧を見て対応表に追記する。
  - 製品種別は、実行結果の `repair_id` から取得する(名称は製品ごとに変換する)。
- R-55: `python -m repclass.evaluate --gold <正解CSV> --run <実行フォルダ>` を提供する。正解CSVの列から、簡易版か詳細版かを自動で判別する。
  - 簡易版: 次の2つを出力する。
    - **YES/NO の一致率**: 正解の代表故障が空欄なら NO、入っていれば YES とみなし、こちらの `manufacturer_repair` と比べる。
    - **代表故障の一致率**: 両方が YES の修理で、`representative_code` が一致する割合。
    - 不一致の一覧(CSV)は、次の種類に分ける。
      - 両方に代表故障があり、コードが違う
      - 正解にだけある(こちらは NO)
      - こちらにだけある(正解は NO)
  - 詳細版: 項目ごとの一致率と、不一致の一覧(CSV)を出力する。
  - `status = error` の修理は評価から外し、件数だけを表示する。
  - 結果は画面に要約を表示し、詳細は `outputs/` に保存する。Windows 側で人が要約を読み、必要な点をメモに書けるようにするため(第10.2節)。

### 10.2 Windows 側からの報告

- R-56: 仕様と食い違う点やテストが通らない点は、**人が短くメモできる形**で Mac 側に伝える。
  - 例: 「R-43: 引き継ぎで②の repair_code が空になる。例: ①電源入らない ②①と同原因」
  - 書く内容: 該当する要件 ID、現象(1〜2行)、架空の短い例。実データの内容は書かない。
  - 伝え方: ユーザが、このチャット(Mac 側)に書き込む。
- R-57: テストやコマンドの出力は、メモしやすいように短く要約された形で表示する。
  - 例: 失敗したテスト名と要件 ID の一覧。長い出力は `--verbose` を付けたときだけ表示する。

## 11. 確認事項

### 11.1 決定済み(2026-11-02)

| 項目 | 決定 |
|---|---|
| Q1 修理者が確認した故障内容 | 確認できた行(再現・一部再現)の `repair_code` + 追加の発見のみ。YES/NO と代表故障もこれを対象にする(R-46〜R-48) |
| Q2 「ご指摘外の現象」 | ユーザコメント側に、修理者が見つけた故障として書かれたもの。`reproduced` として扱う(R-31) |
| Q3 雨による水濡れ | 案A。水濡れは常にユーザ起因とする(R-17) |
| Q4 確信度 | 出力させない(R-32) |
| 再現しない行のコード | 「同原因」の行の `repair_code` は、その行自身の `user_code` とする(R-43) |
| Parquet | 出力しない(R-10) |
| pandas | 必要なら使ってよい(R-09) |
| Q5 過去の分類結果 | 名称で入っており、表記が少し違う。正規化と対応表でコードに変換する(R-55a)。メーカー責任でない修理は空欄。代表故障は修理者確認後の内容 |
| Q6 エラーの自動再試行 | 1件ずつ1回だけ再試行する(R-36) |
| Q7 Windows 側への更新 | GitHub から全体をダウンロードする。上書きを防ぐため、Windows 側で変更するファイルはコードとは別のローカル作業フォルダに置く(R-05a) |

### 11.2 要確認

- なし(2026-11-02 時点)

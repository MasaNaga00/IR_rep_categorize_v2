# Dify ワークフロー構築手順書(v2)

- 作成日: 2026-11-02
- 対象: 要件定義書 `docs/20261101_requirements.md` の R-29〜R-32、R-52、R-53
- 旧方式(旧リポジトリ IR_rep_categorize2)の手順書との違い: 製品ごとの if/else 分岐をやめ、**共通のプロンプト1つ**にする。コード一覧は呼び出しのたびに変数で渡す(仕様メモ第16.2節)。

---

## 1. 全体構成

```
[開始ノード]  product_name / code_list / records
     ↓
[LLM ノード]  SYSTEM: system_prompt.md(product_name・code_list を変数挿入)
              USER:   records
     ↓
[終了ノード]  result = LLM の出力テキスト
```

### 1.1 入力変数(開始ノード)

| 変数名 | フィールドタイプ | 必須 | 最大長 | 内容 |
|---|---|---|---|---|
| `product_name` | 短いテキスト | ✓ | 100 | 製品の表示名(例: ミラーレスカメラ) |
| `code_list` | 段落 | ✓ | 30000 | コード一覧(1行1コード: `コード \| 名称 \| 説明文`) |
| `records` | 段落 | ✓ | 50000 | 修理の JSON 配列(文字列) |

- 変数名は上のとおりにすること(Python 側がこの名前で送る)。
- 最大長が足りないと Dify がエラーを返す。コードを追加して `code_list` が長くなったら最大長を増やす。

### 1.2 出力変数(終了ノード)

| 変数名 | 内容 |
|---|---|
| `result` | LLM の出力テキスト(JSON 文字列)。Python 側がパース・検証する |

## 2. 作成手順

### 2.1 アプリケーションの作成
1. Dify の「スタジオ」→「アプリを作成」→「ワークフロー」を選ぶ。
2. 名前の例: `repair-classify-v2`

### 2.2 開始ノード
1.1 の表のとおりに3つの変数を追加する。

### 2.3 LLM ノード
- モデル: 社内で利用可能なモデル(旧方式では GPT-4o)
- Temperature: `0`(同じ入力でなるべく同じ結果にするため)
- 最大トークン数: 8000 以上(10修理のバッチで、申告が多い場合に足りるように)
- Response Format: **JSON Object**(利用できる場合)
  - JSON Mode では、プロンプトに「JSON」という単語が必要。`system_prompt.md` には含まれている。
- SYSTEM:
  1. ローカル作業フォルダの `prompts/system_prompt.md` を開き、`---` の行より**下**をすべて貼り付ける。
  2. 本文中の `{{product_name}}` と `{{code_list}}` を消し、同じ場所に Dify の変数挿入(`{` を入力すると出る候補)で、開始ノードの `product_name` と `code_list` を挿入する。
- USER: 開始ノードの `records` だけを変数挿入する。

### 2.4 終了ノード
- 出力変数 `result` を追加し、値に LLM ノードの `text` を選ぶ。

### 2.5 公開と API キー
1. 右上の「公開」を押す。
2. 「API アクセス」で API キー(`app-` で始まる)を発行する。
3. ローカル作業フォルダの `.env` に設定する。

```
DIFY_BASE_URL=https://<Dify のホスト>/v1
DIFY_API_KEY=app-xxxxxxxx
```

- `DIFY_BASE_URL` は `/v1` までを書く(`/workflows/run` は書かない)。
- 社内の証明書が必要な場合は、`.env` に `REQUESTS_CA_BUNDLE=<証明書ファイルのパス>` を追加する。

## 3. 動作確認

### 3.1 管理画面でのテスト
1. Python 側でリクエストの中身を作る(Dify は呼ばない)。

```
python repclass_cli.py run --input tests\fixtures\synthetic\repairs.csv --local-dir C:\work\repclass_local --dry-run
```

2. 実行フォルダの `raw\batch_001_request.json` を開き、`inputs` の3つの値を、Dify のテスト実行画面の3つの入力欄にそれぞれ貼り付けて実行する。
3. `result` が `{"results": [...]}` の形になり、10修理分の結果が入っていることを確認する。

### 3.2 架空データでの通し確認
架空データ(35件、うち2件は除外される想定)で、Python から Dify を呼んで評価する。

```
python repclass_cli.py run --input tests\fixtures\synthetic\repairs.csv --local-dir C:\work\repclass_local
python repclass_cli.py evaluate --gold tests\fixtures\synthetic\expected_claims.csv --run C:\work\repclass_local\outputs\<timestamp> --local-dir C:\work\repclass_local
```

- 目安: error が 0 件、`user_code`・`reproduction`・`repair_code` の一致率が高いこと。
- 架空データの各シナリオのねらいは `tests/fixtures/synthetic/README.md` にある。一致しなかったシナリオを見て、プロンプトを調整する。

## 4. トラブルシューティング

| 現象 | 確認すること |
|---|---|
| `api_error`(401/403) | API キー、`DIFY_BASE_URL` の `/v1` |
| `api_error`(タイムアウト) | バッチを小さくする(`--batch-size 5`) |
| `parse_error` | Response Format を JSON Object にする。LLM が説明文を付けていないか `raw\*_response.json` で確認 |
| `count_mismatch` | 申告の件数が合わない。プロンプトの「ちょうど failure_count 件」の指示が守られているか |
| `unknown_code` | 分類コードにないコードを返している。`code_list` が最後まで渡っているか(最大長)を確認 |
| `missing_repair` | 最大トークン数が足りず途中で切れている可能性。最大トークン数を増やすか、バッチを小さくする |

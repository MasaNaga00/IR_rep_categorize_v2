# 架空テストデータの生成スクリプト(Mac 側の開発用)

`tests/fixtures/` の架空データとテスト専用 YAML を作り直すためのスクリプト。Windows 側では使わない。

## シナリオを追加・変更する手順

1. `gen_synthetic.py` の `add("T0xx", ...)` を追加・修正する。
   - 引数: ID, 製品, パターン名, ねらい, ユーザコメント, 修理者コメント, 申告の期待値のリスト, env=環境要因, extra=追加の発見, i1=内部コメント1, note=補足
   - 申告の期待値: `(sub_id, user_code, reproduction, basis, ref_sub_id, repair_code)`
   - 新しいメーカー責任ではないコードを使う場合は、`NON_MFR` に追加する(生成後に YAML と照合する)。
2. リポジトリの直下で、次の順に実行する(pyyaml が必要)。
   ```
   python tools/fixture_gen/gen_synthetic.py tests/fixtures/synthetic
   python tools/fixture_gen/gen_readme.py tests/fixtures/synthetic
   python tools/fixture_gen/gen_mock.py tests/fixtures/synthetic
   python tools/fixture_gen/gen_codebook_fixture.py .
   ```
   - `gen_codebook_fixture.py` は、`config/classification_codes.yaml` から、架空データで使うコードと必須コードを抜き出して `tests/fixtures/codebook_test.yaml` を作る。製品を追加した場合は、スクリプト内の製品の一覧(`used`、`ROLE`、`extra_needed`、製品のループ)にも追加する。
   - `gen_readme.py` の作成日の行に、追加した内容を追記する。
3. 件数に依存するテスト(`tests/v2/test_llm_request.py`、`test_pipeline.py`)と、手順書の件数(架空データの件数、dry-run の表示例)を更新する。
4. `python -m pytest tests/v2 -q` で全件通ることを確認する。

## 架空 LLM 応答(`mock_llm_results.json`)の作り方
- `expected_claims.csv` などから「理想の LLM 応答」を作る。
- ただし、Python 側のルールを確かめるため、次の2点はわざと期待値と違う値にしている。
  - 同原因の行: 再現を「reproduced」、repair_code を空にする(Python が引き継ぐ)
  - 番号飛びの行: 仮の値にする(Python が NO_CLAIM に置き換える)

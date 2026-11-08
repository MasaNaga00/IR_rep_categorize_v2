# 修理データ分類パイプライン v2(LLM方式)

カメラ等の修理データ(ユーザコメント・修理者コメント)を LLM(Dify 経由)で分類し、修理ごとに次の情報を出力する。

- ユーザが申告した故障内容
- 申告のうち、修理者が確認できたもの
- 修理者が確認した故障内容
- メーカー責任修理を含むか(YES/NO)
- 代表故障

旧方式(①②の機械分割)からの移行版。旧方式のコードは旧リポジトリ `IR_rep_categorize2` に残している。

## 文書

| 文書 | 内容 |
|---|---|
| `docs/handoff_v2/20261106_chat_handoff.md` | **開発の引き継ぎ資料**(現状・残課題・次の作業。新しいチャットで最初に読む) |
| `docs/20261101_requirements.md` | **要件定義書(正本)**。要件 ID(R-xx) |
| `docs/20261030_llm-classification-spec.md` | 仕様メモ(決定の経緯) |
| `docs/handoff_v2/20261102_windows_steps_detailed.md` | Windows 側の作業手順(担当者向け) |
| `docs/handoff_v2/20261108_windows_update_steps.md` | Windows 側の更新手順(2026-11-08 版: メーカー責任の判定の修正、注記の除去) |
| `docs/handoff_v2/20261102_windows_handoff.md` | Windows 側の作業ルール(担当者と GPT。GPT はチャットだけで使う) |
| `docs/handoff_v2/20261103_ai_prompt_templates.md` | 分類の定義を GPT と直すときの依頼文のひな形(ファイルはアップロードして渡し、変更は担当者が当てる) |
| `docs/dify/v2_workflow_setup.md` | Dify ワークフローの構築手順 |
| `tests/fixtures/synthetic/README.md` | 架空テストデータのシナリオ一覧 |
| `docs/20261101_responsibility-set.csv` | 全コードの責任区分の決定記録(2026-11-01) |

## 構成

```
repclass_cli.py              起動用スクリプト(init / check / run / evaluate / codes-export / codes-import)
src/repclass/                プログラム本体
config/
  classification_codes.yaml  コード体系の初期値
  input_columns.yaml         入力 CSV の列の対応づけの初期値
  comment_preprocess.yaml    修理者コメントから取り除く注記のマークの初期値(2026-11-08 追加)
  prompts/v2/system_prompt.md  Dify に貼り付けるプロンプトの初期値
tests/v2/                    テスト(テスト名に要件 ID)
tests/fixtures/              テスト専用のコード体系と架空データ
tools/fixture_gen/           架空データ・テスト用 YAML の生成スクリプト(Mac 開発用)
requirements.txt             実行に必要なライブラリ
requirements-dev.txt         テストに必要なライブラリ
```

## 使い方(概要)

詳しくは `docs/handoff_v2/20261102_windows_steps_detailed.md`。

```
python -m venv .venv
.venv\Scripts\activate          (Mac: source .venv/bin/activate)
pip install -r requirements-dev.txt
python -m pytest tests/v2 -q

python repclass_cli.py init  --local-dir <ローカル作業フォルダ>
python repclass_cli.py check --local-dir <ローカル作業フォルダ>
python repclass_cli.py run   --input <CSV(UTF-8)> --local-dir <ローカル作業フォルダ> [--dry-run] [--resume <timestamp>]
python repclass_cli.py evaluate --gold <正解CSV> --run <実行フォルダ> --local-dir <ローカル作業フォルダ>
python repclass_cli.py codes-export --local-dir <ローカル作業フォルダ>              (YAML → Excel)
python repclass_cli.py codes-import --local-dir <ローカル作業フォルダ> --xlsx <Excel>  (Excel → YAML)
```

- Windows 側で変更するファイル(YAML・プロンプト・接続情報・データ・結果)は、コードとは別の**ローカル作業フォルダ**に置く(要件 R-05a)。
- 動作環境: Python 3.13 以上。

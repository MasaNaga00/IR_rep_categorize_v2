import csv, json, sys
from pathlib import Path
D = Path(sys.argv[1])
sc = json.load(open(D/"_scenarios.json", encoding="utf-8"))
def load(n):
    out = {}
    for r in csv.DictReader(open(D/n, encoding="utf-8-sig")):
        out.setdefault(r["repair_id"], []).append(r)
    return out
claims, env, ext = load("expected_claims.csv"), load("expected_environments.csv"), load("expected_extra_findings.csv")
fin = {r["repair_id"]: r for r in csv.DictReader(open(D/"expected_final.csv", encoding="utf-8-sig"))}
JP = {"reproduced":"再現","partial":"一部再現","not_reproduced":"再現せず","not_mentioned":"記載なし","out_of_scope":"対象外","request_only":"依頼のみ"}
L = ["# 架空テストデータ(v2)", "",
"- 作成日: 2026-11-02(同日更新: 実データの書きぶりに合わせてコメントを修正、T030〜T035 を追加 / 2026-11-03: 設定・操作起因の T036・T037、現象未確認とユーザ提出の証左の T038〜T040、レンズ表面と内部の T041〜T043、コンパクトカメラ(DC)の T044・T045 を追加 / 2026-11-08: 実データの5つの例を言い換えた T046〜T053(環境要因の否定、製品実力、後付けの注記、外から触れる部分の汚れ)を追加。追加の発見を判断に使わない変更で T017 の期待値を NO に変更 / 同日 第2弾: T054〜T058(LENS の動作不良、SDカードが原因、背面操作部のゴム欠損、電源スイッチ部のまとめ書き)を追加)",
"- 目的: 要件定義書(`docs/20261101_requirements.md`)の各ルールを、実データを使わずに確かめるための架空の修理データ。",
"- 使い道:",
"  - Mac 側: ロジックのテスト(架空の LLM 応答と組み合わせる)",
"  - Windows 側: Dify ワークフローとプロンプトの動作確認。`expected_claims.csv` は詳細版の正解ファイル(R-54)と同じ形式なので、`repclass.evaluate` でそのまま評価できる。",
"- 期待値: `expected_claims.csv` などは、仕様メモと要件定義の判断ルールに基づく**理想の分類結果**。`expected_final.csv` は、それに R-46〜R-48 を適用した結果。",
"- 書きぶりの参考にした実データの特徴(ユーザ談):",
"  - 実際のコメントは長めで、丸数字の前に全体の前置き(「ショック品」「メンテナンスで入庫しましたが、修理に移行しました」など)が付くことがある。",
"  - 【】の使い方: `②hogehoge【ご指摘外の現象】`、`部品【基板ユニット】を交換`、`【修理上限金額：100000円】`、`【オーバーホール】①…②…`",
"  - よく出る表現: 「関連箇所を点検いたしましたが、異常はございませんでした。」(再現せず)、「メカの不具合により、ご指摘の現象が発生していたため、不具合箇所を含む部品を交換しました。」、「※作業に伴いカメラ設定を初期化しました※最新ファームウエアに更新しました（Ver.x→y）」(付随作業)",
"",
"## ファイル", "",
"| ファイル | 内容 |", "|---|---|",
"| `repairs.csv` | 入力(実データと同じ列構成) |",
"| `expected_claims.csv` | 申告表の期待値(詳細版の正解ファイル形式 + basis / ref_sub_id) |",
"| `expected_environments.csv` | 環境要因表の期待値 |",
"| `expected_extra_findings.csv` | 追加の発見表の期待値 |",
"| `expected_final.csv` | 最終出力の期待値 |",
"| `expected_excluded.csv` | 処理対象から除外される行 |",
"| `_scenarios.json` | シナリオ定義(この README の元データ) |",
"", "## シナリオ一覧", ""]
for s in sc:
    L += [f"### {s['id']} {s['pattern']}({s['prod']})", "", f"- ねらい: {s['aim']}",
          f"- ユーザ: {s['user'] or '(空欄)'}", f"- 修理者: {s['repair']}"]
    if s["i1"]: L.append(f"- 内部コメント1: {s['i1']}")
    rid = s["id"]
    if rid in fin:
        L.append("- 期待される申告表:")
        for c in claims[rid]:
            ref = f"(参照先: {c['ref_sub_id']})" if c["ref_sub_id"] else ""
            L.append(f"  - {c['sub_id']}: ユーザ視点 {c['user_code']} / {JP[c['reproduction']]} / 根拠 {c['basis']}{ref} / 修理者視点 {c['repair_code'] or '(空)'}")
        for e in env.get(rid, []):
            L.append(f"- 環境要因: {e['factor']}(記述: {e['source']}、通常では考えづらい使用: {e['abnormal_use']}、ユーザ起因: {e['user_caused']})")
        for e in ext.get(rid, []):
            L.append(f"- 追加の発見: {e['description']} → {e['repair_code']}")
        f = fin[rid]
        L.append(f"- 期待される最終出力: メーカー責任修理 **{f['manufacturer_repair']}** / 代表故障 {f['representative_code'] or '(空)'}")
    if s["note"]: L.append(f"- 補足: {s['note']}")
    L.append("")
(D/"README.md").write_text("\n".join(L), encoding="utf-8")
print("README lines", len(L))

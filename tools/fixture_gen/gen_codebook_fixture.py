import csv, sys, yaml
from pathlib import Path
root = Path(sys.argv[1])
src = yaml.safe_load(open(root/"config/classification_codes.yaml", encoding="utf-8"))
used = {"ML": set(), "LENS": set(), "DC": set()}
prod = {r["repair_id"]: r["product_type"] for r in csv.DictReader(open(root/"tests/fixtures/synthetic/expected_final.csv", encoding="utf-8-sig"))}
for f, cols in (("expected_claims.csv", ("user_code","repair_code")), ("expected_extra_findings.csv", ("repair_code",))):
    for r in csv.DictReader(open(root/f"tests/fixtures/synthetic/{f}", encoding="utf-8-sig")):
        for c in cols:
            if r[c] and r[c] != "NO_CLAIM": used[prod[r["repair_id"]]].add(r[c])
ROLE = {"M047":"connected_device","M046":"other","M_UNK":"unknown","L037":"connected_device","L036":"other","L_UNK":"unknown","D046":"connected_device","D048":"other","D_UNK":"unknown"}
extra_needed = {"ML": {"M042","M043","M044","M045","M046","M047","M_UNK","M012","M015"}, "LENS": {"L032","L035","L036","L037","L_UNK"}, "DC": {"D042","D043","D045","D046","D048","D_UNK"}}
def code_entry(v, code):
    e = {"name": v["name"], "description": " ".join(str(v["description"]).split()),
         "record_type": v["record_type"], "responsibility": v["responsibility"]}
    if code in ROLE: e["role"] = ROLE[code]
    return e
out = {"meta": {"version": "0.3.0-test", "description": "テスト専用のコード体系(実データ用 YAML とは独立。R-05)"},
       "product_categories": {}}
for pid, prefix in (("ML","M"),("LENS","L"),("DC","D")):
    fc = src["product_categories"][pid]["failure_categories"]
    keep = sorted(used[pid] | extra_needed[pid], key=lambda c: (c.endswith("_UNK"), c))
    out["product_categories"][pid] = {"name": src["product_categories"][pid]["name"], "code_prefix": prefix,
        "failure_categories": {c: code_entry(fc[c], c) for c in keep}}
out["product_categories"]["STB"] = {
    "name": "ストロボ(テスト用の架空製品)", "code_prefix": "S",
    "environment_factors_override": {
        "battery_leak": {"name": "電池の液漏れ", "description": "乾電池の液漏れによる腐食。", "always_user_caused": True},
        "heat": {"always_user_caused": True},
    },
    "failure_categories": {
        "S001": {"name": "発光不良", "description": "発光しない、光量が足りない。", "record_type": "failure", "responsibility": "manufacturer"},
        "S002": {"name": "クリーニング", "description": "清掃作業を行った修理データ。", "record_type": "service", "responsibility": "user_or_unknown"},
        "S003": {"name": "接続機器要因", "description": "接続したカメラ側に原因がある。", "record_type": "failure", "responsibility": "user_or_unknown", "role": "connected_device"},
        "S004": {"name": "その他", "description": "その他。", "record_type": "failure", "responsibility": "manufacturer", "role": "other"},
        "S_UNK": {"name": "判定不能", "description": "情報不足。", "record_type": "unknown", "responsibility": "user_or_unknown", "role": "unknown"},
    }}
env = {}
for k, v in src["environment_factors"].items():
    if k in ("none", "unknown"): continue
    env[k] = {"name": v["name"], "description": " ".join(str(v["description"]).split()),
              "always_user_caused": k in ("impact", "water")}
out["environment_factors"] = env
out["claim_reproduction_statuses"] = {
    "reproduced": {"name": "再現", "description": "修理者が症状を確認した(原因・処置の記載、ユーザ提出の証左での確認を含む)。", "counts_as_confirmed": True},
    "partial": {"name": "一部再現", "description": "条件付き、または一部の症状だけ再現。", "counts_as_confirmed": True},
    "not_reproduced": {"name": "再現せず", "description": "確認したが症状を確認できなかった。予防交換、エラー履歴のみ・推定交換を含む。", "counts_as_confirmed": False},
    "not_mentioned": {"name": "記載なし", "description": "再現の有無が読み取れない。", "counts_as_confirmed": False},
    "out_of_scope": {"name": "対象外", "description": "別の機器で対応など、この製品では扱っていない。", "counts_as_confirmed": False},
    "request_only": {"name": "依頼のみ", "description": "点検・清掃などの依頼で、不具合の訴えがない。", "counts_as_confirmed": False},
}
dst = root/"tests/fixtures/codebook_test.yaml"
with open(dst, "w", encoding="utf-8") as f:
    f.write("# テスト専用のコード体系(R-05)。実データ用の config/classification_codes.yaml とは独立。\n")
    f.write("# 生成元: 2026-11-02 時点の config/classification_codes.yaml から、架空データで使うコードと必須コードを抜粋し、\n")
    f.write("# v2 で追加するキー(code_prefix, role, always_user_caused, claim_reproduction_statuses)を付与。STB は架空製品。\n")
    yaml.safe_dump(out, f, allow_unicode=True, sort_keys=False, width=200)
print({k: len(v["failure_categories"]) for k, v in out["product_categories"].items()})

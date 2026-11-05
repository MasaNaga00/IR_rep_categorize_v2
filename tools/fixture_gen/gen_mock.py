import csv, json, sys
from pathlib import Path
D = Path(sys.argv[1])
sc = {s["id"]: s for s in json.load(open(D/"_scenarios.json", encoding="utf-8"))}
def load(n):
    out = {}
    for r in csv.DictReader(open(D/n, encoding="utf-8-sig")):
        out.setdefault(r["repair_id"], []).append(r)
    return out
claims, env, ext = load("expected_claims.csv"), load("expected_environments.csv"), load("expected_extra_findings.csv")
res = {}
for rid, cl in claims.items():
    s = sc[rid]
    out_claims = []
    for c in cl:
        if c["user_code"] == "NO_CLAIM":
            # 番号飛び: LLM は仮の値を返す想定。Python が NO_CLAIM に置き換える(R-42)
            out_claims.append({"sub_id": int(c["sub_id"]), "user_excerpt": "", "user_code": "M_UNK",
                               "reproduction": "not_mentioned", "basis": "none", "ref_sub_id": None,
                               "repair_code": None, "repair_excerpt": ""})
            continue
        same = c["basis"] == "same_cause"
        out_claims.append({
            "sub_id": int(c["sub_id"]),
            "user_excerpt": s["user"],
            "user_code": c["user_code"],
            # 同原因: LLM は「再現」と仮に返し、repair_code は空。Python が引き継ぐ(R-43)
            "reproduction": "reproduced" if same else c["reproduction"],
            "basis": c["basis"],
            "ref_sub_id": int(c["ref_sub_id"]) if c["ref_sub_id"] else None,
            "repair_code": None if same else (c["repair_code"] or None),
            "repair_excerpt": s["repair"] if c["repair_code"] else "",
        })
    res[rid] = {
        "repair_id": rid,
        "claims": out_claims,
        "environment": [{"factor": e["factor"], "source": e["source"], "abnormal_use": e["abnormal_use"] == "true", "excerpt": ""} for e in env.get(rid, [])],
        "extra_findings": [{"description": e["description"], "repair_code": e["repair_code"], "excerpt": ""} for e in ext.get(rid, [])],
    }
(D/"mock_llm_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(res))

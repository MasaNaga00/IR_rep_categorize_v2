"""R-46〜R-48: 最終出力(修理単位)の判断ルール。"""
from __future__ import annotations

from .codebook import Codebook
from .constants import NO_CLAIM, NO_CLAIM_NAME, SEP, STATUS_ERROR
from .tables import Tables

FINAL_COLUMNS = [
    "repair_id", "product_type", "failure_count", "status", "error_reason",
    "user_claim_codes", "user_claim_names", "confirmed_claim_codes", "confirmed_claim_names",
    "repair_confirmed_codes", "repair_confirmed_names", "user_caused_env", "user_caused_factors",
    "manufacturer_repair", "representative_code", "representative_name",
]


def judge_repairs(tables: Tables, codebook: Codebook) -> list[dict]:
    claims: dict[str, list[dict]] = {}
    for c in tables.claims:
        claims.setdefault(c["repair_id"], []).append(c)
    envs: dict[str, list[dict]] = {}
    for e in tables.environments:
        envs.setdefault(e["repair_id"], []).append(e)
    extras: dict[str, list[dict]] = {}
    for x in tables.extra_findings:
        extras.setdefault(x["repair_id"], []).append(x)
    confirmed = codebook.confirmed_statuses()

    out = []
    for r in tables.repairs:
        rid, pid = r["repair_id"], r["product_type"]
        row = {k: "" for k in FINAL_COLUMNS}
        row.update(repair_id=rid, product_type=pid, failure_count=r["failure_count"],
                   status=r["status"], error_reason=r["error_reason"])
        if r["status"] == STATUS_ERROR:
            row["user_caused_env"] = None
            out.append(row)
            continue

        def name(code: str) -> str:
            return NO_CLAIM_NAME if code == NO_CLAIM else codebook.code_name(pid, code)

        def join(codes):
            return SEP.join(codes), SEP.join(name(c) for c in codes)

        cl = sorted(claims.get(rid, []), key=lambda c: c["sub_id"])
        conf = [c for c in cl if c["reproduction"] in confirmed]
        xs = sorted(extras.get(rid, []), key=lambda x: x["seq"])
        user_codes = [c["user_code"] for c in cl]
        conf_codes = [c["user_code"] for c in conf]
        repair_codes = [c["repair_code"] for c in conf if c["repair_code"]] + [x["repair_code"] for x in xs if x["repair_code"]]
        factors = []
        for e in envs.get(rid, []):
            if e["user_caused"] and e["factor"] not in factors:
                factors.append(e["factor"])
        user_caused = bool(factors)
        yes = (not user_caused) and any(codebook.is_manufacturer(pid, c) for c in repair_codes)
        rep = ""
        if yes:
            rep = next((c["repair_code"] for c in conf if c["repair_code"] and codebook.is_manufacturer(pid, c["repair_code"])), "")
            if not rep:
                rep = next((x["repair_code"] for x in xs if codebook.is_manufacturer(pid, x["repair_code"])), "")
        row["user_claim_codes"], row["user_claim_names"] = join(user_codes)
        row["confirmed_claim_codes"], row["confirmed_claim_names"] = join(conf_codes)
        row["repair_confirmed_codes"], row["repair_confirmed_names"] = join(repair_codes)
        row["user_caused_env"] = user_caused
        row["user_caused_factors"] = SEP.join(factors)
        row["manufacturer_repair"] = "YES" if yes else "NO"
        row["representative_code"] = rep
        row["representative_name"] = name(rep) if rep else ""
        out.append(row)
    return out

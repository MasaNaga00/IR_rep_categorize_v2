"""R-41〜R-45: 中間データ(4表)の作成と、Python 側で機械的に適用するルール。"""
from __future__ import annotations

from dataclasses import dataclass, field

from .codebook import Codebook
from .constants import NO_CLAIM, STATUS_ERROR, STATUS_OK, STATUS_WARNING
from .failure_count import count_failures
from .llm_response import ValidationIssue


@dataclass
class Tables:
    repairs: list[dict] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    environments: list[dict] = field(default_factory=list)
    extra_findings: list[dict] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)


def is_user_caused(factor: str, abnormal_use, product_id: str, codebook: Codebook) -> bool:
    """R-44: always_user_caused が真、または abnormal_use が真ならユーザ起因。"""
    info = codebook.environment_factors(product_id).get(factor)
    return bool(info and info.always_user_caused) or abnormal_use is True


def _build_claims(rid: str, result: dict, missing: set[int]) -> tuple[list[dict], list[ValidationIssue]]:
    rows: dict[int, dict] = {}
    for c in result.get("claims") or []:
        sub = c["sub_id"]
        if sub in missing:   # R-42 番号飛び
            rows[sub] = {"repair_id": rid, "sub_id": sub, "user_excerpt": "", "user_code": NO_CLAIM,
                         "reproduction": "not_mentioned", "basis": "none", "ref_sub_id": None,
                         "repair_code": "", "repair_excerpt": "", "inherited": False}
            continue
        rows[sub] = {
            "repair_id": rid, "sub_id": sub,
            "user_excerpt": c.get("user_excerpt") or "",
            "user_code": c.get("user_code") or "",
            "reproduction": c.get("reproduction") or "",
            "basis": c.get("basis") or "none",
            "ref_sub_id": c.get("ref_sub_id") if c.get("basis") == "same_cause" else None,
            "repair_code": c.get("repair_code") or "",
            "repair_excerpt": c.get("repair_excerpt") or "",
            "inherited": False,
        }
    issues: list[ValidationIssue] = []
    # R-43 同原因の引き継ぎ(元の値を見て決めるため、先に参照先を解決してから書き換える)
    updates: dict[int, str] = {}
    for sub, row in rows.items():
        if row["basis"] != "same_cause":
            continue
        visited = {sub}
        cur = row["ref_sub_id"]
        cycle = False
        while cur in rows and rows[cur]["basis"] == "same_cause":
            if cur in visited:
                cycle = True
                break
            visited.add(cur)
            cur = rows[cur]["ref_sub_id"]
        if cycle or cur not in rows:
            issues.append(ValidationIssue(rid, sub, "ref_cycle", "同原因の参照が循環しているため引き継ぎません", "warning"))
            continue
        updates[sub] = rows[cur]["reproduction"]
    for sub, rep in updates.items():
        rows[sub]["reproduction"] = rep
        rows[sub]["repair_code"] = rows[sub]["user_code"]
        rows[sub]["inherited"] = True
    return [rows[k] for k in sorted(rows)], issues


def build_tables(records: list[dict], results: dict[str, dict], errors: dict[str, str], codebook: Codebook,
                 warnings: dict[str, list] | None = None) -> Tables:
    warnings = warnings or {}
    t = Tables()
    for rec in records:
        rid, pid = rec["repair_id"], rec["product_type"]
        fc = count_failures(rec.get("user_comment"))
        row = {
            "repair_id": rid, "product_type": pid, "failure_count": fc.failure_count,
            # 入力どおりの全文と、注記として取り除いた文(R-67)
            "user_comment": rec.get("user_comment_original", rec.get("user_comment", "")),
            "repair_comment": rec.get("repair_comment_original", rec.get("repair_comment", "")),
            "internal_1": rec.get("internal_1", ""), "internal_2": rec.get("internal_2", ""),
            "status": STATUS_OK, "error_reason": "",
            "user_comment_notes": rec.get("user_comment_notes", ""),
            "repair_comment_notes": rec.get("repair_comment_notes", ""),
        }
        t.repairs.append(row)
        if rid in errors or rid not in results:
            row["status"] = STATUS_ERROR
            row["error_reason"] = errors.get(rid, "missing_result")
            continue
        res = results[rid]
        claims, issues = _build_claims(rid, res, set(fc.missing_numbers))
        t.claims.extend(claims)
        t.issues.extend(issues)
        for e in res.get("environment") or []:
            t.environments.append({
                "repair_id": rid, "factor": e.get("factor"), "source": e.get("source"),
                "abnormal_use": e.get("abnormal_use") is True,
                "user_caused": is_user_caused(e.get("factor"), e.get("abnormal_use"), pid, codebook),
                "excerpt": e.get("excerpt") or "",
            })
        for i, x in enumerate(res.get("extra_findings") or [], start=1):
            t.extra_findings.append({"repair_id": rid, "seq": i, "description": x.get("description") or "",
                                     "repair_code": x.get("repair_code") or "", "excerpt": x.get("excerpt") or ""})
        if issues or warnings.get(rid):
            row["status"] = STATUS_WARNING
    return t

"""R-32〜R-34: LLM 応答のパースと検証。"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from .codebook import Codebook
from .constants import BASIS_VALUES, SOURCE_VALUES


class LLMParseError(Exception):
    pass


@dataclass
class ValidationIssue:
    repair_id: str
    sub_id: int | None
    kind: str
    message: str
    severity: str = "error"   # "error" / "warning"

    def to_dict(self) -> dict:
        return asdict(self)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("results", "data", "classifications", "records"):
            if isinstance(obj.get(key), list):
                return obj[key]
    raise LLMParseError("応答に results の配列がありません")


def parse_llm_response(raw) -> list[dict]:
    if isinstance(raw, (dict, list)):
        items = _extract(raw)
    else:
        text = (raw or "").strip()
        if not text:
            raise LLMParseError("応答が空です")
        candidates = [text] + [m.group(1).strip() for m in _FENCE.finditer(text)]
        for start, end in (("{", "}"), ("[", "]")):
            i, j = text.find(start), text.rfind(end)
            if 0 <= i < j:
                candidates.append(text[i:j + 1])
        items = None
        for c in candidates:
            try:
                obj = json.loads(c)
            except (json.JSONDecodeError, ValueError):
                continue
            try:
                items = _extract(obj)
                break
            except LLMParseError:
                continue
        if items is None:
            raise LLMParseError("応答を JSON として読めません")
    if not all(isinstance(x, dict) for x in items):
        raise LLMParseError("results の要素が辞書ではありません")
    return items


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def validate_result(result: dict, request_record: dict, product_id: str, codebook: Codebook,
                    original: dict | None = None) -> list[ValidationIssue]:
    """original: 注記を取り除く前の文({"user_comment": ..., "repair_comment": ...})。抜き出しの確認では、
    取り除いた後の文(request_record)と取り除く前の文のどちらに含まれていてもよい(R-67)。"""
    rid = request_record["repair_id"]
    fc = int(request_record["failure_count"])
    missing = set(request_record.get("missing_numbers") or [])
    original = original or {}
    user_txts = [_squash(request_record.get("user_comment", ""))]
    rep_txts = [_squash(request_record.get("repair_comment", ""))]
    if original.get("user_comment"):
        user_txts.append(_squash(original["user_comment"]))
    if original.get("repair_comment"):
        rep_txts.append(_squash(original["repair_comment"]))
    statuses = codebook.claim_statuses()
    envs = codebook.environment_factors(product_id)
    issues: list[ValidationIssue] = []

    def err(sub, kind, msg):
        issues.append(ValidationIssue(rid, sub, kind, msg, "error"))

    def warn(sub, kind, msg):
        issues.append(ValidationIssue(rid, sub, kind, msg, "warning"))

    def check_excerpt(sub, value, *texts):
        v = _squash(value or "")
        if v and not any(v in t for t in texts):
            warn(sub, "excerpt_not_found", f"抜き出しが原文にありません: {value[:40]}")

    claims = result.get("claims")
    if not isinstance(claims, list):
        err(None, "count_mismatch", "claims がありません")
        claims = []
    if len(claims) != fc:
        err(None, "count_mismatch", f"claims の件数 {len(claims)} が故障数 {fc} と違います")
    seen: set[int] = set()
    for c in claims:
        sub = c.get("sub_id")
        if not isinstance(sub, int) or isinstance(sub, bool) or not 1 <= sub <= fc or sub in seen:
            err(sub if isinstance(sub, int) else None, "sub_id_invalid", f"sub_id が不正です: {sub!r}")
            continue
        seen.add(sub)
        if sub in missing:
            continue   # 番号飛びの行は Python が上書きする(R-42)
        uc = c.get("user_code")
        if not codebook.is_valid_code(product_id, uc or ""):
            err(sub, "unknown_code", f"user_code がコード体系にありません: {uc!r}")
        rc = c.get("repair_code")
        if rc not in (None, "") and not codebook.is_valid_code(product_id, rc):
            err(sub, "unknown_code", f"repair_code がコード体系にありません: {rc!r}")
        if c.get("reproduction") not in statuses:
            err(sub, "invalid_enum", f"reproduction が不正です: {c.get('reproduction')!r}")
        basis = c.get("basis")
        if basis not in BASIS_VALUES:
            err(sub, "invalid_enum", f"basis が不正です: {basis!r}")
        if basis == "same_cause":
            ref = c.get("ref_sub_id")
            if not isinstance(ref, int) or isinstance(ref, bool) or not 1 <= ref <= fc or ref == sub:
                err(sub, "ref_invalid", f"ref_sub_id が不正です: {ref!r}")
        check_excerpt(sub, c.get("user_excerpt"), *user_txts)
        check_excerpt(sub, c.get("repair_excerpt"), *rep_txts)
    for e in result.get("environment") or []:
        if e.get("factor") not in envs:
            err(None, "invalid_enum", f"環境要因が不正です: {e.get('factor')!r}")
        if e.get("source") not in SOURCE_VALUES:
            err(None, "invalid_enum", f"source が不正です: {e.get('source')!r}")
        if not isinstance(e.get("abnormal_use"), bool):
            err(None, "invalid_enum", f"abnormal_use は真偽値にしてください: {e.get('abnormal_use')!r}")
        check_excerpt(None, e.get("excerpt"), *(u + r for u in user_txts for r in rep_txts))
    for x in result.get("extra_findings") or []:
        rc = x.get("repair_code")
        if not codebook.is_valid_code(product_id, rc or ""):
            err(None, "unknown_code", f"追加の発見の repair_code がコード体系にありません: {rc!r}")
        check_excerpt(None, x.get("excerpt"), *rep_txts)
    return issues


def validate_batch(results: list[dict], request_records: list[dict], product_id: str,
                   codebook: Codebook, originals: dict[str, dict] | None = None) -> tuple[dict[str, dict], list[ValidationIssue]]:
    by_id: dict[str, dict] = {}
    for r in results:
        rid = r.get("repair_id")
        if rid is not None and str(rid) not in by_id:
            by_id[str(rid)] = r
    out: dict[str, dict] = {}
    issues: list[ValidationIssue] = []
    for rr in request_records:
        rid = rr["repair_id"]
        if rid not in by_id:
            issues.append(ValidationIssue(rid, None, "missing_repair", "応答にこの修理の結果がありません", "error"))
            continue
        out[rid] = by_id[rid]
        issues.extend(validate_result(by_id[rid], rr, product_id, codebook, (originals or {}).get(rid)))
    return out, issues

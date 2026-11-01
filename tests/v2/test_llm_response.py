"""R-32〜R-34: LLM 応答のパースと検証。"""
from __future__ import annotations

import copy
import json

import pytest

from repclass.llm_response import LLMParseError, parse_llm_response, validate_batch, validate_result


def _req(rid="R1", count=2, missing=None, user="①電源が入らない ②液晶が映らない", repair="①電源基板交換 ②①と同原因"):
    return {"repair_id": rid, "failure_count": count, "missing_numbers": missing or [], "user_comment": user, "repair_comment": repair}


def _res(rid="R1"):
    return {
        "repair_id": rid,
        "claims": [
            {"sub_id": 1, "user_excerpt": "電源が入らない", "user_code": "M001", "reproduction": "reproduced",
             "basis": "direct", "ref_sub_id": None, "repair_code": "M001", "repair_excerpt": "電源基板交換"},
            {"sub_id": 2, "user_excerpt": "液晶が映らない", "user_code": "M017", "reproduction": "reproduced",
             "basis": "same_cause", "ref_sub_id": 1, "repair_code": None, "repair_excerpt": "①と同原因"},
        ],
        "environment": [{"factor": "heat", "source": "user", "abnormal_use": False, "excerpt": ""}],
        "extra_findings": [],
    }


# --- パース(R-33) ---

@pytest.mark.parametrize("raw", [
    {"results": [_res()]},
    json.dumps({"results": [_res()]}, ensure_ascii=False),
    json.dumps([_res()], ensure_ascii=False),
    "```json\n" + json.dumps({"results": [_res()]}, ensure_ascii=False) + "\n```",
    "以下が結果です。\n```json\n" + json.dumps([_res()], ensure_ascii=False) + "\n```\n",
])
def test_r33_parse_variants(raw):
    out = parse_llm_response(raw)
    assert isinstance(out, list) and out[0]["repair_id"] == "R1"


@pytest.mark.parametrize("raw", ["これはJSONではありません", "", "{\"foo\": 1}", "123"])
def test_r33_parse_error(raw):
    with pytest.raises(LLMParseError):
        parse_llm_response(raw)


# --- 検証(R-34) ---

def _kinds(issues):
    return sorted((i.kind, i.severity) for i in issues)


def test_r34_valid_result_has_no_issues(codebook):
    assert validate_result(_res(), _req(), "ML", codebook) == []


def test_r34_count_mismatch(codebook):
    r = _res(); r["claims"].pop()
    assert ("count_mismatch", "error") in _kinds(validate_result(r, _req(), "ML", codebook))


@pytest.mark.parametrize("sub_ids", [(1, 1), (1, 3), (0, 1)])
def test_r34_sub_id_invalid(codebook, sub_ids):
    r = _res()
    for c, s in zip(r["claims"], sub_ids):
        c["sub_id"] = s
    assert ("sub_id_invalid", "error") in _kinds(validate_result(r, _req(), "ML", codebook))


@pytest.mark.parametrize("path", ["user", "repair", "extra"])
def test_r34_unknown_code(codebook, path):
    r = _res()
    if path == "user":
        r["claims"][0]["user_code"] = "L001"  # 他製品のコード
    elif path == "repair":
        r["claims"][0]["repair_code"] = "ZZZ999"
    else:
        r["extra_findings"] = [{"description": "x", "repair_code": "ZZZ999", "excerpt": ""}]
    issues = validate_result(r, _req(), "ML", codebook)
    assert ("unknown_code", "error") in _kinds(issues)


@pytest.mark.parametrize("field, value", [
    (("claims", 0, "reproduction"), "maybe"),
    (("claims", 0, "basis"), "guess"),
    (("environment", 0, "source"), "someone"),
    (("environment", 0, "factor"), "volcano"),
    (("environment", 0, "factor"), "none"),     # R-18 none は使わない
])
def test_r34_invalid_enum(codebook, field, value):
    r = _res()
    a, i, k = field
    r[a][i][k] = value
    assert ("invalid_enum", "error") in _kinds(validate_result(r, _req(), "ML", codebook))


@pytest.mark.parametrize("ref", [None, 2, 5])
def test_r34_ref_invalid(codebook, ref):
    r = _res()
    r["claims"][1]["ref_sub_id"] = ref
    assert ("ref_invalid", "error") in _kinds(validate_result(r, _req(), "ML", codebook))


def test_r34_excerpt_not_found_is_warning(codebook):
    r = _res()
    r["claims"][0]["user_excerpt"] = "存在しない文"
    issues = validate_result(r, _req(), "ML", codebook)
    assert _kinds(issues) == [("excerpt_not_found", "warning")]


def test_r34_excerpt_whitespace_and_empty_ignored(codebook):
    r = _res()
    r["claims"][0]["user_excerpt"] = "電源が 入らない"   # 空白の違いは無視
    r["claims"][1]["repair_excerpt"] = ""             # 空の抜き出しはチェックしない
    assert validate_result(r, _req(user="①電源が入らない ②液晶が映らない"), "ML", codebook) == []


def test_r34_missing_numbers_rows_are_not_checked_for_codes(codebook):
    """番号飛びの行は Python が上書きするため、LLM の値が不正でもエラーにしない(R-42)。"""
    r = _res()
    r["claims"][1].update({"user_code": "", "basis": "none", "ref_sub_id": None, "reproduction": "", "repair_code": None})
    assert validate_result(r, _req(missing=[2]), "ML", codebook) == []


def test_r34_validate_batch_missing_repair(codebook):
    reqs = [_req("R1"), _req("R2")]
    results, issues = validate_batch([_res("R1")], reqs, "ML", codebook)
    assert set(results) == {"R1"}
    assert [(i.repair_id, i.kind, i.severity) for i in issues] == [("R2", "missing_repair", "error")]


def test_r34_validate_batch_separates_errors_by_repair(codebook):
    bad = _res("R2"); bad["claims"][0]["user_code"] = "ZZZ999"
    results, issues = validate_batch([_res("R1"), bad], [_req("R1"), _req("R2")], "ML", codebook)
    assert set(results) == {"R1", "R2"}
    assert {i.repair_id for i in issues if i.severity == "error"} == {"R2"}


def test_r34_unexpected_repair_id_ignored(codebook):
    results, issues = validate_batch([_res("R1"), _res("R9")], [_req("R1")], "ML", codebook)
    assert set(results) == {"R1"}

"""R-41〜R-45: 中間データの作成と、Python 側で機械的に適用するルール。"""
from __future__ import annotations

import copy

import pytest

from repclass.constants import NO_CLAIM
from repclass.input_loader import load_input
from repclass.tables import build_tables


@pytest.fixture
def records(codebook, synth_csv):
    return load_input(synth_csv, codebook).records


@pytest.fixture
def tables(records, mock_results, codebook):
    return build_tables(records, mock_results, errors={}, codebook=codebook)


def _claims(tables, rid):
    return sorted((c for c in tables.claims if c["repair_id"] == rid), key=lambda c: c["sub_id"])


def test_r41_columns(tables):
    assert set(tables.repairs[0]) == {"repair_id", "product_type", "failure_count", "user_comment", "repair_comment",
                                      "internal_1", "internal_2", "status", "error_reason",
                                      "user_comment_notes", "repair_comment_notes"}   # R-67(2026-11-08 追加)
    assert set(tables.claims[0]) == {"repair_id", "sub_id", "user_excerpt", "user_code", "reproduction", "basis",
                                     "ref_sub_id", "repair_code", "repair_excerpt", "inherited"}
    assert set(tables.environments[0]) == {"repair_id", "factor", "source", "abnormal_use", "user_caused", "excerpt"}
    assert set(tables.extra_findings[0]) == {"repair_id", "seq", "description", "repair_code", "excerpt"}


def test_r41_claims_match_expected(tables, expected_claims):
    got = {(c["repair_id"], c["sub_id"]): c for c in tables.claims}
    assert len(got) == len(expected_claims)
    for e in expected_claims:
        c = got[(e["repair_id"], int(e["sub_id"]))]
        want = (e["user_code"], e["reproduction"], e["basis"], int(e["ref_sub_id"]) if e["ref_sub_id"] else None, e["repair_code"])
        assert (c["user_code"], c["reproduction"], c["basis"], c["ref_sub_id"], c["repair_code"]) == want, e["repair_id"]


def test_r42_missing_number_row(tables):
    c2 = _claims(tables, "T008")[1]
    assert (c2["user_code"], c2["reproduction"], c2["repair_code"]) == (NO_CLAIM, "not_mentioned", "")


def test_r43_same_cause_inherits_reproduction_and_uses_own_user_code(tables):
    c = _claims(tables, "T005")[1]
    assert (c["reproduction"], c["repair_code"], c["inherited"]) == ("reproduced", "M017", True)
    assert _claims(tables, "T005")[0]["inherited"] is False


def test_r43_not_reproduced_is_inherited(tables):
    c = _claims(tables, "T018")[1]   # LLM は「再現」と返したが、①の「再現せず」を引き継ぐ
    assert (c["reproduction"], c["inherited"]) == ("not_reproduced", True)


def test_r43_chain(tables):
    cs = _claims(tables, "T025")
    assert [c["reproduction"] for c in cs] == ["reproduced"] * 3
    assert [c["repair_code"] for c in cs] == ["M001", "M017", "M016"]


def test_r43_cycle_is_warning_and_not_inherited(records, mock_results, codebook):
    res = copy.deepcopy(mock_results)
    cl = res["T025"]["claims"]
    cl[1].update(basis="same_cause", ref_sub_id=3, reproduction="not_mentioned")
    cl[2].update(basis="same_cause", ref_sub_id=2, reproduction="not_mentioned")
    t = build_tables(records, res, errors={}, codebook=codebook)
    cs = _claims(t, "T025")
    assert [c["reproduction"] for c in cs[1:]] == ["not_mentioned", "not_mentioned"]
    assert [c["inherited"] for c in cs[1:]] == [False, False]
    assert any(i.kind == "ref_cycle" and i.repair_id == "T025" and i.severity == "warning" for i in t.issues)
    assert next(r for r in t.repairs if r["repair_id"] == "T025")["status"] == "warning"


def test_r44_user_caused(tables, expected_environments):
    got = {(e["repair_id"], e["factor"]): e["user_caused"] for e in tables.environments}
    want = {(e["repair_id"], e["factor"]): e["user_caused"] == "true" for e in expected_environments}
    assert got == want


def test_r44_override_per_product(codebook):
    from repclass.tables import is_user_caused
    assert is_user_caused("heat", False, "ML", codebook) is False
    assert is_user_caused("heat", False, "STB", codebook) is True     # 製品ごとの上書き
    assert is_user_caused("heat", True, "ML", codebook) is True
    assert is_user_caused("water", False, "ML", codebook) is True


def test_r37_r38_error_repairs_are_kept(records, mock_results, codebook):
    res = {k: v for k, v in mock_results.items() if k != "T003"}
    t = build_tables(records, res, errors={"T003": "unknown_code"}, codebook=codebook)
    row = next(r for r in t.repairs if r["repair_id"] == "T003")
    assert (row["status"], row["error_reason"]) == ("error", "unknown_code")
    assert not [c for c in t.claims if c["repair_id"] == "T003"]
    assert len(t.repairs) == len(records)


def test_r37_warning_status(records, mock_results, codebook):
    from repclass.llm_response import ValidationIssue
    w = {"T001": [ValidationIssue("T001", 1, "excerpt_not_found", "x", "warning")]}
    t = build_tables(records, mock_results, errors={}, codebook=codebook, warnings=w)
    assert next(r for r in t.repairs if r["repair_id"] == "T001")["status"] == "warning"
    assert next(r for r in t.repairs if r["repair_id"] == "T002")["status"] == "ok"

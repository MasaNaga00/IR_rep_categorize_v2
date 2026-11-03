"""R-46〜R-48: 最終出力(修理単位)の判断ルール。"""
from __future__ import annotations

import copy

import pytest

from repclass.input_loader import load_input
from repclass.judge import FINAL_COLUMNS, judge_repairs
from repclass.tables import build_tables


@pytest.fixture
def final(codebook, synth_csv, mock_results):
    recs = load_input(synth_csv, codebook).records
    return {r["repair_id"]: r for r in judge_repairs(build_tables(recs, mock_results, {}, codebook), codebook)}


def test_r46_columns():
    assert FINAL_COLUMNS == [
        "repair_id", "product_type", "failure_count", "status", "error_reason",
        "user_claim_codes", "user_claim_names", "confirmed_claim_codes", "confirmed_claim_names",
        "repair_confirmed_codes", "repair_confirmed_names", "user_caused_env", "user_caused_factors",
        "manufacturer_repair", "representative_code", "representative_name",
    ]


def test_r46_r48_all_synthetic_scenarios(final, expected_final):
    assert list(final) == list(expected_final)
    for rid, e in expected_final.items():
        f = final[rid]
        got = (f["status"], f["failure_count"], f["user_claim_codes"], f["confirmed_claim_codes"],
               f["repair_confirmed_codes"], f["user_caused_env"], f["manufacturer_repair"], f["representative_code"])
        want = (e["status"], int(e["failure_count"]), e["user_claim_codes"], e["confirmed_claim_codes"],
                e["repair_confirmed_codes"], e["user_caused_env"] == "true", e["manufacturer_repair"], e["representative_code"])
        assert got == want, rid


def test_r46_names(final):
    assert final["T008"]["user_claim_names"] == "シャッター不具合;申告なし;背面操作部不具合"
    assert final["T001"]["representative_name"] == "電源不良"
    assert final["T009"]["user_caused_factors"] == "impact"
    assert final["T002"]["representative_name"] == ""


@pytest.mark.parametrize("rid, yes, rep, why", [
    ("T013", "NO", "", "ファームアップで解消はメーカー責任ではない"),
    ("T034", "YES", "M007", "付随のファーム更新は処置ではない"),
    ("T017", "YES", "M031", "追加の発見だけで YES"),
    ("T024", "NO", "", "再現したがメーカー責任でないコード"),
    ("T030", "NO", "", "前置きのショック品"),
    ("T011", "YES", "M004", "通常の使用の高温"),
    ("T032", "YES", "M022", "予防交換は再現せず"),
    ("T036", "NO", "", "設定が原因(設定・操作起因)はメーカー責任ではない"),
    ("T037", "NO", "", "設定が原因(表示先の設定)"),
    ("T038", "NO", "", "現象未確認ならエラー履歴・推定交換があっても再現せず"),
    ("T039", "NO", "", "エラー履歴だけでは再現にしない"),
    ("T040", "YES", "M008", "ユーザ提出の証左で確認できた場合は再現"),
    ("T041", "NO", "", "前玉表面の汚れはレンズ表面(ユーザ責任)"),
    ("T042", "YES", "L028", "レンズ内部のゴミはメーカー責任"),
    ("T043", "NO", "", "内部か表面か判断できなければ表面"),
    ("T044", "YES", "D001", "コンパクトカメラのコード体系"),
    ("T045", "NO", "", "コンパクトカメラでもレンズ表面はユーザ責任"),
])
def test_r47_r48_key_cases(final, rid, yes, rep, why):
    assert (final[rid]["manufacturer_repair"], final[rid]["representative_code"]) == (yes, rep), why


def test_r37_error_rows_have_blank_judgements(codebook, synth_csv, mock_results):
    recs = load_input(synth_csv, codebook).records
    res = {k: v for k, v in mock_results.items() if k != "T003"}
    out = {r["repair_id"]: r for r in judge_repairs(build_tables(recs, res, {"T003": "api_error"}, codebook), codebook)}
    r = out["T003"]
    assert (r["status"], r["error_reason"]) == ("error", "api_error")
    for k in ("user_claim_codes", "confirmed_claim_codes", "repair_confirmed_codes", "user_caused_factors",
              "manufacturer_repair", "representative_code", "representative_name"):
        assert r[k] == "", k
    assert r["user_caused_env"] is None
    assert r["failure_count"] == 2


def test_r48_representative_prefers_smallest_confirmed_sub_id(codebook, synth_csv, mock_results):
    recs = load_input(synth_csv, codebook).records
    res = copy.deepcopy(mock_results)
    res["T003"]["claims"][0]["reproduction"] = "not_reproduced"
    res["T003"]["claims"][0]["repair_code"] = None
    out = {r["repair_id"]: r for r in judge_repairs(build_tables(recs, res, {}, codebook), codebook)}
    assert out["T003"]["representative_code"] == "M017"

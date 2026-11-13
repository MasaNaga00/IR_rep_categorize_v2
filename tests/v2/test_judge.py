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
        "extra_finding_codes", "extra_finding_names",
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
    ("T017", "NO", "", "追加の発見は判断に使わない(2026-11-08 変更)"),
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
    ("T046", "YES", "L028", "雨に気をつけていた(否定の文)は環境要因にしない"),
    ("T047", "NO", "", "修理者が水濡れ痕を確認していれば、ユーザが否定していても水濡れ"),
    ("T048", "NO", "", "製品実力の範囲内は調整していてもメーカー責任ではない"),
    ("T049", "NO", "", "仕様の範囲内も製品実力範囲内"),
    ("T050", "NO", "", "後付けの注記(バッテリーの劣化)は判断に使わない"),
    ("T051", "YES", "M028", "注記の後に続く②は残る"),
    ("T052", "NO", "", "ディスプレイオフセンサーの汚れ(清掃で解消)はユーザ責任"),
    ("T053", "NO", "", "容易に拭き取れる接点の汚れはユーザ責任"),
    ("T054", "YES", "L042", "スイッチを操作していない表示の切り替わりは動作不良"),
    ("T055", "NO", "", "SDカードの使い方が原因なら設定・操作起因"),
    ("T056", "NO", "", "SDカード自体の不良なら接続機器要因"),
    ("T057", "YES", "M026", "AF-ONボタンのゴム欠損は背面操作部不具合"),
    ("T058", "YES", "M021", "修理者が電源スイッチ部と書いていれば電源SW不具合"),
    ("T059", "YES", "M052", "純正バッテリーの不良はメーカー責任(本体に異常が無くても)"),
    ("T060", "NO", "", "バッテリーの劣化・寿命はユーザ責任"),
    ("T061", "YES", "M051", "純正充電器の不良はメーカー責任"),
    ("T062", "NO", "", "他社製の USB 充電器は接続機器要因"),
    ("T063", "YES", "D051", "純正の USB 電源アダプターは充電器不良"),
    ("T064", "NO", "", "互換バッテリーは接続機器要因"),
])
def test_r47_r48_key_cases(final, rid, yes, rep, why):
    assert (final[rid]["manufacturer_repair"], final[rid]["representative_code"]) == (yes, rep), why


def test_r46_extra_findings_are_reference_only(final):
    """2026-11-08 変更(Q16): 追加の発見は参考の列に残すが、repair_confirmed_codes・YES/NO・代表故障には使わない。"""
    t017 = final["T017"]
    assert t017["extra_finding_codes"] == "M031"
    assert t017["extra_finding_names"] == "内蔵ストロボ不具合"
    assert t017["repair_confirmed_codes"] == ""
    assert (t017["manufacturer_repair"], t017["representative_code"]) == ("NO", "")
    assert final["T001"]["extra_finding_codes"] == ""


def test_r47_extra_finding_with_manufacturer_code_does_not_make_yes(codebook, synth_csv, mock_results):
    """例3・例4: 注記を LLM が追加の発見(電源不良・その他)と読んでも、YES にならない。"""
    recs = load_input(synth_csv, codebook).records
    res = copy.deepcopy(mock_results)
    res["T050"]["extra_findings"] = [{"description": "バッテリーの劣化", "repair_code": "M001", "excerpt": ""},
                                     {"description": "防滴マウントゴムの破れ", "repair_code": "M046", "excerpt": ""}]
    out = {r["repair_id"]: r for r in judge_repairs(build_tables(recs, res, {}, codebook), codebook)}
    r = out["T050"]
    assert r["repair_confirmed_codes"] == "M013"
    assert r["extra_finding_codes"] == "M001;M046"
    assert (r["manufacturer_repair"], r["representative_code"]) == ("NO", "")


def test_r37_error_rows_have_blank_judgements(codebook, synth_csv, mock_results):
    recs = load_input(synth_csv, codebook).records
    res = {k: v for k, v in mock_results.items() if k != "T003"}
    out = {r["repair_id"]: r for r in judge_repairs(build_tables(recs, res, {"T003": "api_error"}, codebook), codebook)}
    r = out["T003"]
    assert (r["status"], r["error_reason"]) == ("error", "api_error")
    for k in ("user_claim_codes", "confirmed_claim_codes", "repair_confirmed_codes", "user_caused_factors",
              "manufacturer_repair", "representative_code", "representative_name", "extra_finding_codes"):
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

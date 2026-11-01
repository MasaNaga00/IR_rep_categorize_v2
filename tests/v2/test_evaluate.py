"""R-54〜R-55a: 精度評価。"""
from __future__ import annotations

import csv

import pytest

from repclass.evaluate import NameResolver, evaluate_detailed, evaluate_simple, main, normalize_name
from repclass.input_loader import load_input
from repclass.judge import judge_repairs
from repclass.tables import build_tables

from .conftest import SYNTH, read_csv


@pytest.fixture
def tables(codebook, synth_csv, mock_results):
    return build_tables(load_input(synth_csv, codebook).records, mock_results, {}, codebook)


@pytest.fixture
def final_rows(tables, codebook):
    return judge_repairs(tables, codebook)


@pytest.mark.parametrize("a, b", [
    ("ｼｬｯﾀｰ不具合", "シャッター不具合"),
    ("ＡＦ不良", "AF不良"),
    ("ファインダー／EVF表示不具合", "ファインダー/EVF表示不具合"),
    (" 電源 不良 ", "電源不良"),
    ("電子ダイヤル不具合(メイン)", "電子ダイヤル不具合（メイン）"),
])
def test_r55a_normalize(a, b):
    assert normalize_name(a) == normalize_name(b)


def test_r55a_resolver(codebook):
    r = NameResolver(codebook, name_map=[{"product_type": "ML", "past_name": "電源ﾌﾘｮｳ(旧)", "code": "M001"}])
    assert r.resolve("ML", "ｼｬｯﾀｰ不具合") == "M007"
    assert r.resolve("ML", "電源フリョウ(旧)") == "M001"      # 対応表も正規化して照合
    assert r.resolve("LENS", "ｼｬｯﾀｰ不具合") is None          # 製品ごとに変換
    assert r.resolve("ML", "ナゾの故障") is None


GOLD = [
    {"repair_id": "T001", "representative_name": "電源不良"},
    {"repair_id": "T003", "representative_name": "ＡＦ不良"},
    {"repair_id": "T002", "representative_name": ""},
    {"repair_id": "T009", "representative_name": "電源不良"},
    {"repair_id": "T017", "representative_name": ""},
    {"repair_id": "T005", "representative_name": "ｼｬｯﾀｰ不具合"},
    {"repair_id": "T019", "representative_name": "電源ﾌﾘｮｳ(旧)"},
    {"repair_id": "T006", "representative_name": "ナゾの故障"},
    {"repair_id": "Z999", "representative_name": "電源不良"},
]


def test_r55_simple(codebook, final_rows):
    resolver = NameResolver(codebook, name_map=[{"product_type": "ML", "past_name": "電源ﾌﾘｮｳ(旧)", "code": "M001"}])
    r = evaluate_simple(GOLD, final_rows, resolver)
    assert r.n_compared == 7
    assert r.yes_no_accuracy == pytest.approx(5 / 7)
    assert r.n_both_yes == 4
    assert r.representative_accuracy == pytest.approx(3 / 4)
    kinds = {(m["repair_id"], m["kind"]) for m in r.mismatches}
    assert kinds == {("T009", "gold_only"), ("T017", "pred_only"), ("T005", "code_differs")}
    assert r.unresolved == {("ML", "ナゾの故障"): 1}
    assert r.n_missing_in_run == 1


def test_r55_simple_skips_error_rows(codebook, final_rows):
    rows = [dict(r) for r in final_rows]
    for r in rows:
        if r["repair_id"] == "T001":
            r.update(status="error", manufacturer_repair="", representative_code="")
    res = evaluate_simple(GOLD[:2], rows, NameResolver(codebook))
    assert res.n_error_skipped == 1 and res.n_compared == 1


def test_r55_detailed_perfect(tables):
    gold = read_csv(SYNTH / "expected_claims.csv")
    r = evaluate_detailed(gold, tables.claims)
    assert r.accuracy == {"user_code": 1.0, "reproduction": 1.0, "repair_code": 1.0}
    assert r.mismatches == []


def test_r55_detailed_mismatch_and_blank_skipped(tables):
    gold = [dict(g) for g in read_csv(SYNTH / "expected_claims.csv")]
    gold[0]["user_code"] = "M999"
    gold[1]["repair_code"] = ""          # 空欄は評価しない
    r = evaluate_detailed(gold, tables.claims)
    assert r.accuracy["user_code"] < 1.0 and r.accuracy["repair_code"] == 1.0
    assert r.mismatches[0]["field"] == "user_code"


def test_r55_cli_autodetect(tmp_path, codebook, fake_client_factory, capsys):
    from repclass.pipeline import run_pipeline
    res = run_pipeline(SYNTH / "repairs.csv", codebook=codebook, client=fake_client_factory(),
                       output_dir=tmp_path / "out", timestamp="20261102_150000")
    gold = tmp_path / "gold_simple.csv"
    with open(gold, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["repair_id", "representative_name"])
        w.writeheader(); w.writerows(GOLD)
    cb = str(SYNTH.parent / "codebook_test.yaml")
    assert main(["--gold", str(gold), "--run", str(res.run_dir), "--codebook", cb]) == 0
    out = capsys.readouterr().out
    assert "YES/NO" in out and len(out.splitlines()) <= 20
    assert (res.run_dir / "evaluation" / "mismatches.csv").exists()
    assert (res.run_dir / "evaluation" / "unresolved_names.csv").exists()
    assert main(["--gold", str(SYNTH / "expected_claims.csv"), "--run", str(res.run_dir), "--codebook", cb]) == 0
    assert "user_code" in capsys.readouterr().out

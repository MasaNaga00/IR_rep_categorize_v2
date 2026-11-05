"""R-23〜R-26: 入力の読み込み。"""
from __future__ import annotations

from repclass.input_loader import DEFAULT_COLUMNS, load_column_config, load_input


def test_r24_default_columns():
    assert DEFAULT_COLUMNS == {
        "repair_id": "ID", "product_type": "事業コード", "user_comment": "user_comment",
        "repair_comment": "repair_comment", "internal_1": "Internal_1", "internal_2": "Internal_2",
    }


def test_r23_r25_load_synthetic(codebook, synth_csv, expected_excluded, expected_final):
    res = load_input(synth_csv, codebook)
    ids = [r["repair_id"] for r in res.records]
    assert ids == list(expected_final)  # 入力順のまま、除外分を除いた全件
    got = sorted((e["row_number"], e["repair_id"], e["reason"]) for e in res.excluded)
    want = sorted((int(e["row_number"]), e["repair_id"], e["reason"]) for e in expected_excluded)
    assert got == want


def test_r26_internal_comments_kept(codebook, synth_csv):
    res = load_input(synth_csv, codebook)
    t028 = next(r for r in res.records if r["repair_id"] == "T028")
    assert t028["internal_1"] == "ショック痕あるが初回のため無償対応"
    assert t028["internal_2"] == ""
    t021 = next(r for r in res.records if r["repair_id"] == "T021")
    assert t021["user_comment"] == ""


def test_r25_empty_id_excluded(tmp_path, codebook):
    p = tmp_path / "in.csv"
    p.write_text("ID,事業コード,user_comment,repair_comment\n,ML,a,b\nX1,ML,c,d\n", encoding="utf-8")
    res = load_input(p, codebook)
    assert [r["repair_id"] for r in res.records] == ["X1"]
    assert res.excluded == [{"row_number": 1, "repair_id": "", "product_type": "ML", "reason": "empty_id"}]


def test_r23_bom_and_optional_internal_columns(tmp_path, codebook):
    p = tmp_path / "in.csv"
    p.write_text("ID,事業コード,user_comment,repair_comment\nX1,ML,a,b\n", encoding="utf-8-sig")
    res = load_input(p, codebook)
    assert res.records[0]["repair_id"] == "X1"
    assert res.records[0]["internal_1"] == "" and res.records[0]["internal_2"] == ""


def test_r24_column_config(tmp_path, codebook):
    cfg = tmp_path / "cols.yaml"
    cfg.write_text("repair_id: 修理番号\nproduct_type: 製品\n", encoding="utf-8")
    cols = load_column_config(cfg)
    assert cols["repair_id"] == "修理番号" and cols["user_comment"] == "user_comment"
    p = tmp_path / "in.csv"
    p.write_text("修理番号,製品,user_comment,repair_comment\nX1,LENS,a,b\n", encoding="utf-8")
    res = load_input(p, codebook, columns=cols)
    assert res.records[0]["product_type"] == "LENS"

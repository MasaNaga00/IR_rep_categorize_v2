"""R-26, R-29, R-30: Dify へのリクエストの組み立て。"""
from __future__ import annotations

import json

from repclass.input_loader import load_input
from repclass.llm_request import build_requests, make_request_record


def _records(codebook, synth_csv):
    return load_input(synth_csv, codebook).records


def test_r29_batches_are_per_product_and_sized(codebook, synth_csv):
    recs = _records(codebook, synth_csv)
    batches = build_requests(recs, codebook, batch_size=10)
    for b in batches:
        assert len(b.repair_ids) <= 10
        prods = {r["product_type"] for r in recs if r["repair_id"] in b.repair_ids}
        assert prods == {b.product_id}
    all_ids = [i for b in batches for i in b.repair_ids]
    assert sorted(all_ids) == sorted(r["repair_id"] for r in recs)
    assert [b.batch_id for b in batches] == list(range(1, len(batches) + 1))
    ml = [b for b in batches if b.product_id == "ML"]
    assert [len(b.repair_ids) for b in ml] == [10, 10, 10, 10, 4]  # ML 44 件
    assert [len(b.repair_ids) for b in batches if b.product_id == "LENS"] == [9]
    assert [len(b.repair_ids) for b in batches if b.product_id == "DC"] == [3]


def test_r30_inputs(codebook, synth_csv):
    recs = _records(codebook, synth_csv)
    b = build_requests(recs, codebook, batch_size=10)[0]
    assert set(b.inputs) == {"product_name", "code_list", "records"}
    assert b.inputs["product_name"] == "ミラーレスカメラ"
    assert b.inputs["code_list"] == codebook.code_list_text("ML")
    rows = json.loads(b.inputs["records"])
    assert rows == b.request_records
    assert set(rows[0]) == {"repair_id", "failure_count", "missing_numbers", "user_comment", "repair_comment"}


def test_r30_failure_count_and_missing_numbers(codebook, synth_csv):
    recs = {r["repair_id"]: r for r in _records(codebook, synth_csv)}
    rr = make_request_record(recs["T008"])
    assert rr["failure_count"] == 3 and rr["missing_numbers"] == [2]
    assert make_request_record(recs["T007"])["failure_count"] == 3
    assert make_request_record(recs["T021"])["failure_count"] == 1


def test_r26_internal_comments_not_sent_by_default(codebook, synth_csv):
    recs = {r["repair_id"]: r for r in _records(codebook, synth_csv)}
    assert "internal_1" not in make_request_record(recs["T028"])
    rr = make_request_record(recs["T028"], include_internal=True)
    assert rr["internal_1"] == "ショック痕あるが初回のため無償対応"
    batches = build_requests([recs["T028"]], codebook, include_internal=True)
    assert "internal_1" in json.loads(batches[0].inputs["records"])[0]

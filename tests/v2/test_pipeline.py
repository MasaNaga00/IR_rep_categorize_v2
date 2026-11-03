"""R-35〜R-40, R-49〜R-51: 実行全体(Dify は FakeDifyClient で代替)。"""
from __future__ import annotations

import json

import pytest

from repclass.pipeline import run_pipeline

from .conftest import read_csv


def _run(tmp_path, codebook, synth_csv, client, **kw):
    kw.setdefault("timestamp", "20261102_120000")
    return run_pipeline(synth_csv, codebook=codebook, client=client, output_dir=tmp_path / "out", **kw)


def test_r50_output_files(tmp_path, codebook, synth_csv, fake_client_factory):
    res = _run(tmp_path, codebook, synth_csv, fake_client_factory())
    d = res.run_dir
    assert d == tmp_path / "out" / "20261102_120000"
    for name in ("repairs.csv", "claims.csv", "environments.csv", "extra_findings.csv", "final.csv",
                 "error_repairs.json", "validation_issues.csv", "run_meta.json", "results.json"):
        assert (d / name).exists(), name
    assert sorted(p.name for p in (d / "raw").glob("batch_*_request.json")) == [f"batch_{i:03d}_request.json" for i in range(1, 7)]
    assert len(list((d / "raw").glob("batch_*_response.json"))) == 6
    assert not list(d.glob("*.parquet"))   # R-10


def test_r13_csv_encoding_and_values(tmp_path, codebook, synth_csv, fake_client_factory, expected_final):
    res = _run(tmp_path, codebook, synth_csv, fake_client_factory())
    raw = (res.run_dir / "final.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")   # utf-8-sig
    rows = read_csv(res.run_dir / "final.csv")
    assert [r["repair_id"] for r in rows] == list(expected_final)
    for r in rows:
        e = expected_final[r["repair_id"]]
        assert (r["manufacturer_repair"], r["representative_code"], r["user_caused_env"]) == \
               (e["manufacturer_repair"], e["representative_code"], e["user_caused_env"]), r["repair_id"]


def test_r51_run_meta(tmp_path, codebook, synth_csv, fake_client_factory):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")
    res = _run(tmp_path, codebook, synth_csv, fake_client_factory(), prompt_path=prompt)
    meta = json.loads((res.run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["input_path"] == str(synth_csv)
    assert meta["codebook_version"] == codebook.version and meta["codebook_sha256"] == codebook.sha256
    assert len(meta["prompt_sha256"]) == 64
    assert meta["counts"] == {"input": 45, "excluded": 2, "ok": 43, "warning": 0, "error": 0}
    assert meta["excluded_reasons"] == {"unknown_product": 1, "duplicate_id": 1}
    assert meta["batches"] == 6 and meta["retries"] == 0
    assert meta["total_tokens"] == 600
    assert meta["resume_from"] is None
    assert "elapsed_seconds" in meta and "started_at" in meta


def test_r36_api_error_batch_is_retried_one_by_one(tmp_path, codebook, synth_csv, fake_client_factory):
    client = fake_client_factory(fail_batches={1})
    res = _run(tmp_path, codebook, synth_csv, client)
    assert res.meta["counts"]["error"] == 0
    assert res.meta["retries"] == 10
    single_calls = [c for c in client.calls[6:]]
    assert all(len(json.loads(c["records"])) == 1 for c in single_calls)


def test_r36_parse_error_batch_is_retried(tmp_path, codebook, synth_csv, fake_client_factory):
    res = _run(tmp_path, codebook, synth_csv, fake_client_factory(invalid_json_calls={2}))
    assert res.meta["counts"]["error"] == 0 and res.meta["retries"] == 10


def test_r36_broken_once_recovers(tmp_path, codebook, synth_csv, fake_client_factory):
    res = _run(tmp_path, codebook, synth_csv, fake_client_factory(broken_once_ids={"T005"}))
    assert res.meta["counts"]["error"] == 0 and res.meta["retries"] == 1


def test_r35_r39_persistent_error_still_produces_full_output(tmp_path, codebook, synth_csv, fake_client_factory):
    res = _run(tmp_path, codebook, synth_csv, fake_client_factory(broken_ids={"T003"}))
    assert res.meta["counts"] == {"input": 45, "excluded": 2, "ok": 42, "warning": 0, "error": 1}
    final = {r["repair_id"]: r for r in read_csv(res.run_dir / "final.csv")}
    assert len(final) == 43
    assert (final["T003"]["status"], final["T003"]["error_reason"], final["T003"]["manufacturer_repair"]) == ("error", "unknown_code", "")
    err = json.loads((res.run_dir / "error_repairs.json").read_text(encoding="utf-8"))
    assert [e["repair_id"] for e in err] == ["T003"]
    issues = read_csv(res.run_dir / "validation_issues.csv")
    assert {"repair_id", "sub_id", "kind", "severity", "message"} <= set(issues[0])
    assert any(i["repair_id"] == "T003" and i["kind"] == "unknown_code" for i in issues)


def test_r40_resume_reruns_only_errors(tmp_path, codebook, synth_csv, fake_client_factory):
    first = _run(tmp_path, codebook, synth_csv, fake_client_factory(broken_ids={"T003"}))
    client = fake_client_factory()
    second = _run(tmp_path, codebook, synth_csv, client, resume_from=first.run_dir, timestamp="20261102_130000")
    assert second.run_dir != first.run_dir
    assert [json.loads(c["records"])[0]["repair_id"] for c in client.calls] == ["T003"]
    assert second.meta["counts"]["error"] == 0
    assert second.meta["resume_from"] == "20261102_120000"
    final = read_csv(second.run_dir / "final.csv")
    assert len(final) == 43 and all(r["status"] == "ok" for r in final)


def test_r49_dry_run(tmp_path, codebook, synth_csv):
    res = run_pipeline(synth_csv, codebook=codebook, client=None, output_dir=tmp_path / "out",
                       dry_run=True, timestamp="20261102_140000")
    assert len(list((res.run_dir / "raw").glob("batch_*_request.json"))) == 6
    assert not (res.run_dir / "final.csv").exists()
    assert res.meta["dry_run"] is True


def test_r29_batch_size_option(tmp_path, codebook, synth_csv, fake_client_factory):
    res = _run(tmp_path, codebook, synth_csv, fake_client_factory(), batch_size=40)
    assert res.meta["batches"] == 3   # ML・LENS・DC で1バッチずつ

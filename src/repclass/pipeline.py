"""R-35〜R-40, R-49〜R-51: 実行全体の流れ。"""
from __future__ import annotations

import hashlib
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .codebook import Codebook
from .comment_preprocess import REMOVED_COLUMNS, PreprocessRules, apply_preprocess
from .constants import STATUS_ERROR, STATUS_OK, STATUS_WARNING
from .dify_client import DifyAPIError
from .input_loader import load_input
from .judge import FINAL_COLUMNS, judge_repairs
from .llm_request import BatchRequest, build_requests
from .llm_response import LLMParseError, ValidationIssue, parse_llm_response, validate_batch
from .outputs import read_json, write_csv, write_json
from .tables import build_tables

REPAIRS_COLUMNS = ["repair_id", "product_type", "failure_count", "status", "error_reason",
                   "user_comment", "repair_comment", "internal_1", "internal_2",
                   "user_comment_notes", "repair_comment_notes"]   # R-67(2026-11-08 追加)
CLAIMS_COLUMNS = ["repair_id", "sub_id", "user_code", "reproduction", "basis", "ref_sub_id", "repair_code",
                  "inherited", "user_excerpt", "repair_excerpt"]
ENV_COLUMNS = ["repair_id", "factor", "source", "abnormal_use", "user_caused", "excerpt"]
EXTRA_COLUMNS = ["repair_id", "seq", "description", "repair_code", "excerpt"]
ISSUE_COLUMNS = ["repair_id", "sub_id", "kind", "severity", "message"]
EXCLUDED_COLUMNS = ["row_number", "excel_row", "repair_id", "product_type", "reason"]


@dataclass
class RunResult:
    run_dir: Path
    final_rows: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def _sha256(path: Path | None) -> str | None:
    if path is None or not Path(path).exists():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class _Runner:
    def __init__(self, client, codebook: Codebook, raw_dir: Path, originals: dict[str, dict] | None = None):
        self.client = client
        self.codebook = codebook
        self.raw_dir = raw_dir
        self.originals = originals or {}   # 注記を取り除く前の文(抜き出しの確認用。R-67)
        self.total_tokens = 0
        self.results: dict[str, dict] = {}
        self.issues: dict[str, list[ValidationIssue]] = {}
        self.errors: dict[str, str] = {}

    def call(self, batch: BatchRequest, label: str) -> None:
        write_json(self.raw_dir / f"{label}_request.json",
                   {"product_id": batch.product_id, "repair_ids": batch.repair_ids, "inputs": batch.inputs})
        ids = batch.repair_ids
        try:
            resp = self.client.run(batch.inputs)
        except DifyAPIError as e:
            write_json(self.raw_dir / f"{label}_response.json", {"error": str(e)})
            self._fail(ids, "api_error", str(e))
            return
        self.total_tokens += resp.total_tokens or 0
        write_json(self.raw_dir / f"{label}_response.json", {"text": resp.text, "total_tokens": resp.total_tokens})
        try:
            items = parse_llm_response(resp.text)
        except LLMParseError as e:
            self._fail(ids, "parse_error", str(e))
            return
        results, issues = validate_batch(items, batch.request_records, batch.product_id, self.codebook, self.originals)
        by_rid: dict[str, list[ValidationIssue]] = {rid: [] for rid in ids}
        for i in issues:
            by_rid.setdefault(i.repair_id, []).append(i)
        for rid in ids:
            iss = by_rid.get(rid, [])
            self.issues[rid] = iss
            errs = [i for i in iss if i.severity == "error"]
            if errs:
                self.errors[rid] = errs[0].kind
                self.results.pop(rid, None)
            else:
                self.errors.pop(rid, None)
                self.results[rid] = results[rid]

    def _fail(self, ids, kind, msg):
        for rid in ids:
            self.issues[rid] = [ValidationIssue(rid, None, kind, msg, "error")]
            self.errors[rid] = kind
            self.results.pop(rid, None)


def run_pipeline(input_csv, *, codebook: Codebook, client, output_dir, batch_size: int = 10,
                 columns: dict | None = None, include_internal: bool = False, resume_from=None,
                 dry_run: bool = False, prompt_path=None, timestamp: str | None = None,
                 preprocess: PreprocessRules | None = None) -> RunResult:
    t0 = time.time()
    started = datetime.now()
    ts = timestamp or started.strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_dir) / ts
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    loaded = load_input(input_csv, codebook, columns)
    records = loaded.records
    # R-64〜R-67: 注記を取り除く(preprocess が無ければ何もしない)
    removed_rows = apply_preprocess(records, preprocess) if preprocess is not None else []
    rec_by_id = {r["repair_id"]: r for r in records}
    originals = {r["repair_id"]: {"user_comment": r.get("user_comment_original"),
                                  "repair_comment": r.get("repair_comment_original")}
                 for r in records if "user_comment_original" in r or "repair_comment_original" in r}

    prev: dict[str, dict] = {}
    if resume_from is not None:
        prev_file = Path(resume_from) / "results.json"
        if prev_file.exists():
            prev = {k: v for k, v in read_json(prev_file).items() if k in rec_by_id}
    to_run = [r for r in records if r["repair_id"] not in prev]
    batches = build_requests(to_run, codebook, batch_size, include_internal)

    meta = {
        "started_at": started.isoformat(timespec="seconds"),
        "input_path": str(input_csv),
        "resume_from": Path(resume_from).name if resume_from is not None else None,
        "dry_run": dry_run,
        "codebook_path": str(codebook.path),
        "codebook_version": codebook.version,
        "codebook_sha256": codebook.sha256,
        "prompt_path": str(prompt_path) if prompt_path else None,
        "prompt_sha256": _sha256(prompt_path),
        "include_internal": include_internal,
        "batch_size": batch_size,
        "excluded_reasons": dict(Counter(e["reason"] for e in loaded.excluded)),
        # YAML にない製品種別の値と件数(2026-11-06 追加。表記ゆれ・未登録の製品の確認用)
        "unknown_product_values": dict(Counter(e["product_type"] for e in loaded.excluded
                                               if e["reason"] == "unknown_product").most_common()),
        "batches": len(batches),
        "retries": 0,
        # 注記の除去(R-67。2026-11-08 追加)
        "preprocess": None if preprocess is None else {
            "path": str(preprocess.path) if preprocess.path else None,
            "sha256": preprocess.sha256,
            "markers": preprocess.marker_codes(),
            "apply_to": {"repair_comment": preprocess.apply_repair_comment, "user_comment": preprocess.apply_user_comment},
            "repairs_with_notes": len({r["repair_id"] for r in removed_rows}),
        },
    }

    # 除外された行の一覧(2026-11-06 追加。excel_row は見出しを含めた Excel 上の行番号)
    write_csv(run_dir / "excluded_rows.csv", [dict(e, excel_row=e["row_number"] + 1) for e in loaded.excluded],
              EXCLUDED_COLUMNS)
    # 注記として取り除いた文の一覧(R-67。dry-run でも出力する)
    write_csv(run_dir / "removed_notes.csv", removed_rows, REMOVED_COLUMNS)

    if dry_run:
        for b in batches:
            write_json(raw_dir / f"batch_{b.batch_id:03d}_request.json",
                       {"product_id": b.product_id, "repair_ids": b.repair_ids, "inputs": b.inputs})
        meta["counts"] = {"input": len(records) + len(loaded.excluded), "excluded": len(loaded.excluded),
                          "to_run": len(to_run)}
        meta["elapsed_seconds"] = round(time.time() - t0, 2)
        write_json(run_dir / "run_meta.json", meta)
        return RunResult(run_dir, [], meta)

    runner = _Runner(client, codebook, raw_dir, originals)
    for b in batches:
        runner.call(b, f"batch_{b.batch_id:03d}")
    # R-36: エラーの修理を1件ずつ1回だけ再試行
    retry_ids = [r["repair_id"] for r in to_run if r["repair_id"] in runner.errors]
    for n, rid in enumerate(retry_ids, start=1):
        single = build_requests([rec_by_id[rid]], codebook, 1, include_internal)[0]
        runner.call(single, f"retry_{n:03d}")
    meta["retries"] = len(retry_ids)

    results = {k: v["result"] for k, v in prev.items()}
    warnings: dict[str, list] = {k: v.get("warnings") or [] for k, v in prev.items() if v.get("warnings")}
    results.update(runner.results)
    # 前回分の警告(同原因の循環は build_tables で再計算されるので除く)
    all_issues: list[ValidationIssue] = [ValidationIssue(**w) for v in prev.values()
                                         for w in (v.get("warnings") or []) if w.get("kind") != "ref_cycle"]
    for rid, iss in runner.issues.items():
        all_issues.extend(iss)
        w = [i for i in iss if i.severity == "warning"]
        if w and rid not in runner.errors:
            warnings[rid] = w

    tables = build_tables(records, results, dict(runner.errors), codebook, warnings)
    all_issues.extend(tables.issues)
    final = judge_repairs(tables, codebook)
    status = {r["repair_id"]: r["status"] for r in tables.repairs}

    write_csv(run_dir / "repairs.csv", tables.repairs, REPAIRS_COLUMNS)
    write_csv(run_dir / "claims.csv", tables.claims, CLAIMS_COLUMNS)
    write_csv(run_dir / "environments.csv", tables.environments, ENV_COLUMNS)
    write_csv(run_dir / "extra_findings.csv", tables.extra_findings, EXTRA_COLUMNS)
    write_csv(run_dir / "final.csv", final, FINAL_COLUMNS)
    write_csv(run_dir / "validation_issues.csv", [i.to_dict() for i in all_issues], ISSUE_COLUMNS)
    write_json(run_dir / "error_repairs.json", [rec_by_id[rid] for rid in rec_by_id if status.get(rid) == STATUS_ERROR])
    table_warn: dict[str, list] = {}
    for i in all_issues:
        if i.severity == "warning":
            table_warn.setdefault(i.repair_id, []).append(i.to_dict())
    write_json(run_dir / "results.json", {
        rid: {"status": status[rid], "result": res, "warnings": table_warn.get(rid, [])}
        for rid, res in results.items() if status.get(rid) in (STATUS_OK, STATUS_WARNING)
    })

    cnt = Counter(status.values())
    meta["counts"] = {"input": len(records) + len(loaded.excluded), "excluded": len(loaded.excluded),
                      "ok": cnt.get(STATUS_OK, 0), "warning": cnt.get(STATUS_WARNING, 0), "error": cnt.get(STATUS_ERROR, 0)}
    meta["manufacturer_repair_yes"] = sum(1 for r in final if r["manufacturer_repair"] == "YES")
    meta["total_tokens"] = runner.total_tokens
    meta["elapsed_seconds"] = round(time.time() - t0, 2)
    write_json(run_dir / "run_meta.json", meta)
    return RunResult(run_dir, final, meta)

"""R-23〜R-26: 入力 CSV の読み込み。"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .codebook import Codebook

DEFAULT_COLUMNS = {
    "repair_id": "ID",
    "product_type": "事業コード",
    "user_comment": "user_comment",
    "repair_comment": "repair_comment",
    "internal_1": "Internal_1",
    "internal_2": "Internal_2",
}
REQUIRED = ("repair_id", "product_type", "user_comment", "repair_comment")
FIELDS = tuple(DEFAULT_COLUMNS)


@dataclass
class LoadResult:
    records: list[dict] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)


def load_column_config(path: str | Path | None) -> dict:
    cols = dict(DEFAULT_COLUMNS)
    if path is not None and Path(path).exists():
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig")) or {}
        for k, v in data.items():
            if k not in DEFAULT_COLUMNS:
                raise ValueError(f"列の対応づけに不明な項目があります: {k}")
            cols[k] = str(v)
    return cols


def load_input(path: str | Path, codebook: Codebook, columns: dict | None = None) -> LoadResult:
    cols = dict(DEFAULT_COLUMNS)
    cols.update(columns or {})
    res = LoadResult()
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing = [cols[k] for k in REQUIRED if cols[k] not in header]
        if missing:
            raise ValueError(f"入力 CSV に必須の列がありません: {', '.join(missing)}")
        seen: set[str] = set()
        products = set(codebook.product_ids())
        for n, row in enumerate(reader, start=1):
            rec = {k: (row.get(cols[k]) or "").strip() if k in ("repair_id", "product_type") else (row.get(cols[k]) or "")
                   for k in FIELDS}
            rid = rec["repair_id"]
            if not rid:
                res.excluded.append({"row_number": n, "repair_id": "", "product_type": rec["product_type"], "reason": "empty_id"})
                continue
            if rid in seen:
                res.excluded.append({"row_number": n, "repair_id": rid, "product_type": rec["product_type"], "reason": "duplicate_id"})
                continue
            seen.add(rid)
            if rec["product_type"] not in products:
                res.excluded.append({"row_number": n, "repair_id": rid, "product_type": rec["product_type"], "reason": "unknown_product"})
                continue
            rec["row_number"] = n
            res.records.append(rec)
    return res

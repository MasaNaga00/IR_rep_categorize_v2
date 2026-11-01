"""R-26, R-29, R-30: Dify へのリクエストの組み立て。"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .codebook import Codebook
from .failure_count import count_failures


@dataclass
class BatchRequest:
    batch_id: int
    product_id: str
    repair_ids: list[str]
    request_records: list[dict]
    inputs: dict


def make_request_record(record: dict, include_internal: bool = False) -> dict:
    fc = count_failures(record.get("user_comment"))
    rr = {
        "repair_id": record["repair_id"],
        "failure_count": fc.failure_count,
        "missing_numbers": list(fc.missing_numbers),
        "user_comment": record.get("user_comment", ""),
        "repair_comment": record.get("repair_comment", ""),
    }
    if include_internal:
        rr["internal_1"] = record.get("internal_1", "")
        rr["internal_2"] = record.get("internal_2", "")
    return rr


def build_requests(records: list[dict], codebook: Codebook, batch_size: int = 10,
                   include_internal: bool = False, start_batch_id: int = 1) -> list[BatchRequest]:
    if batch_size < 1:
        raise ValueError("batch_size は 1 以上にしてください")
    by_product: dict[str, list[dict]] = {}
    for r in records:
        by_product.setdefault(r["product_type"], []).append(r)
    out: list[BatchRequest] = []
    bid = start_batch_id
    for pid, recs in by_product.items():
        for i in range(0, len(recs), batch_size):
            chunk = recs[i:i + batch_size]
            rrs = [make_request_record(r, include_internal) for r in chunk]
            inputs = {
                "product_name": codebook.product_name(pid),
                "code_list": codebook.code_list_text(pid),
                "records": json.dumps(rrs, ensure_ascii=False),
            }
            out.append(BatchRequest(bid, pid, [r["repair_id"] for r in chunk], rrs, inputs))
            bid += 1
    return out

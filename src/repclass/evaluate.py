"""R-54〜R-55a: 精度評価(簡易版: 修理単位の代表故障 / 詳細版: 申告単位)。"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .codebook import Codebook, load_codebook
from .local_config import resolve_paths
from .outputs import write_csv, write_json


def normalize_name(s: str | None) -> str:
    """NFKC 正規化(半角カナ→全角、全角英数→半角)、空白除去、記号ゆれの統一、大文字小文字の無視。"""
    t = unicodedata.normalize("NFKC", s or "")
    t = re.sub(r"\s+", "", t)
    t = t.replace("／", "/").replace("・", "/").replace("･", "/")
    t = t.replace("【", "(").replace("】", ")").replace("[", "(").replace("]", ")")
    return t.casefold()


def _read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class NameResolver:
    """過去の分類結果の名称 → コード(R-55a)。"""

    def __init__(self, codebook: Codebook, name_map: list[dict] | None = None):
        self._by_product: dict[str, dict[str, str]] = {}
        for pid in codebook.product_ids():
            self._by_product[pid] = {normalize_name(i.name): c for c, i in codebook.codes(pid).items()}
        for row in name_map or []:
            pid, name, code = row.get("product_type", ""), row.get("past_name", ""), row.get("code", "")
            if pid and name and code:
                self._by_product.setdefault(pid, {})[normalize_name(name)] = code

    @classmethod
    def from_file(cls, codebook: Codebook, path) -> "NameResolver":
        return cls(codebook, _read_csv(path) if path and Path(path).exists() else None)

    def resolve(self, product_id: str, name: str) -> str | None:
        if not name:
            return None
        return self._by_product.get(product_id, {}).get(normalize_name(name))


@dataclass
class SimpleEvalResult:
    n_compared: int = 0
    yes_no_accuracy: float | None = None
    n_both_yes: int = 0
    representative_accuracy: float | None = None
    mismatches: list[dict] = field(default_factory=list)
    unresolved: dict = field(default_factory=dict)
    n_missing_in_run: int = 0
    n_error_skipped: int = 0


def evaluate_simple(gold_rows: list[dict], final_rows: list[dict], resolver: NameResolver) -> SimpleEvalResult:
    final = {r["repair_id"]: r for r in final_rows}
    r = SimpleEvalResult()
    unresolved: Counter = Counter()
    yn_ok = rep_ok = 0
    for g in gold_rows:
        rid = g["repair_id"]
        f = final.get(rid)
        if f is None:
            r.n_missing_in_run += 1
            continue
        if f["status"] == "error":
            r.n_error_skipped += 1
            continue
        name = (g.get("representative_name") or "").strip()
        code = None
        if name:
            code = resolver.resolve(f["product_type"], name)
            if code is None:
                unresolved[(f["product_type"], name)] += 1
                continue
        gold_yes, pred_yes = bool(name), f["manufacturer_repair"] == "YES"
        r.n_compared += 1
        yn_ok += gold_yes == pred_yes
        pred = f["representative_code"]
        if gold_yes and pred_yes:
            r.n_both_yes += 1
            if code == pred:
                rep_ok += 1
            else:
                r.mismatches.append({"repair_id": rid, "kind": "code_differs", "gold_code": code, "gold_name": name, "pred_code": pred})
        elif gold_yes:
            r.mismatches.append({"repair_id": rid, "kind": "gold_only", "gold_code": code, "gold_name": name, "pred_code": ""})
        elif pred_yes:
            r.mismatches.append({"repair_id": rid, "kind": "pred_only", "gold_code": "", "gold_name": "", "pred_code": pred})
    r.yes_no_accuracy = yn_ok / r.n_compared if r.n_compared else None
    r.representative_accuracy = rep_ok / r.n_both_yes if r.n_both_yes else None
    r.unresolved = dict(unresolved)
    return r


DETAIL_FIELDS = ("user_code", "reproduction", "repair_code")


@dataclass
class DetailedEvalResult:
    accuracy: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    mismatches: list[dict] = field(default_factory=list)


def evaluate_detailed(gold_rows: list[dict], claims_rows: list[dict]) -> DetailedEvalResult:
    pred = {(c["repair_id"], int(c["sub_id"])): c for c in claims_rows}
    ok = Counter(); total = Counter()
    res = DetailedEvalResult()
    for g in gold_rows:
        key = (g["repair_id"], int(g["sub_id"]))
        p = pred.get(key, {})
        for f in DETAIL_FIELDS:
            gv = (g.get(f) or "").strip()
            if not gv:
                continue
            total[f] += 1
            pv = str(p.get(f) or "")
            if gv == pv:
                ok[f] += 1
            else:
                res.mismatches.append({"repair_id": key[0], "sub_id": key[1], "field": f, "gold": gv, "pred": pv})
    res.accuracy = {f: (ok[f] / total[f] if total[f] else None) for f in DETAIL_FIELDS}
    res.counts = {f: total[f] for f in DETAIL_FIELDS}
    return res


def _pct(v):
    return "—" if v is None else f"{v * 100:.1f}%"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="精度評価(正解CSVの列から簡易版/詳細版を自動判別)")
    ap.add_argument("--gold", required=True)
    ap.add_argument("--run", required=True, help="実行フォルダ")
    ap.add_argument("--codebook")
    ap.add_argument("--local-dir")
    ap.add_argument("--name-map")
    a = ap.parse_args(argv)
    run = Path(a.run)
    gold = _read_csv(a.gold)
    out_dir = run / "evaluation"
    if gold and "sub_id" in gold[0]:
        r = evaluate_detailed(gold, _read_csv(run / "claims.csv"))
        write_csv(out_dir / "mismatches.csv", r.mismatches, ["repair_id", "sub_id", "field", "gold", "pred"])
        write_json(out_dir / "summary.json", {"type": "detailed", "accuracy": r.accuracy, "counts": r.counts})
        print(f"詳細版の評価: {run.name}")
        for f in DETAIL_FIELDS:
            print(f"  {f}: {_pct(r.accuracy[f])}(対象 {r.counts[f]} 件)")
        print(f"不一致 {len(r.mismatches)} 件 → {out_dir / 'mismatches.csv'}")
        return 0
    paths = resolve_paths(local_dir=a.local_dir, codebook=a.codebook)
    codebook = load_codebook(paths.codebook)
    resolver = NameResolver.from_file(codebook, a.name_map or paths.name_map)
    r = evaluate_simple(gold, _read_csv(run / "final.csv"), resolver)
    write_csv(out_dir / "mismatches.csv", r.mismatches, ["repair_id", "kind", "gold_code", "gold_name", "pred_code"])
    write_csv(out_dir / "unresolved_names.csv",
              [{"product_type": p, "past_name": n, "count": c} for (p, n), c in sorted(r.unresolved.items(), key=lambda x: -x[1])],
              ["product_type", "past_name", "count"])
    write_json(out_dir / "summary.json", {"type": "simple", "n_compared": r.n_compared,
               "yes_no_accuracy": r.yes_no_accuracy, "n_both_yes": r.n_both_yes,
               "representative_accuracy": r.representative_accuracy, "n_missing_in_run": r.n_missing_in_run,
               "n_error_skipped": r.n_error_skipped, "n_unresolved": sum(r.unresolved.values())})
    kinds = Counter(m["kind"] for m in r.mismatches)
    print(f"簡易版の評価: {run.name}(比較 {r.n_compared} 件)")
    print(f"  YES/NO 一致率: {_pct(r.yes_no_accuracy)}")
    print(f"  代表故障 一致率: {_pct(r.representative_accuracy)}(両方 YES の {r.n_both_yes} 件中)")
    print(f"  不一致: コード違い {kinds['code_differs']} / 正解だけYES {kinds['gold_only']} / こちらだけYES {kinds['pred_only']}")
    print(f"  名称を変換できず除外: {sum(r.unresolved.values())} 件(種類 {len(r.unresolved)})→ unresolved_names.csv")
    print(f"  実行結果に無い: {r.n_missing_in_run} 件 / エラーで除外: {r.n_error_skipped} 件")
    print(f"詳細: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

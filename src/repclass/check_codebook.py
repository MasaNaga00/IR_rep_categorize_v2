"""python -m repclass.check_codebook [--codebook <path>] [--local-dir <path>](R-16)"""
from __future__ import annotations

import argparse
import sys

from .codebook import CodebookError, load_codebook
from .local_config import resolve_paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="分類コード体系(YAML)の自動チェック")
    ap.add_argument("--codebook")
    ap.add_argument("--local-dir")
    a = ap.parse_args(argv)
    path = resolve_paths(local_dir=a.local_dir, codebook=a.codebook).codebook
    try:
        cb = load_codebook(path)
    except CodebookError as e:
        print(f"NG: {path}({len(e.errors)} 件)")
        for err in e.errors:
            print(f"  - {err}")
        return 1
    prods = ", ".join(f"{p}({len(cb.codes(p))})" for p in cb.product_ids())
    print(f"OK: {path}  version={cb.version}  製品={prods}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

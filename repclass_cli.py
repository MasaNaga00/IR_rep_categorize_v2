"""v2(repclass)の起動用スクリプト。インストール不要で、リポジトリの直下から実行する。

  python repclass_cli.py init      --local-dir C:\\work\\repclass_local
  python repclass_cli.py check     [--local-dir ...] [--codebook ...]
  python repclass_cli.py run       --input <CSV> [--local-dir ...] [--dry-run] [--resume <timestamp>]
  python repclass_cli.py evaluate  --gold <正解CSV> --run <実行フォルダ> [--local-dir ...]

各サブコマンドの引数は、python -m repclass.<module> と同じ(要件定義書 R-16, R-05a, R-49, R-55)。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

COMMANDS = {
    "init": "repclass.init_local",
    "check": "repclass.check_codebook",
    "run": "repclass.run",
    "evaluate": "repclass.evaluate",
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    import importlib
    mod = importlib.import_module(COMMANDS[sys.argv[1]])
    return mod.main(sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())

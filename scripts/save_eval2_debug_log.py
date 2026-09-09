#!/usr/bin/env python3
# WriterAgent - one-shot save of writeragent_debug.log for eval-2
"""Copy the live LibreOffice-user debug log into DEST_DIR.

Use this mid-stall, *before* restarting LibreOffice for the next trial.
``eval_2_headed.py --launch`` also snapshots on Enter / Ctrl-C; this
helper is for saving while the hang is still on disk.

Usage:
  .venv/bin/python scripts/save_eval2_debug_log.py DEST_DIR
  .venv/bin/python scripts/save_eval2_debug_log.py docs/eval/eval-2/writer-calc-peer-write/runs/20260909-1748
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval_2_debug_log import copy_debug_log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dest_dir",
        type=Path,
        help="Directory that will receive writeragent_debug.log",
    )
    args = parser.parse_args(argv)
    try:
        source, dest = copy_debug_log(args.dest_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Could not copy writeragent_debug.log: {exc}", file=sys.stderr)
        return 1
    print(f"source: {source}")
    print(f"dest: {dest} ({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

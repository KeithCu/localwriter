#!/usr/bin/env python3
# WriterAgent - headed eval-2 / AFC tool-round budget
"""Temporarily write chatbot.max_tool_rounds=50, then restore.

No new yaml knobs. Everyday chat stays at the schema default (15).

``--launch`` copies only the Population ODS into a clean trial directory
(default ``$TMP/writeragent-eval2-afc``) so ``document_research`` cannot see
prompt/rubric/gold or fixture siblings. Do not open ``fixtures/`` or the
task folder.

Usage:
  .venv/bin/python scripts/eval_2_headed.py
  .venv/bin/python scripts/eval_2_headed.py --launch
  .venv/bin/python scripts/eval_2_headed.py --launch --trial-dir /tmp/my-afc
  .venv/bin/python scripts/eval_2_headed.py -- soffice --calc workbook.ods
  .venv/bin/python scripts/eval_2_headed.py --score path/to/final_workbook.ods
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_TOOL_ROUNDS_KEY = "chatbot.max_tool_rounds"
DEFAULT_MAX_TOOL_ROUNDS = 15
EVAL_2_MAX_TOOL_ROUNDS = 50
_AFC_DIR = REPO_ROOT / "docs" / "eval" / "eval-2" / "afc-sample-83d10b06"
POPULATION_ODS_NAME = "Population v2.ods"
_FIXTURE_ODS = _AFC_DIR / "fixtures" / POPULATION_ODS_NAME
_FIXTURE_CANDIDATES = (
    _FIXTURE_ODS,
    _AFC_DIR / "fixtures" / "Population v2.xlsx",
)
DEFAULT_TRIAL_DIR_NAME = "writeragent-eval2-afc"


def writeragent_json_candidates() -> list[Path]:
    """Same profile locations as bench_embeddings / strip_lru / bench_warm_numpy."""
    if os.name == "nt":
        return [Path(os.environ.get("APPDATA", "")) / "LibreOffice" / "4" / "user" / "writeragent.json"]
    if sys.platform == "darwin":
        return [Path("~/Library/Application Support/LibreOffice/4/user/writeragent.json").expanduser()]
    return [
        Path("~/.config/libreoffice/4/user/config/writeragent.json").expanduser(),
        Path("~/.config/libreoffice/4/user/writeragent.json").expanduser(),
        Path("~/.config/libreoffice/24/user/config/writeragent.json").expanduser(),
        Path("~/.config/libreoffice/24/user/writeragent.json").expanduser(),
    ]


def find_writeragent_json(
    explicit: Path | None = None,
    candidates: list[Path] | None = None,
) -> Path:
    if explicit is not None:
        return explicit
    search = writeragent_json_candidates() if candidates is None else candidates
    for path in search:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "Could not find writeragent.json. Pass --config PATH "
        "(LibreOffice user profile)."
    )


def _split_comment_header(text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].lstrip(" \t")
        if stripped == "" or stripped.startswith("//"):
            idx += 1
            continue
        break
    return "".join(lines[:idx]), "".join(lines[idx:])


def parse_config_object(text: str) -> dict[str, Any]:
    _header, body = _split_comment_header(text)
    data = json.loads(body or "{}")
    if not isinstance(data, dict):
        raise ValueError("writeragent.json must be a JSON object")
    return data


def read_max_tool_rounds(data: dict[str, Any]) -> int:
    """Effective cap: missing key is the schema default (15)."""
    if MAX_TOOL_ROUNDS_KEY not in data:
        return DEFAULT_MAX_TOOL_ROUNDS
    return int(data[MAX_TOOL_ROUNDS_KEY])


def apply_max_tool_rounds(data: dict[str, Any], rounds: int) -> object | None:
    """Write rounds onto data. Return the prior raw value, or None if absent."""
    previous = data[MAX_TOOL_ROUNDS_KEY] if MAX_TOOL_ROUNDS_KEY in data else None
    data[MAX_TOOL_ROUNDS_KEY] = rounds
    return previous


def restore_max_tool_rounds(data: dict[str, Any], previous: object | None) -> None:
    """Put back the prior value, or drop the key if it was not set."""
    if previous is None:
        data.pop(MAX_TOOL_ROUNDS_KEY, None)
    else:
        data[MAX_TOOL_ROUNDS_KEY] = previous


def write_config_flushed(path: Path, data: dict[str, Any], header: str = "") -> None:
    body = json.dumps(data, indent=4) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        if header:
            handle.write(header)
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def temporary_max_tool_rounds(
    config_path: Path,
    rounds: int = EVAL_2_MAX_TOOL_ROUNDS,
):
    """Set chatbot.max_tool_rounds, then restore the previous value (or omit the key)."""
    existed = config_path.is_file()
    text = config_path.read_text(encoding="utf-8") if existed else "{}"
    header = _split_comment_header(text)[0]
    data = parse_config_object(text)
    previous = apply_max_tool_rounds(data, rounds)
    write_config_flushed(config_path, data, header)
    try:
        yield previous
    finally:
        restore_max_tool_rounds(data, previous)
        if not existed and previous is None and not data:
            if config_path.is_file():
                config_path.unlink()
        else:
            write_config_flushed(config_path, data, header)


def find_afc_fixture() -> Path | None:
    for path in _FIXTURE_CANDIDATES:
        if path.is_file():
            return path
    return None


def find_afc_population_ods() -> Path:
    """Population ODS only. XLSX stay in fixtures/ (sibling, researchable)."""
    if _FIXTURE_ODS.is_file():
        return _FIXTURE_ODS
    raise FileNotFoundError(
        f"Missing {_FIXTURE_ODS}. Convert the xlsx fixture with "
        "soffice --convert-to ods; do not open fixtures/ (siblings leak)."
    )


def default_eval2_trial_dir() -> Path:
    return Path(tempfile.gettempdir()) / DEFAULT_TRIAL_DIR_NAME


def _is_protected_trial_dest(dest_dir: Path, source: Path) -> bool:
    """Refuse dest that would wipe the task tree, fixtures, or a filesystem root."""
    dest_dir = dest_dir.resolve()
    source = source.resolve()
    afc = _AFC_DIR.resolve()
    if dest_dir == source.parent or dest_dir in source.parents:
        return True
    if dest_dir == afc or dest_dir == afc.parent:
        return True
    try:
        dest_dir.relative_to(afc)
        return True
    except ValueError:
        pass
    if dest_dir == Path(dest_dir.anchor) or dest_dir == Path(tempfile.gettempdir()):
        return True
    return False


def stage_clean_trial_ods(source: Path, dest_dir: Path) -> Path:
    """Copy only *source* into *dest_dir* (wiped). Prompt/rubric/gold stay outside.

    document_research lists the open workbook's folder. Opening from fixtures/
    or the AFC task dir exposes xlsx, min-range ODS, prompt.txt, rubric, notes.
    """
    source = source.resolve()
    dest_dir = dest_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Population fixture not found: {source}")
    if _is_protected_trial_dest(dest_dir, source):
        raise ValueError(
            f"refusing to stage into protected path {dest_dir} "
            "(task tree, fixture folder, or filesystem/temp root)"
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Previous trials may have leftover Sample notes or extra ODS — wipe so
    # list_nearby_files sees only the Population copy.
    for child in dest_dir.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    dest = dest_dir / source.name
    shutil.copy2(source, dest)
    return dest


def launch_calc(fixture: Path | None) -> None:
    soffice = shutil.which("soffice")
    if soffice is None:
        print("soffice not on PATH; open Calc yourself.", file=sys.stderr)
        return
    cmd = [soffice, "--calc"]
    if fixture is not None:
        cmd.append(str(fixture))
    subprocess.Popen(cmd)


def _wait_for_finish() -> None:
    prompt = (
        f"set to {EVAL_2_MAX_TOOL_ROUNDS}; Ctrl-C / Enter to restore "
        f"{MAX_TOOL_ROUNDS_KEY}.\n"
    )
    try:
        input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None, help="writeragent.json path")
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Stage Population ODS only into a clean trial dir, then soffice --calc",
    )
    parser.add_argument(
        "--trial-dir",
        type=Path,
        default=None,
        help=(
            "Directory that will contain only the Population ODS "
            f"(default: $TMP/{DEFAULT_TRIAL_DIR_NAME})"
        ),
    )
    parser.add_argument(
        "--score",
        type=Path,
        default=None,
        help="Score a saved trial workbook (ODS/XLSX). Ignores chat Ready; does not write config.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Optional command to run as the session (prefix with --)",
    )
    args = parser.parse_args(argv)
    if args.score is not None:
        from eval_2_ods_oracle import main as score_main

        return score_main([str(args.score)])
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]

    config_path = find_writeragent_json(args.config)
    exit_code = 0
    with temporary_max_tool_rounds(config_path):
        print(f"Using {config_path}: {MAX_TOOL_ROUNDS_KEY}={EVAL_2_MAX_TOOL_ROUNDS}")
        if command:
            exit_code = subprocess.call(command)
        elif args.launch:
            try:
                trial_ods = stage_clean_trial_ods(
                    find_afc_population_ods(),
                    args.trial_dir or default_eval2_trial_dir(),
                )
            except (FileNotFoundError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"Staged clean trial dir {trial_ods.parent} ({trial_ods.name} only)")
            launch_calc(trial_ods)
            _wait_for_finish()
        else:
            _wait_for_finish()
    print(f"Restored previous {MAX_TOOL_ROUNDS_KEY} in {config_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

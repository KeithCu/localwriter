#!/usr/bin/env python3
# WriterAgent - snapshot writeragent_debug.log for eval-2 headed runs
"""Discover and copy the live LibreOffice-user writeragent_debug.log.

LO restart for the next headed trial re-inits logging (``Debug log
active``). That can reset the live profile file, so Floorstand Gemini
``20260909-1748`` lost its tool-call trace. Copy the full file with
``shutil.copy2`` before restart.

Candidate dirs match ``eval_2_headed.writeragent_json_candidates`` (same
profile locations as the live log next to ``writeragent.json``). The
filename matches ``plugin.framework.logging.DEBUG_LOG_FILENAME``. Outside
LibreOffice, filesystem candidates are enough — ``get_debug_log_path``
is only set after ``init_logging(ctx)``.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TextIO

# Keep in lockstep with plugin.framework.logging.DEBUG_LOG_FILENAME.
# Scripts stay importable without loading the plugin logging stack.
DEBUG_LOG_FILENAME = "writeragent_debug.log"


def lo_user_profile_dirs() -> list[Path]:
    """LibreOffice user-profile dirs that may hold writeragent.json / the debug log."""
    if os.name == "nt":
        return [Path(os.environ.get("APPDATA", "")) / "LibreOffice" / "4" / "user"]
    if sys.platform == "darwin":
        return [Path("~/Library/Application Support/LibreOffice/4/user").expanduser()]
    return [
        Path("~/.config/libreoffice/4/user/config").expanduser(),
        Path("~/.config/libreoffice/4/user").expanduser(),
        Path("~/.config/libreoffice/24/user/config").expanduser(),
        Path("~/.config/libreoffice/24/user").expanduser(),
    ]


def debug_log_candidates() -> list[Path]:
    """Same profile locations as analyze_tool_call_timing / writeragent.json."""
    return [directory / DEBUG_LOG_FILENAME for directory in lo_user_profile_dirs()]


def find_debug_log(
    explicit: Path | None = None,
    candidates: list[Path] | None = None,
) -> Path | None:
    """Return the first existing debug log, or None if none exist."""
    if explicit is not None:
        return explicit if explicit.is_file() else None
    search = debug_log_candidates() if candidates is None else candidates
    for path in search:
        if path.is_file():
            return path
    return None


def copy_debug_log(
    dest_dir: Path,
    *,
    source: Path | None = None,
    candidates: list[Path] | None = None,
) -> tuple[Path, Path]:
    """Copy the live debug log into ``dest_dir/writeragent_debug.log``.

    Raises ``FileNotFoundError`` when no live log exists. Does not change
    the live file (no truncate / no format change).
    """
    found = find_debug_log(source, candidates)
    if found is None:
        searched = [source] if source is not None else (candidates or debug_log_candidates())
        raise FileNotFoundError(
            "Could not find writeragent_debug.log. Looked in: "
            + ", ".join(str(path) for path in searched)
        )
    dest_dir = dest_dir.expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / DEBUG_LOG_FILENAME
    if dest.resolve() != found.resolve():
        shutil.copy2(found, dest)
    return found, dest


def snapshot_debug_log(
    dest_dir: Path,
    *,
    source: Path | None = None,
    candidates: list[Path] | None = None,
    file: TextIO | None = None,
) -> Path | None:
    """Copy the live log for a headed trial. Warn and return None on failure.

    Headed ``--launch`` must not fail the restore-config path if the log
    is missing or unreadable.
    """
    out = sys.stderr if file is None else file
    try:
        found, dest = copy_debug_log(dest_dir, source=source, candidates=candidates)
    except FileNotFoundError as exc:
        print(f"Warning: {exc}", file=out)
        return None
    except OSError as exc:
        print(f"Warning: could not snapshot writeragent_debug.log: {exc}", file=out)
        return None
    size = dest.stat().st_size
    print(f"Saved {DEBUG_LOG_FILENAME} from {found} -> {dest} ({size} bytes)")
    return dest

#!/usr/bin/env python3
# WriterAgent - eval-2 / Draw-primary process-map oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Soft structural scorer for the eval-2 Draw-primary process map.

Pass/fail is document-local. Chat Ready / STREAM_DONE is never consulted.
Score the saved Draw tree (shapes, labels, connectors) — not a Writer memo
and not gold-PDF pixels. Process anchors are gold-hard (Clearbend, automation
vs manual lanes, scan, sort, decision, failure/reroute). Hyphen-like
characters fold to ASCII before those searches.

Usage:
  .venv/bin/python scripts/eval_2_draw_oracle.py path/to/final_drawing.odg
  .venv/bin/python scripts/eval_2_draw_oracle.py path/to/runs/<stamp>/
  .venv/bin/python scripts/eval_2_headed.py --task draw-primary --score path/to/final_drawing.odg
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from eval_2_headed import DRAW_PRIMARY_ODG_NAME

_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_DRAW_NS = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
_DRAW_FRAME = f"{{{_DRAW_NS}}}frame"
_DRAW_CUSTOM = f"{{{_DRAW_NS}}}custom-shape"
_DRAW_RECT = f"{{{_DRAW_NS}}}rect"
_DRAW_ELLIPSE = f"{{{_DRAW_NS}}}ellipse"
_DRAW_CIRCLE = f"{{{_DRAW_NS}}}circle"
_DRAW_POLYGON = f"{{{_DRAW_NS}}}polygon"
_DRAW_CAPTION = f"{{{_DRAW_NS}}}caption"
_DRAW_CONNECTOR = f"{{{_DRAW_NS}}}connector"
_DRAW_LINE = f"{{{_DRAW_NS}}}line"
_DRAW_POLYLINE = f"{{{_DRAW_NS}}}polyline"
_NODE_TAGS = {
    _DRAW_FRAME,
    _DRAW_CUSTOM,
    _DRAW_RECT,
    _DRAW_ELLIPSE,
    _DRAW_CIRCLE,
    _DRAW_POLYGON,
    _DRAW_CAPTION,
}
_CONNECTOR_TAGS = {_DRAW_CONNECTOR, _DRAW_LINE, _DRAW_POLYLINE}
# Title-only husk is one labeled box. A real process map needs several nodes.
_MIN_LABELED_SHAPES = 6
_MIN_CONNECTORS = 2
_MIN_LABELED_CHARS = 80
_TITLE_ONLY = re.compile(r"^process\s+flow\s+map$", re.I)

_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
_CLEARBEND_RE = re.compile(r"clearbend", re.I)
_AUTOMATION_RE = re.compile(r"automation|automated|conveyable", re.I)
_MANUAL_RE = re.compile(r"\bmanual\b|non[\s\-]*conveyable|incompatible", re.I)
_DECISION_RE = re.compile(
    r"decision|classif|compatib|separat(?:e|ion)|routing\s+of\s+items",
    re.I,
)
_SCAN_RE = re.compile(r"\bscan(?:ning|ned)?\b|barcode|ocr|\brfid\b", re.I)
_SORT_RE = re.compile(r"\bsort(?:ing)?\b|divert|auto\s+rout", re.I)
_FAILURE_RE = re.compile(
    r"fail(?:ure)?|\bjam\b|no[\s\-]*read|reject|out[\s\-]*of[\s\-]*spec|exception",
    re.I,
)
_RECEIVE_RE = re.compile(r"receiv|unload|induct|inbound|\bloading\b", re.I)
_START_END_RE = re.compile(r"\bstart\b|\bend\b|dispatch|outbound|load[\s\-]*out", re.I)
_REWORK_RE = re.compile(
    r"rework|relabel|repack|reweigh|redimension|rescan|recode|triage",
    re.I,
)

# Word/LO often emit U+2011 (non-breaking hyphen). Fold those to ASCII
# before identity searches so Clearbend / non-conveyable still match.
_HYPHEN_LIKE_TO_ASCII = str.maketrans({
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2212": "-",
    "\u00a0": " ",
    "\u202f": " ",
})


def normalize_hyphen_like(text: str) -> str:
    """Fold hyphen-like / NBSP so process anchors match ASCII needles."""
    return (text or "").translate(_HYPHEN_LIKE_TO_ASCII)


@dataclass
class OracleResult:
    """Fail-closed Draw checks. Ready is never a field."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    labeled_shapes: int = 0
    connector_count: int = 0
    labeled_chars: int = 0

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DrawExtract:
    """Shapes and connectors from a saved ``.odg`` (zip XML, not live UNO)."""

    frames: list[tuple[str, str]]
    labeled_shapes: int
    connector_count: int
    labeled_chars: int
    text: str


def read_odg_drawing(path: Path) -> DrawExtract:
    """Collect labeled nodes + connector-like shapes from ``content.xml``."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    frames: list[tuple[str, str]] = []
    labeled = 0
    labeled_chars = 0
    connectors = 0
    parts: list[str] = []
    for node in root.iter():
        if node.tag in _CONNECTOR_TAGS:
            connectors += 1
            text = "".join(node.itertext()).strip()
            if text:
                parts.append(text)
            continue
        if node.tag not in _NODE_TAGS:
            continue
        name = node.get(f"{{{_DRAW_NS}}}name") or ""
        text = "".join(node.itertext())
        frames.append((name, text))
        stripped = text.strip()
        if stripped and not _TITLE_ONLY.match(stripped):
            labeled += 1
            labeled_chars += len(stripped)
            parts.append(stripped)
        elif stripped:
            parts.append(stripped)
    return DrawExtract(
        frames=frames,
        labeled_shapes=labeled,
        connector_count=connectors,
        labeled_chars=labeled_chars,
        text="\n".join(parts),
    )


def resolve_draw_artifact(artifact: Path) -> Path | None:
    """Pick the Draw canvas from a file or trial directory."""
    artifact = artifact.expanduser()
    if artifact.is_dir():
        return _first_existing(
            artifact / "final_drawing.odg",
            artifact / DRAW_PRIMARY_ODG_NAME,
            *sorted(artifact.glob("*.odg")),
        )
    if artifact.suffix.lower() == ".odg":
        return artifact if artifact.is_file() else None
    return _first_existing(
        artifact.with_name("final_drawing.odg"),
        artifact.with_name(DRAW_PRIMARY_ODG_NAME),
        *sorted(artifact.parent.glob("*.odg")),
    )


def _first_existing(*candidates: Path) -> Path | None:
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.is_file():
            return path
    return None


def score_drawing(
    text: str,
    *,
    labeled_shapes: int,
    connector_count: int,
    labeled_chars: int,
) -> OracleResult:
    """Apply soft fail-closed checks to extracted Draw text + counts."""
    failures: list[str] = []
    body = normalize_hyphen_like(text)
    if not body.strip():
        failures.append("drawing has no labeled shapes")
    if labeled_shapes < _MIN_LABELED_SHAPES:
        failures.append(
            f"labeled shapes {labeled_shapes} < {_MIN_LABELED_SHAPES} "
            "(title-only / Ready-empty husk)"
        )
    if labeled_chars < _MIN_LABELED_CHARS:
        failures.append(
            f"labeled chars {labeled_chars} < {_MIN_LABELED_CHARS} "
            "(too thin to count as a process map)"
        )
    if connector_count < _MIN_CONNECTORS:
        failures.append(
            f"connectors {connector_count} < {_MIN_CONNECTORS} "
            "(need flow links, not orphan boxes)"
        )
    if _HUSK_RE.search(body):
        failures.append("body contains Error:/husk residue")
    if not _CLEARBEND_RE.search(body):
        failures.append("missing Clearbend Logistics Hub")
    if not _AUTOMATION_RE.search(body):
        failures.append("missing automation / automated lane")
    if not _MANUAL_RE.search(body):
        failures.append("missing manual / incompatible lane")
    if not _DECISION_RE.search(body):
        failures.append("missing separation decision / classification")
    if not _SCAN_RE.search(body):
        failures.append("missing scanning step")
    if not _SORT_RE.search(body):
        failures.append("missing sort / routing step")
    if not _FAILURE_RE.search(body):
        failures.append("missing automation failure / exception / jam")
    if not _RECEIVE_RE.search(body):
        failures.append("missing receiving / unloading / induction")
    if not _START_END_RE.search(body):
        failures.append("missing start / end / dispatch")
    if not _REWORK_RE.search(body):
        failures.append("missing manual triage / rework")
    return OracleResult(
        passed=not failures,
        failures=failures,
        labeled_shapes=labeled_shapes,
        connector_count=connector_count,
        labeled_chars=labeled_chars,
    )


def score_artifact(path: Path | str) -> OracleResult:
    drawing = Path(path)
    if not drawing.is_file():
        return OracleResult(passed=False, failures=[f"drawing not found: {drawing}"])
    if drawing.suffix.lower() != ".odg":
        return OracleResult(
            passed=False,
            failures=[f"Draw deliverable required (.odg), not {drawing.suffix}"],
        )
    try:
        extract = read_odg_drawing(drawing)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read drawing: {exc}"])
    return score_drawing(
        extract.text,
        labeled_shapes=extract.labeled_shapes,
        connector_count=extract.connector_count,
        labeled_chars=extract.labeled_chars,
    )


def format_result(result: OracleResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        status,
        (
            f"  labeled_shapes: {result.labeled_shapes}  "
            f"connectors: {result.connector_count}  "
            f"labeled_chars: {result.labeled_chars}"
        ),
    ]
    for item in result.failures:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifact",
        type=Path,
        help="Saved drawing (.odg) or trial directory",
    )
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args(argv)
    drawing = resolve_draw_artifact(args.artifact)
    if drawing is None:
        result = OracleResult(
            passed=False,
            failures=[f"need a Draw .odg (artifact={args.artifact})"],
        )
    else:
        result = score_artifact(drawing)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

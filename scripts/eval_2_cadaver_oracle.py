#!/usr/bin/env python3
# WriterAgent - eval-2 / Cadaver Proposal Writer oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed structural scorer for an eval-2 Cadaver Proposal.

Pass/fail is document-local. Chat Ready / STREAM_DONE is never consulted.
Fixture cells ($2,000 or bundled $3,000; $1,000 lab fee) fail closed.
Gold's Silverview hospital name is not a scored string.

Usage:
  .venv/bin/python scripts/eval_2_cadaver_oracle.py path/to/final_proposal.odt
  .venv/bin/python scripts/eval_2_headed.py --task cadaver-proposal --score path/to/final_proposal.odt
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_WORD_MIN = 250
_WORD_MAX = 3000

_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
_HOPE_RE = re.compile(r"hope\s+hospital", re.I)
_GEN_SURG_RE = re.compile(r"general\s+surgery", re.I)
_THORACIC_RE = re.compile(r"thoracic\s+surgery", re.I)
_ENT_RE = re.compile(r"otolaryngology", re.I)
_ORTHO_RE = re.compile(r"orthopedic\s+surgery", re.I)
_INTRO_RE = re.compile(r"\bintroduction\b", re.I)
_COST_RE = re.compile(r"cost\s+saving|cost-saving|\bsavings\b", re.I)
_GRAPH_RE = re.compile(r"\bgraphs?\b|\bcharts?\b", re.I)
_DOLLAR_RE = re.compile(r"\$")
_PARTICIPATION_RE = re.compile(
    r"1\s*[-–to]+\s*4|\b1\b.{0,40}\b2\b.{0,40}\b3\b.{0,40}\b4\b.{0,20}depart",
    re.I,
)
_CADAVER_2000_RE = re.compile(r"\$?\s*2,000|\$?\s*2000")
_CADAVER_3000_RE = re.compile(r"\$?\s*3,000|\$?\s*3000")
_LAB_FEE_RE = re.compile(r"\$?\s*1,000|\$?\s*1000")
_FOUR_CADAVERS_RE = re.compile(r"\b4\s+cadavers\b|\bfour\s+cadavers\b", re.I)
_SUPPLIES_RE = re.compile(r"\bsupplies\b", re.I)
_EDUCATION_RE = re.compile(r"\beducation\b", re.I)
_ETHICS_RE = re.compile(
    r"donat|donor|respect.{0,40}bod|honor.{0,20}donor|final\s+wishes|maximi[sz]e.{0,40}cadaver",
    re.I,
)
_ABDOMEN_RE = re.compile(r"\babdomen\b|\babdominal\b", re.I)
_THORAX_RE = re.compile(r"\bthorax\b|\bthoracic\b", re.I)
_HEAD_NECK_RE = re.compile(r"head\s*(?:and|\/|&)\s*neck|\bneck\b", re.I)
_LIMB_RE = re.compile(r"\blimbs?\b|\bshoulder\b|\bforearm\b|\bthigh\b", re.I)
_CYCLES_RE = re.compile(r"10\s*[-–to]+\s*12|10\s+to\s+12", re.I)
_THREE_HOUR_RE = re.compile(r"\b3[\s\-]*hours?\b", re.I)
_SIMPLE_MIN_RE = re.compile(r"30\s*[-–to]+\s*45")
_STANDARD_HR_RE = re.compile(r"1\s*[-–to.]+\s*1\.?\s*5|1\s*[-–]\s*1\.5|hour to an hour and a half", re.I)
_COMPLEX_HR_RE = re.compile(r"2\s*[-–to]+\s*3")
_SIMPLE_RANGE_40_RE = re.compile(r"\b40\b")
_SIMPLE_RANGE_48_RE = re.compile(r"\b48\b")
_MIXING_RE = re.compile(r"mix(?:ing|ed)?\s+complex|not account for mix|does not account for mix|no mixing", re.I)


@dataclass
class OracleResult:
    """Fail-closed proposal checks. Ready is never a field."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    word_count: int = 0
    para_count: int = 0

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def _docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    paras: list[str] = []
    for para in root.iter(f"{{{_W_NS}}}p"):
        text = "".join(node.text or "" for node in para.iter(f"{{{_W_NS}}}t"))
        paras.append(text)
    return paras


def _odt_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    return ["".join(node.itertext()) for node in root.iter(f"{{{_TEXT_NS}}}p")]


def _docx_table_text(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    cells: list[str] = []
    for cell in root.iter(f"{{{_W_NS}}}tc"):
        text = "".join(node.text or "" for node in cell.iter(f"{{{_W_NS}}}t"))
        cells.append(text)
    return cells


def _odt_table_text(path: Path) -> list[str]:
    table_ns = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    return ["".join(node.itertext()) for node in root.iter(f"{{{table_ns}}}table-cell")]


def read_proposal_paragraphs(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_paragraphs(path) + _docx_table_text(path)
    if suffix == ".odt":
        return _odt_paragraphs(path) + _odt_table_text(path)
    raise ValueError(f"unsupported proposal type: {path.suffix}")


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def score_text(text: str, *, para_count: int) -> OracleResult:
    """Apply fail-closed checks to extracted proposal text."""
    failures: list[str] = []
    words = _word_count(text)
    if not text.strip():
        failures.append("proposal body is empty")
    if words < _WORD_MIN:
        failures.append(f"word_count {words} < {_WORD_MIN} (Ready-empty / too short)")
    if words > _WORD_MAX:
        failures.append(f"word_count {words} > {_WORD_MAX} (not a mini proposal)")
    if _HUSK_RE.search(text):
        failures.append("body contains Error:/husk residue")
    if not _HOPE_RE.search(text):
        failures.append("missing Hope Hospital")
    if not _GEN_SURG_RE.search(text):
        failures.append("missing General Surgery")
    if not _THORACIC_RE.search(text):
        failures.append("missing Thoracic Surgery")
    if not _ENT_RE.search(text):
        failures.append("missing Otolaryngology")
    if not _ORTHO_RE.search(text):
        failures.append("missing Orthopedic Surgery")
    if not _INTRO_RE.search(text):
        failures.append("missing introduction section")
    if not _COST_RE.search(text):
        failures.append("missing cost-savings theme")
    if not _GRAPH_RE.search(text) and not (_DOLLAR_RE.search(text) and _PARTICIPATION_RE.search(text)):
        failures.append("missing graph/chart or 1-4 department savings")
    if not (_CADAVER_2000_RE.search(text) or _CADAVER_3000_RE.search(text)):
        failures.append("missing cadaver unit cost $2,000 or bundled $3,000")
    if not _LAB_FEE_RE.search(text):
        failures.append("missing lab fee $1,000")
    if not _FOUR_CADAVERS_RE.search(text):
        failures.append("missing 4 cadavers baseline")
    if not _SUPPLIES_RE.search(text):
        failures.append("missing supplies exclusion")
    if not _EDUCATION_RE.search(text):
        failures.append("missing education exclusion")
    if not _ETHICS_RE.search(text):
        failures.append("missing donor-respect / maximize-use section")
    if not _ABDOMEN_RE.search(text):
        failures.append("missing abdomen assignment")
    if not _THORAX_RE.search(text):
        failures.append("missing thorax assignment")
    if not _HEAD_NECK_RE.search(text):
        failures.append("missing head/neck assignment")
    if not _LIMB_RE.search(text):
        failures.append("missing limb assignment")
    if not _CYCLES_RE.search(text):
        failures.append("missing 10-12 freeze/thaw cycles")
    if not _THREE_HOUR_RE.search(text):
        failures.append("missing 3-hour thawed window")
    if not _SIMPLE_MIN_RE.search(text):
        failures.append("missing simple 30-45 minute duration")
    if not _STANDARD_HR_RE.search(text):
        failures.append("missing standard 1-1.5 hour duration")
    if not _COMPLEX_HR_RE.search(text):
        failures.append("missing complex 2-3 hour duration")
    if not _SIMPLE_RANGE_40_RE.search(text):
        failures.append("missing simple per-cadaver 40")
    if not _SIMPLE_RANGE_48_RE.search(text):
        failures.append("missing simple per-cadaver 48")
    if not _MIXING_RE.search(text):
        failures.append("missing no-mixing-complexity disclaimer")
    return OracleResult(
        passed=not failures,
        failures=failures,
        word_count=words,
        para_count=para_count,
    )


def score_proposal(path: Path | str) -> OracleResult:
    proposal = Path(path)
    if not proposal.is_file():
        return OracleResult(passed=False, failures=[f"proposal not found: {proposal}"])
    try:
        paras = read_proposal_paragraphs(proposal)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read proposal: {exc}"])
    text = "\n".join(paras)
    nonempty = sum(1 for para in paras if para.strip())
    return score_text(text, para_count=nonempty)


def format_result(result: OracleResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        status,
        f"  words: {result.word_count}  paras: {result.para_count}",
    ]
    for item in result.failures:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path, help="Saved trial .odt (or .docx)")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args(argv)
    result = score_proposal(args.proposal)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

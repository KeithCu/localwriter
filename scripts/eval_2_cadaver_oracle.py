#!/usr/bin/env python3
# WriterAgent - eval-2 / Cadaver Proposal Writer oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed structural scorer for an eval-2 Cadaver Proposal.

Eliyezer-locked v1. Pass/fail is document-local. Chat Ready / STREAM_DONE
is never consulted. Exact dollars, lab-fee share, and chart pixels are
out of v1. Gold's Silverview hospital name is not a scored string.

ODT extraction reads ``text:h`` and ``text:p`` in document order (headed
Writer often puts the title in a heading). DOCX headings are ``w:p``.

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
_WORD_MAX = 2500

_I = re.IGNORECASE | re.DOTALL
_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"collaborative\s+cadaver\s+program", re.I)
_GEN_SURG_RE = re.compile(r"general\s+surgery", re.I)
_THORACIC_RE = re.compile(r"thoracic\s+surgery", re.I)
_ENT_RE = re.compile(r"otolaryngology", re.I)
_ORTHO_RE = re.compile(r"orthopedic\s+surgery", re.I)
_INTRO_RE = re.compile(r"\bintroduction\b", re.I)
_COST_RE = re.compile(r"cost\s+saving|cost-saving|\bsavings\b", re.I)
_ETHICS_RE = re.compile(
    r"donat|donor|honor.{0,20}donor|final\s+wishes|maximi[sz]e.{0,40}(?:cadaver|use)",
    _I,
)
_GRAPH_RE = re.compile(r"\bgraphs?\b|\bcharts?\b", re.I)
_SAVINGS_TABLE_RE = re.compile(
    r"(?:savings?\s+table|table.{0,40}savings?|1\s*[-–to]+\s*4.{0,40}depart)",
    _I,
)
_PER_CADAVER_RE = re.compile(r"per[\s\-]*cadaver", re.I)
_LAB_FEE_RE = re.compile(r"annual\s+cadaver\s+lab\s+fee|(?:anatomy\s+)?lab\s+fee", re.I)
_EXCLUDE_RE = re.compile(
    r"exclud(?:e|es|ed|ing).{0,80}supplies.{0,60}education"
    r"|exclud(?:e|es|ed|ing).{0,80}education.{0,60}supplies"
    r"|supplies.{0,40}and.{0,20}education.{0,40}exclud",
    _I,
)
_FOUR_YEAR_RE = re.compile(
    r"(?:4|four)\s+cadavers(?:\s*/\s*year|\s+per\s+year|\s+each\s+year|\s+a\s+year)?",
    re.I,
)
_FORMULA_RE = re.compile(
    r"\(?\s*4\s*[×x*]\s*(?:the\s+)?per[\s\-]*cadaver.?\)?\s*(?:\+|plus)\s*.{0,24}lab\s+fee"
    r"|4\s*[×x*]\s*(?:the\s+)?per[\s\-]*cadaver.{0,40}(?:\+|plus).{0,20}lab\s+fee",
    _I,
)
_ABDOMEN_RE = re.compile(r"\babdomen\b|\babdominal\b", re.I)
_THORAX_RE = re.compile(r"\bthorax\b|\bthoracic\b", re.I)
_HEAD_NECK_RE = re.compile(r"head\s*(?:and|\/|&)\s*neck", re.I)
_LIMB_RE = re.compile(r"\blimbs?\b", re.I)
_CYCLES_RE = re.compile(r"10\s*[-–to]+\s*12", re.I)
_THREE_HOUR_RE = re.compile(r"\b3[\s\-]*h(?:ours?)?\b", re.I)
_SIMPLE_MIN_RE = re.compile(r"30\s*[-–to]+\s*45")
_STANDARD_HR_RE = re.compile(r"1\s*[-–.]+\s*1\.?5|1\s*[-–]\s*1\.5|hour to an hour and a half", re.I)
_COMPLEX_HR_RE = re.compile(r"2\s*[-–to]+\s*3")
_WINDOW_SIMPLE_RE = re.compile(
    r"simple.{0,50}(?:up\s+to|<=|≤)\s*4|(?:up\s+to|<=|≤)\s*4.{0,30}simple",
    _I,
)
_WINDOW_STANDARD_RE = re.compile(
    r"standard.{0,40}2\s*[-–to]+\s*3|2\s*[-–to]+\s*3.{0,40}standard",
    _I,
)
_WINDOW_COMPLEX_RE = re.compile(
    r"complex.{0,40}(?:only\s+)?(?:one|1)\b|(?:one|1)\s+(?:complex|procedure).{0,30}complex",
    _I,
)
_SIMPLE_40_RE = re.compile(r"\b40\b")
_SIMPLE_48_RE = re.compile(r"\b48\b")
_STANDARD_20_RE = re.compile(r"\b20\b")
_STANDARD_36_RE = re.compile(r"\b36\b")
_COMPLEX_10_RE = re.compile(r"\b10\b")
_COMPLEX_12_RE = re.compile(r"\b12\b")
_MIXING_RE = re.compile(
    r"does\s+not\s+account\s+for\s+mix|not\s+account\s+for\s+mix|no\s+mixing|without\s+mixing",
    re.I,
)


@dataclass
class OracleResult:
    """Fail-closed proposal checks. Ready is never a field."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    word_count: int = 0
    para_count: int = 0

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def _docx_blocks(path: Path) -> list[str]:
    """DOCX headings are ordinary ``w:p`` nodes; walk document order."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    blocks: list[str] = []
    for para in root.iter(f"{{{_W_NS}}}p"):
        text = "".join(node.text or "" for node in para.iter(f"{{{_W_NS}}}t"))
        blocks.append(text)
    return blocks


def _odt_blocks(path: Path) -> list[str]:
    """Headed Writer titles often live in ``text:h``, body in ``text:p``."""
    heading = f"{{{_TEXT_NS}}}h"
    para = f"{{{_TEXT_NS}}}p"
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    return [
        "".join(node.itertext())
        for node in root.iter()
        if node.tag in {heading, para}
    ]


def read_proposal_blocks(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_blocks(path)
    if suffix == ".odt":
        return _odt_blocks(path)
    raise ValueError(f"unsupported proposal type: {path.suffix}")


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _cost_savings_comes_first(text: str) -> bool:
    """Intro must lead with cost savings, not the ethics/anatomy section."""
    cost = _COST_RE.search(text)
    ethics = _ETHICS_RE.search(text)
    if cost is None:
        return False
    if ethics is None:
        return True
    return cost.start() < ethics.start()


def score_text(text: str, *, para_count: int) -> OracleResult:
    """Apply Eliyezer-locked v1 checks to extracted proposal text."""
    failures: list[str] = []
    words = _word_count(text)
    if not text.strip():
        failures.append("proposal body is empty")
    if words < _WORD_MIN:
        failures.append(f"word_count {words} < {_WORD_MIN} (Ready-empty / too short)")
    if words > _WORD_MAX:
        failures.append(f"word_count {words} > {_WORD_MAX} (tune after first headed)")
    if _HUSK_RE.search(text):
        failures.append("body contains Error:/husk residue")
    if not _TITLE_RE.search(text):
        failures.append("missing Collaborative Cadaver Program title theme")
    if not _GEN_SURG_RE.search(text):
        failures.append("missing General Surgery")
    if not _THORACIC_RE.search(text):
        failures.append("missing Thoracic Surgery")
    if not _ENT_RE.search(text):
        failures.append("missing Otolaryngology")
    if not _ORTHO_RE.search(text):
        failures.append("missing Orthopedic Surgery")
    if not _INTRO_RE.search(text):
        failures.append("missing introduction")
    if not _COST_RE.search(text):
        failures.append("missing cost-savings purpose")
    elif not _cost_savings_comes_first(text):
        failures.append("cost-savings purpose is not first")
    if not _PER_CADAVER_RE.search(text):
        failures.append("missing per-cadaver cost input")
    if not _LAB_FEE_RE.search(text):
        failures.append("missing Annual Cadaver Lab Fee / lab fee")
    if not _EXCLUDE_RE.search(text):
        failures.append("missing exclude Supplies and Education")
    if not _FOUR_YEAR_RE.search(text):
        failures.append("missing 4 cadavers/year General Surgery baseline")
    if not _FORMULA_RE.search(text):
        failures.append("missing (4 × per-cadaver) + lab fee formula")
    if not _GRAPH_RE.search(text) and not _SAVINGS_TABLE_RE.search(text):
        failures.append("missing graph/chart or labeled 1-4 savings table")
    if not _ETHICS_RE.search(text):
        failures.append("missing donor-respect / maximize-use section")
    if not _ABDOMEN_RE.search(text):
        failures.append("missing abdomen → General Surgery")
    if not _THORAX_RE.search(text):
        failures.append("missing thorax → Thoracic")
    if not _HEAD_NECK_RE.search(text):
        failures.append("missing head/neck → Otolaryngology")
    if not _LIMB_RE.search(text):
        failures.append("missing limb(s) → Orthopedic")
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
    if not _WINDOW_SIMPLE_RE.search(text):
        failures.append("missing simple ≤4 procedures per window")
    if not _WINDOW_STANDARD_RE.search(text):
        failures.append("missing standard 2-3 procedures per window")
    if not _WINDOW_COMPLEX_RE.search(text):
        failures.append("missing complex 1 procedure per window")
    if not (_SIMPLE_40_RE.search(text) and _SIMPLE_48_RE.search(text)):
        failures.append("missing simple totals 40-48")
    if not (_STANDARD_20_RE.search(text) and _STANDARD_36_RE.search(text)):
        failures.append("missing standard totals 20-36")
    if not (_COMPLEX_10_RE.search(text) and _COMPLEX_12_RE.search(text)):
        failures.append("missing complex totals 10-12")
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
        blocks = read_proposal_blocks(proposal)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read proposal: {exc}"])
    text = "\n".join(blocks)
    nonempty = sum(1 for block in blocks if block.strip())
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

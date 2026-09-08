#!/usr/bin/env python3
# WriterAgent - eval-2 / Cadaver Proposal Writer oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed structural scorer for an eval-2 Cadaver Proposal.

Eliyezer-locked v1, softened after a headed Gemini false-red (Tenant #665
style). Pass/fail is document-local. Chat Ready / STREAM_DONE is never
consulted. Exact lab-fee share and chart pixels stay out of v1. Gold's
Silverview hospital name is not a scored string.

ODT extraction reads ``text:h`` and ``text:p`` in document order (headed
Writer often puts the title in a heading). DOCX headings are ``w:p``.
Embedded ``draw:frame`` / ``table:table`` count as graph/table evidence
only when nearby caption/text mentions savings or 1–4 departments.

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
_DRAW_NS = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_TEXT_H = f"{{{_TEXT_NS}}}h"
_TEXT_P = f"{{{_TEXT_NS}}}p"
_DRAW_FRAME = f"{{{_DRAW_NS}}}frame"
_TABLE_TABLE = f"{{{_TABLE_NS}}}table"
_WORD_MIN = 250
# First headed Gemini proposal was ~9 pages and above 2500; 3200 is the
# Eliyezer lock (min stays 250 so Ready-empty husks still fail).
_WORD_MAX = 3200
_VISUAL_NEAR_RADIUS = 3

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
# Headed drafts use Overview / Executive Summary instead of "Introduction".
_INTRO_RE = re.compile(
    r"\bintroduction\b|\bexecutive\s+summary\b|\bprogram\s+overview\b|\boverview\b",
    re.I,
)
_COST_RE = re.compile(r"cost\s+saving|cost-saving|\bsavings\b", re.I)
_ETHICS_RE = re.compile(
    r"donat|donor|honor.{0,20}donor|final\s+wishes|maximi[sz]e.{0,40}(?:cadaver|use)",
    _I,
)
# Dedicated ethics/stewardship *section* — not mid-overview "honor donors".
_ETHICS_SECTION_HEADING_RE = re.compile(
    r"^(?:#{1,3}\s*|\d+[\.\):]\s*)?(?:ethical(?:\s+use|\s+consider|\s+import|\s+steward)?"
    r"|ethics|stewardship"
    r"|honou?ring\s+donors?"
    r"|respect(?:ing)?\s+(?:the\s+)?(?:bodies|donors)"
    r"|maximi[sz]ing\s+(?:cadaver\s+)?use"
    r"|anatomical\s+assignment|anatomy\s+(?:assignment|map|section))\b",
    re.I | re.M,
)
_COST_HEADING_RE = re.compile(
    r"cost\s*[- ]*saving|financial|budget|savings?\s+analys|cost\s+analys"
    r"|program\s+costs?|annual\s+costs?",
    re.I,
)
# Anatomy *assignment* headings, not "Anatomy Lab Fee" cost titles.
_ETHICS_ANATOMY_HEADING_RE = re.compile(
    r"\bethic|\bstewardship\b|anatomical\s+assign|anatomy\s+(?:assign|map|section|areas)"
    r"|honou?ring\s+donors?|donor\s+respect|maximi[sz]ing\s+(?:cadaver\s+)?use",
    re.I,
)
# "chart" inside "charter" is not a figure; accept Graphical / Figure N too.
_GRAPH_RE = re.compile(
    r"\bgraphs?\b|\bcharts?\b|\bfigures?\b|graphical\s+representation",
    re.I,
)
_SAVINGS_TABLE_RE = re.compile(
    r"(?:savings?\s+table|table.{0,40}savings?|1\s*[-–to]+\s*4.{0,40}depart)",
    _I,
)
# Nearby caption/text for an embedded frame or table — not the frame alone.
_SAVINGS_NEAR_RE = re.compile(
    r"saving|1\s*[-–to]+\s*4.{0,48}depart|departments?.{0,32}participat",
    re.I,
)
_PER_CADAVER_RE = re.compile(r"per[\s\-]*cadaver", re.I)
# Fixture used "Annual Anatomy Lab Facility Fee"; require an anatomy/lab tie.
_LAB_FEE_RE = re.compile(
    r"(?:annual\s+)?(?:cadaver\s+)?lab\s+fee"
    r"|anatomy\s+lab.{0,48}fee"
    r"|lab\s+facility\s+fee"
    r"|(?:anatomy|cadaver).{0,32}facility\s+fee"
    r"|facility\s+fee.{0,32}(?:anatomy|cadaver|lab)",
    re.I,
)
_SUPPLIES_RE = re.compile(r"\bsupplies\b", re.I)
_EDUCATION_RE = re.compile(r"\beducation\b", re.I)
# Either order supplies↔education with an exclude verb; both names required.
_EXCLUDE_BOTH_RE = re.compile(
    r"exclud(?:e|es|ed|ing).{0,160}supplies.{0,80}education"
    r"|exclud(?:e|es|ed|ing).{0,160}education.{0,80}supplies"
    r"|supplies.{0,80}education.{0,80}exclud(?:e|es|ed|ing)"
    r"|education.{0,80}supplies.{0,80}exclud(?:e|es|ed|ing)"
    r"|supplies.{0,80}exclud(?:e|es|ed|ing).{0,80}education"
    r"|education.{0,80}exclud(?:e|es|ed|ing).{0,80}supplies",
    _I,
)
_FOUR_YEAR_RE = re.compile(
    r"(?:4|four)\s+cadavers(?:\s*/\s*year|\s+per\s+year|\s+each\s+year|\s+a\s+year)?",
    re.I,
)
_FORMULA_RE = re.compile(
    r"\(?\s*4\s*[×x*]\s*(?:the\s+)?per[\s\-]*(?:cadaver|specimen).?\)?\s*(?:\+|plus)\s*.{0,24}(?:lab|facility)\s+fee"
    r"|4\s*[×x*]\s*(?:the\s+)?per[\s\-]*(?:cadaver|specimen).{0,40}(?:\+|plus).{0,24}(?:lab|facility)\s+fee"
    r"|(?:4|four)\s+(?:times|x)\s+(?:the\s+)?per[\s\-]*(?:cadaver|specimen).{0,40}(?:\+|plus).{0,40}(?:lab|facility)\s+fee",
    _I,
)
_THOUSANDS_RE = r"(?:\$?\s*3(?:\s*,\s*)?000|\b3k\b|\$?\s*3\s*thousand)"
_ONE_K_RE = r"(?:\$?\s*1(?:\s*,\s*)?000|\b1k\b|\$?\s*1\s*thousand)"
_THIRTEEN_K_RE = r"(?:\$?\s*13(?:\s*,\s*)?000|\b13k\b|\$?\s*13\s*thousand)"
# Gold baseline is 4 × $3,000 + $1,000 = $13,000. Accept that arithmetic
# in prose so a literal "(4 × per-cadaver) + lab fee" string is not required.
_ARITH_FORMULA_RE = re.compile(
    rf"(?:{_THOUSANDS_RE}.{{0,28}}(?:[×x*]|times).{{0,16}}(?:4|four).{{0,28}}"
    rf"(?:\+|plus).{{0,28}}{_ONE_K_RE}.{{0,28}}(?:(?:=|equals).{{0,16}}{_THIRTEEN_K_RE})?)"
    rf"|(?:(?:4|four).{{0,16}}(?:[×x*]|times).{{0,28}}{_THOUSANDS_RE}.{{0,28}}"
    rf"(?:\+|plus).{{0,28}}{_ONE_K_RE}.{{0,28}}(?:(?:=|equals).{{0,16}}{_THIRTEEN_K_RE})?)"
    rf"|(?:{_THOUSANDS_RE}.{{0,16}}(?:\+|plus).{{0,16}}{_ONE_K_RE}.{{0,16}}"
    rf"(?:=|equals).{{0,16}}{_THIRTEEN_K_RE})",
    _I,
)
_ABDOMEN_RE = re.compile(r"\babdomen\b|\babdominal\b", re.I)
_THORAX_RE = re.compile(r"\bthorax\b|\bthoracic\b", re.I)
_HEAD_NECK_RE = re.compile(r"head\s*(?:and|\/|&)\s*neck", re.I)
_LIMB_RE = re.compile(r"\blimbs?\b", re.I)
_CYCLES_RE = re.compile(r"10\s*[-–to]+\s*12", re.I)
_THREE_HOUR_RE = re.compile(r"\b3[\s\-]*h(?:ours?)?\b", re.I)
_SIMPLE_MIN_RE = re.compile(r"30\s*[-–to]+\s*45")
_STANDARD_HR_RE = re.compile(
    r"1\s*[-–.]+\s*1\.?5|1\s*[-–]\s*1\.5|hour to an hour and a half"
    r"|60\s*[-–to]+\s*90|60\s+to\s+90",
    re.I,
)
_WINDOW_SIMPLE_RE = re.compile(
    r"simple.{0,60}(?:up\s+to|<=|≤|at\s+most)\s*4"
    r"|(?:up\s+to|<=|≤)\s*4.{0,40}simple"
    r"|3\s*(?:[-–]|to)\s*4.{0,50}(?:simple|per\s+(?:thaw|window)|procedures?\s+per)"
    r"|(?:simple|per\s+(?:thaw|window)).{0,50}3\s*(?:[-–]|to)\s*4",
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


@dataclass
class ProposalExtract:
    """Text blocks plus heading-order / embedded-visual evidence."""

    blocks: list[str]
    headings: list[str]
    has_savings_visual: bool


def _elem_text(elem: ET.Element) -> str:
    return "".join(elem.itertext())


def _docx_is_heading(para: ET.Element) -> bool:
    ppr = para.find(f"{{{_W_NS}}}pPr")
    if ppr is None:
        return False
    style = ppr.find(f"{{{_W_NS}}}pStyle")
    if style is not None:
        val = style.get(f"{{{_W_NS}}}val") or ""
        if re.search(r"heading|title", val, re.I):
            return True
    return ppr.find(f"{{{_W_NS}}}outlineLvl") is not None


def _docx_has_drawing(para: ET.Element) -> bool:
    return (
        para.find(f"{{{_W_NS}}}drawing") is not None
        or para.find(f"{{{_W_NS}}}pict") is not None
    )


def _window_has_savings(items: list[tuple[str, str]], index: int) -> bool:
    start = max(0, index - _VISUAL_NEAR_RADIUS)
    end = min(len(items), index + _VISUAL_NEAR_RADIUS + 1)
    blob = " ".join(text for unused_kind, text in items[start:end])
    return bool(_SAVINGS_NEAR_RE.search(blob))


def _has_savings_visual(items: list[tuple[str, str]]) -> bool:
    """Embedded frame/table counts only with nearby savings / 1–4 depts."""
    for index, (kind, unused_text) in enumerate(items):
        if kind in {"frame", "table"} and _window_has_savings(items, index):
            return True
    return False


def _docx_extract(path: Path) -> ProposalExtract:
    """DOCX headings are ordinary ``w:p``; drawings/tables are visual items."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    blocks: list[str] = []
    headings: list[str] = []
    items: list[tuple[str, str]] = []
    body = root.find(f"{{{_W_NS}}}body")
    for child in body if body is not None else root:
        if child.tag == f"{{{_W_NS}}}tbl":
            text = _elem_text(child)
            items.append(("table", text))
            blocks.append(text)
            continue
        if child.tag != f"{{{_W_NS}}}p":
            continue
        text = "".join(node.text or "" for node in child.iter(f"{{{_W_NS}}}t"))
        blocks.append(text)
        if _docx_is_heading(child):
            headings.append(text)
            items.append(("h", text))
        else:
            items.append(("p", text))
        if _docx_has_drawing(child):
            items.append(("frame", text))
    return ProposalExtract(
        blocks=blocks,
        headings=headings,
        has_savings_visual=_has_savings_visual(items),
    )


def _walk_odt(elem: ET.Element) -> list[tuple[str, str]]:
    """Document-order items: headings, paras, frames, tables."""
    items: list[tuple[str, str]] = []
    tag = elem.tag
    if tag == _DRAW_FRAME:
        name = elem.get(f"{{{_DRAW_NS}}}name") or ""
        items.append(("frame", f"{_elem_text(elem)} {name}".strip()))
        for child in elem:
            items.extend(_walk_odt(child))
        return items
    if tag == _TABLE_TABLE:
        items.append(("table", _elem_text(elem)))
        for child in elem:
            items.extend(_walk_odt(child))
        return items
    if tag == _TEXT_H:
        items.append(("h", _elem_text(elem)))
        return items
    if tag == _TEXT_P:
        items.append(("p", _elem_text(elem)))
        return items
    for child in elem:
        items.extend(_walk_odt(child))
    return items


def _odt_extract(path: Path) -> ProposalExtract:
    """Headed Writer titles often live in ``text:h``, body in ``text:p``."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    items = _walk_odt(root)
    blocks = [text for kind, text in items if kind in {"h", "p"}]
    headings = [text for kind, text in items if kind == "h"]
    return ProposalExtract(
        blocks=blocks,
        headings=headings,
        has_savings_visual=_has_savings_visual(items),
    )


def read_proposal_blocks(path: Path) -> list[str]:
    return read_proposal(path).blocks


def read_proposal(path: Path) -> ProposalExtract:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_extract(path)
    if suffix == ".odt":
        return _odt_extract(path)
    raise ValueError(f"unsupported proposal type: {path.suffix}")


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _heading_kind(heading: str) -> str | None:
    """Cost/financial vs ethics/anatomy H2. Cost wins if a title matches both."""
    if _COST_HEADING_RE.search(heading):
        return "cost"
    if _ETHICS_ANATOMY_HEADING_RE.search(heading):
        return "ethics"
    return None


def _dedicated_ethics_pos(text: str, headings: list[str] | None) -> int | None:
    """Start index of the dedicated stewardship/ethics section, if any."""
    if headings:
        for heading in headings:
            if _ETHICS_SECTION_HEADING_RE.search(heading.strip()):
                pos = text.find(heading)
                if pos >= 0:
                    return pos
    match = _ETHICS_SECTION_HEADING_RE.search(text)
    return match.start() if match else None


def _cost_purpose_leads(text: str, headings: list[str] | None) -> bool:
    """Cost/financial H2 before ethics/anatomy H2, or cost-savings before ethics section.

    Early overview "honor donors" is not a dedicated ethics section. The old
    first-regex-hit of honor/donor was a false-red on headed Gemini drafts.
    """
    if headings:
        cost_i: int | None = None
        ethics_i: int | None = None
        for index, heading in enumerate(headings):
            kind = _heading_kind(heading)
            if kind == "cost" and cost_i is None:
                cost_i = index
            elif kind == "ethics" and ethics_i is None:
                ethics_i = index
        if cost_i is not None and (ethics_i is None or cost_i < ethics_i):
            return True
    cost = _COST_RE.search(text)
    if cost is None:
        return False
    ethics_pos = _dedicated_ethics_pos(text, headings)
    if ethics_pos is None:
        return True
    return cost.start() < ethics_pos


def _has_baseline_formula(text: str) -> bool:
    """Algebraic (4 × per-cadaver/specimen + lab/facility fee) or $3k+$1k=$13k."""
    return bool(_FORMULA_RE.search(text) or _ARITH_FORMULA_RE.search(text))


def _has_graph_or_savings_table(text: str, *, has_savings_visual: bool) -> bool:
    if _GRAPH_RE.search(text) or _SAVINGS_TABLE_RE.search(text):
        return True
    return has_savings_visual


def score_text(
    text: str,
    *,
    para_count: int,
    headings: list[str] | None = None,
    has_savings_visual: bool = False,
) -> OracleResult:
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
    elif not _cost_purpose_leads(text, headings):
        failures.append("cost-savings purpose is not first")
    if not _PER_CADAVER_RE.search(text):
        failures.append("missing per-cadaver cost input")
    if not _LAB_FEE_RE.search(text):
        failures.append("missing Annual Cadaver Lab Fee / lab fee")
    if not (_SUPPLIES_RE.search(text) and _EDUCATION_RE.search(text) and _EXCLUDE_BOTH_RE.search(text)):
        failures.append("missing exclude Supplies and Education")
    if not _FOUR_YEAR_RE.search(text):
        failures.append("missing 4 cadavers/year General Surgery baseline")
    if not _has_baseline_formula(text):
        failures.append("missing (4 × per-cadaver) + lab fee formula")
    if not _has_graph_or_savings_table(text, has_savings_visual=has_savings_visual):
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
        extract = read_proposal(proposal)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read proposal: {exc}"])
    text = "\n".join(extract.blocks)
    nonempty = sum(1 for block in extract.blocks if block.strip())
    return score_text(
        text,
        para_count=nonempty,
        headings=extract.headings,
        has_savings_visual=extract.has_savings_visual,
    )


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

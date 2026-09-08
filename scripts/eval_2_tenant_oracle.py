#!/usr/bin/env python3
# WriterAgent - eval-2 / Tenant Retention Writer memo oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed structural scorer for an eval-2 Tenant Retention memo.

Pass/fail is document-local. Chat Ready / STREAM_DONE is never consulted.
Gold-hard survey counts (9/20 rent increase, 5/20 community) fail closed.
The gold basename typo ``Rentention`` is not a scored string.

Usage:
  .venv/bin/python scripts/eval_2_tenant_oracle.py path/to/final_memo.odt
  .venv/bin/python scripts/eval_2_headed.py --task tenant-retention --score path/to/final_memo.odt
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
_WORD_MIN = 180
_WORD_MAX = 1400

_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
_HARBORVIEW_RE = re.compile(r"harborview\s+flats", re.I)
_STAMFORD_RE = re.compile(r"stamford", re.I)
_TEN_PCT_RE = re.compile(r"10\s*%")
_SIX_MONTHS_RE = re.compile(r"6\s*-\s*months?|6\s+months?", re.I)
_RENT_COUNT_RE = re.compile(r"9\s*/\s*20|9\s+out\s+of\s+20|9\s+of\s+20", re.I)
_RENT_PCT_RE = re.compile(r"45\s*%")
_RENT_THEME_RE = re.compile(r"rent\s+increase|price\s+sensitivity", re.I)
_COMMUNITY_COUNT_RE = re.compile(r"5\s*/\s*20|5\s+out\s+of\s+20|5\s+of\s+20", re.I)
_COMMUNITY_PCT_RE = re.compile(r"25\s*%")
_COMMUNITY_THEME_RE = re.compile(
    r"lack\s+of\s+community|feeling\s+disconnected|disconnected",
    re.I,
)
_EARLY_BIRD_RE = re.compile(r"early[\s\-]*bird", re.I)
_MONTH_TO_MONTH_RE = re.compile(r"month[\s\-]*to[\s\-]*month|\bm2m\b", re.I)
_PREMIUM_RE = re.compile(r"premium", re.I)
_TWO_EVENTS_RE = re.compile(r"\btwo\b.{0,40}\bevents?\b|\b2\b.{0,20}\bevents?\b", re.I)
_DEPARTURE_RE = re.compile(r"departure\s+reasons|analysis\s+of\s+departure", re.I)
_TIERED_RE = re.compile(r"tiered\s+renewal", re.I)
_COMM_PLAN_RE = re.compile(r"communication\s+plan", re.I)
_ENGAGEMENT_RE = re.compile(r"community\s+engagement", re.I)
_DAY_90_RE = re.compile(r"\b90[\s\-]*day|\b90\s+days?\b", re.I)
_DAY_60_RE = re.compile(r"\b60[\s\-]*day|\b60\s+days?\b", re.I)
_DAY_30_RE = re.compile(r"\b30[\s\-]*day|\b30\s+days?\b", re.I)


@dataclass
class OracleResult:
    """Fail-closed memo checks. Ready is never a field."""

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


def read_memo_paragraphs(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_paragraphs(path)
    if suffix == ".odt":
        return _odt_paragraphs(path)
    raise ValueError(f"unsupported memo type: {path.suffix}")


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def score_text(text: str, *, para_count: int) -> OracleResult:
    """Apply fail-closed checks to extracted memo text."""
    failures: list[str] = []
    words = _word_count(text)
    if not text.strip():
        failures.append("memo body is empty")
    if words < _WORD_MIN:
        failures.append(f"word_count {words} < {_WORD_MIN} (Ready-empty / too short)")
    if words > _WORD_MAX:
        failures.append(f"word_count {words} > {_WORD_MAX} (not 1-2 pages)")
    if _HUSK_RE.search(text):
        failures.append("body contains Error:/husk residue")
    if not _HARBORVIEW_RE.search(text):
        failures.append("missing Harborview Flats")
    if not _STAMFORD_RE.search(text):
        failures.append("missing Stamford")
    if not _TEN_PCT_RE.search(text):
        failures.append("missing 10% retention objective")
    if not _SIX_MONTHS_RE.search(text):
        failures.append("missing 6 months objective")
    if not _DEPARTURE_RE.search(text):
        failures.append("missing departure-reasons section")
    if not _TIERED_RE.search(text):
        failures.append("missing tiered renewal section")
    if not _COMM_PLAN_RE.search(text):
        failures.append("missing communication plan section")
    if not _ENGAGEMENT_RE.search(text):
        failures.append("missing community engagement section")
    if not _RENT_THEME_RE.search(text):
        failures.append("missing rent-increase theme")
    if not _RENT_COUNT_RE.search(text):
        failures.append("missing rent-increase 9/20 count")
    if not _RENT_PCT_RE.search(text):
        failures.append("missing rent-increase 45%")
    if not _COMMUNITY_THEME_RE.search(text):
        failures.append("missing lack of community / disconnected theme")
    if not _COMMUNITY_COUNT_RE.search(text):
        failures.append("missing community 5/20 count")
    if not _COMMUNITY_PCT_RE.search(text):
        failures.append("missing community 25%")
    if not _EARLY_BIRD_RE.search(text):
        failures.append("missing early-bird offer")
    if not _DAY_90_RE.search(text):
        failures.append("missing 90-day touchpoint")
    if not _DAY_60_RE.search(text):
        failures.append("missing 60-day standard / touchpoint")
    if not _DAY_30_RE.search(text):
        failures.append("missing 30-day touchpoint")
    if not _MONTH_TO_MONTH_RE.search(text):
        failures.append("missing month-to-month option")
    if not _PREMIUM_RE.search(text):
        failures.append("missing month-to-month premium")
    if not _TWO_EVENTS_RE.search(text):
        failures.append("missing two events")
    return OracleResult(
        passed=not failures,
        failures=failures,
        word_count=words,
        para_count=para_count,
    )


def score_memo(path: Path | str) -> OracleResult:
    memo = Path(path)
    if not memo.is_file():
        return OracleResult(passed=False, failures=[f"memo not found: {memo}"])
    try:
        paras = read_memo_paragraphs(memo)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read memo: {exc}"])
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
    parser.add_argument("memo", type=Path, help="Saved trial .odt (or .docx)")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args(argv)
    result = score_memo(args.memo)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

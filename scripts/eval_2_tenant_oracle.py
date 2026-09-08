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
_TEXT_P = f"{{{_TEXT_NS}}}p"
_TEXT_H = f"{{{_TEXT_NS}}}h"
_WORD_MIN = 180
# Table-heavy headed memos land ~1500 words; 1400 was a false-FAIL on format.
_WORD_MAX = 1800

_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
_HARBORVIEW_RE = re.compile(r"harborview\s+flats", re.I)
_STAMFORD_RE = re.compile(r"stamford", re.I)
_TEN_PCT_RE = re.compile(r"10\s*%")
_SIX_MONTHS_RE = re.compile(r"6\s*-\s*months?|6\s+months?", re.I)
_RENT_COUNT_RE = re.compile(r"9\s*/\s*20|9\s+out\s+of\s+20|9\s+of\s+20", re.I)
# Writer tables often store 45.0% (office:value) rather than "45%".
_RENT_PCT_RE = re.compile(r"45(?:\.0+)?\s*%|45\s+percent", re.I)
_RENT_THEME_RE = re.compile(r"rent\s+increase|price\s+sensitivity", re.I)
_COMMUNITY_COUNT_RE = re.compile(r"5\s*/\s*20|5\s+out\s+of\s+20|5\s+of\s+20", re.I)
_COMMUNITY_PCT_RE = re.compile(r"25(?:\.0+)?\s*%|25\s+percent", re.I)
_COMMUNITY_THEME_RE = re.compile(
    r"lack\s+of\s+community|feeling\s+disconnected|disconnected",
    re.I,
)
# Survey N lives in prose or a caption, not always glued to 9/20.
_SURVEY_N20_RE = re.compile(
    r"(?i)"
    r"(?:n\s*=\s*20)"
    r"|(?:\b20\s+(?:comments?|residents?|respondents?|exits?|surveys?|tenants?|responses?|people))"
    r"|(?:(?:survey|sample|feedback|comments?|respondents?|residents?).{0,48}\b20\b)"
    r"|(?:\b20\b.{0,48}(?:survey|comments?|residents?|respondents?|exits?|responses?))"
)
_EARLY_BIRD_RE = re.compile(r"early[\s\-]*bird", re.I)
_MONTH_TO_MONTH_RE = re.compile(r"month[\s\-]*to[\s\-]*month|\bm2m\b", re.I)
_PREMIUM_RE = re.compile(r"premium", re.I)
_TWO_EVENTS_RE = re.compile(r"\btwo\b.{0,40}\bevents?\b|\b2\b.{0,20}\bevents?\b", re.I)
# Heading extract is the main section fix; these ORs are belt-and-suspenders.
_DEPARTURE_RE = re.compile(
    r"departure\s+(?:reason|categor)\w*"
    r"|exit\s+(?:survey|analysis)"
    r"|why\s+(?:residents|tenants)\s+(?:left|leave)"
    r"|analysis\s+of\s+(?:resident\s+)?departure",
    re.I,
)
_TIERED_RE = re.compile(r"tiered\s+renewal", re.I)
_COMM_PLAN_RE = re.compile(
    r"communication\s+(?:plan|template|cadence)"
    r"|email\s+(?:draft|timeline|plan)"
    r"|renewal\s+notification",
    re.I,
)
_ENGAGEMENT_RE = re.compile(
    r"community\s+engagement"
    r"|resident\s+events?"
    r"|engagement\s+initiative",
    re.I,
)
_DAY_90_RE = re.compile(r"\b90[\s\-]*day|\b90\s+days?\b", re.I)
_DAY_60_RE = re.compile(r"\b60[\s\-]*day|\b60\s+days?\b", re.I)
_DAY_30_RE = re.compile(r"\b30[\s\-]*day|\b30\s+days?\b", re.I)
# Window for table-split "9" / "5" sitting in a cell next to the theme label.
_COUNT_WINDOW_BEFORE = 80
_COUNT_WINDOW_AFTER = 300


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
    """Body blocks in document order: ``text:p`` and ``text:h``.

    Heading-only section titles live in ``text:h``. Walking ``text:p``
    alone hid those titles (Gemini headed memo) and false-failed the
    section checks. Table cells already wrap ``text:p``, so cell text
    is included; document order keeps count-near-theme windows honest.
    """
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    blocks: list[str] = []
    for node in root.iter():
        if node.tag in (_TEXT_P, _TEXT_H):
            blocks.append("".join(node.itertext()))
    return blocks


def read_memo_paragraphs(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_paragraphs(path)
    if suffix == ".odt":
        return _odt_paragraphs(path)
    raise ValueError(f"unsupported memo type: {path.suffix}")


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _digit_near_theme(text: str, theme_re: re.Pattern[str], digit: int) -> bool:
    """Standalone digit in a short window around a theme mention."""
    digit_re = re.compile(rf"\b{digit}\b")
    for match in theme_re.finditer(text):
        start = max(0, match.start() - _COUNT_WINDOW_BEFORE)
        end = min(len(text), match.end() + _COUNT_WINDOW_AFTER)
        if digit_re.search(text[start:end]):
            return True
    return False


def _has_survey_count(
    text: str,
    *,
    digit: int,
    literal_re: re.Pattern[str],
    theme_re: re.Pattern[str],
) -> bool:
    """Literal ``9/20`` / ``9 of 20``, or split table: digit near theme + N=20.

    Writer tables put the count in one cell and the percent in the next, so
    the body never contains the token ``9/20``. Requiring that glue was a
    false-FAIL on format; the fixture still has to state survey N=20 and
    place ``9`` (or ``5``) next to the rent / community theme.
    """
    if literal_re.search(text):
        return True
    return bool(_SURVEY_N20_RE.search(text) and _digit_near_theme(text, theme_re, digit))


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
    if not _has_survey_count(
        text, digit=9, literal_re=_RENT_COUNT_RE, theme_re=_RENT_THEME_RE
    ):
        failures.append("missing rent-increase 9/20 count")
    if not _RENT_PCT_RE.search(text):
        failures.append("missing rent-increase 45%")
    if not _COMMUNITY_THEME_RE.search(text):
        failures.append("missing lack of community / disconnected theme")
    if not _has_survey_count(
        text, digit=5, literal_re=_COMMUNITY_COUNT_RE, theme_re=_COMMUNITY_THEME_RE
    ):
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

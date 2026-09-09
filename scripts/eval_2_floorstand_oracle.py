#!/usr/bin/env python3
# WriterAgent - eval-2 / Floorstand Writer→Calc oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Soft structural scorer for the eval-2 Floorstand Writer + Calc pair.

Pass/fail is document-local. Chat Ready / STREAM_DONE is never consulted.
Identity facts are gold-hard (floorstand / stores / shelf strip) but exact
gold dollars and unit counts are **not** required. Hyphen-like characters
fold to ASCII before those id checks. A still-blank scaffold or a
research-only store-list copy fails even if the email is well formatted.

Usage:
  .venv/bin/python scripts/eval_2_floorstand_oracle.py path/to/final_memo.odt
  .venv/bin/python scripts/eval_2_floorstand_oracle.py path/to/runs/<stamp>/
  .venv/bin/python scripts/eval_2_headed.py --task writer-calc-peer-write --score path/to/final_memo.odt
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from eval_2_headed import FLOORSTAND_BUDGET_ODS_NAME, FLOORSTAND_EMAIL_NAME
from eval_2_ods_oracle import Cell, read_workbook

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_TEXT_P = f"{{{_TEXT_NS}}}p"
_TEXT_H = f"{{{_TEXT_NS}}}h"
# Gold draft email is short; Ready-empty husks are far shorter.
_WORD_MIN = 40
_WORD_MAX = 2000
# Scaffold has two title cells. A written budget needs more than that.
_MIN_NONEMPTY_CELLS = 8
# Store-list refs have 1,200+ ids. A paste with no budget work is research-only.
_RESEARCH_ONLY_STORE_IDS = 100

_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
_FLOORSTAND_RE = re.compile(r"floor[\s\-]*stands?", re.I)
_STORE_RE = re.compile(r"\bstores?\b", re.I)
_SHELF_STRIP_RE = re.compile(r"shelf[\s\-]*strips?", re.I)
_COST_COMPARE_RE = re.compile(
    r"(?:original|revised).{0,40}(?:cost|budget|unit|program)"
    r"|(?:cost|budget|unit|program).{0,40}(?:original|revised)"
    r"|cost\s+per\s+unit|per[\s\-]*unit\s+cost|program\s+cost"
    r"|total\s+program|unit\s+cost",
    re.I,
)
_BUDGET_CITE_RE = re.compile(
    r"budget\s+workbook|floorstand\s+budget|floor[\s\-]*stand\s+budget"
    r"|program\s+(?:budget|cost)|updated\s+budget|holiday\s+floorstand"
    r"|workbook|spreadsheet",
    re.I,
)
_EMAIL_SUMMARY_RE = re.compile(
    r"(?:floor[\s\-]*stands?|units?).{0,40}(?:budget|program|total|produc)"
    r"|(?:budget|program).{0,40}(?:change|increase|variance|total)"
    r"|new\s+total|total\s+program|display\s+budget",
    re.I,
)
_STORE_ID_RE = re.compile(r"^\d{3,6}$")

_RESEARCH_WORKBOOK_NEEDLES = (
    "store list original",
    "holiday matrix",
    "matrix final count",
)
_RESEARCH_DOC_NEEDLES = ("email trail",)
_PREFERRED_EMAIL_NAMES = (
    "final_memo.odt",
    "final_email.odt",
    "final_email.docx",
    FLOORSTAND_EMAIL_NAME,
    "Final Email Deliverable.docx",
)
_PREFERRED_WORKBOOK_NAMES = (
    "final_workbook.ods",
    "final_workbook.xlsx",
    FLOORSTAND_BUDGET_ODS_NAME,
    "Deliverable Holiday Floorstand Budget.xlsx",
)

# Word/LO often emit U+2011 (non-breaking hyphen) in compounds.
# Fold those to ASCII '-' before identity searches. NBSP-adjacent spaces fold too.
_HYPHEN_LIKE_TO_ASCII = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2212": "-",  # minus sign
    "\u00a0": " ",  # NBSP
    "\u202f": " ",  # narrow NBSP
})


def normalize_hyphen_like(text: str) -> str:
    """Fold hyphen-like / NBSP so identity ids match ASCII needles."""
    return (text or "").translate(_HYPHEN_LIKE_TO_ASCII)


@dataclass
class OracleResult:
    """Fail-closed pair checks. Ready is never a field."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    word_count: int = 0
    para_count: int = 0
    nonempty_cells: int = 0
    sheet_count: int = 0

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
    """Body blocks in document order: ``text:p`` and ``text:h``."""
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


def _cell_is_empty(cell: Cell) -> bool:
    if cell.formula.strip():
        return False
    value = cell.value
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def workbook_stats(sheets: dict[str, list[list[Cell]]]) -> tuple[int, int, str, int]:
    """Return nonempty cells, sheet count, joined text, and store-id-like count."""
    parts: list[str] = []
    nonempty = 0
    store_ids = 0
    for name, rows in sheets.items():
        if name:
            parts.append(name)
        for row in rows:
            for cell in row:
                if _cell_is_empty(cell):
                    continue
                nonempty += 1
                for text in cell.texts():
                    stripped = str(text).strip()
                    if stripped:
                        parts.append(stripped)
                    if _STORE_ID_RE.match(stripped.replace(".0", "")):
                        store_ids += 1
    return nonempty, len(sheets), "\n".join(parts), store_ids


def _looks_research_workbook(path: Path) -> bool:
    lowered = path.name.casefold()
    return any(needle in lowered for needle in _RESEARCH_WORKBOOK_NEEDLES)


def _looks_research_doc(path: Path) -> bool:
    lowered = path.name.casefold()
    return any(needle in lowered for needle in _RESEARCH_DOC_NEEDLES)


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


def _preferred_in_dir(directory: Path, names: tuple[str, ...], suffix: str) -> Path | None:
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    extras: list[Path] = []
    for path in sorted(directory.glob(f"*{suffix}")):
        if suffix in {".ods", ".xlsx"} and _looks_research_workbook(path):
            continue
        if suffix in {".odt", ".docx"} and _looks_research_doc(path):
            continue
        extras.append(path)
    if extras:
        return extras[0]
    return None


def resolve_floorstand_artifacts(
    artifact: Path,
    *,
    workbook: Path | None = None,
    memo: Path | None = None,
) -> tuple[Path | None, Path | None]:
    """Pick the Writer email and Calc budget from a file or trial directory."""
    artifact = artifact.expanduser()
    memo_path = memo.expanduser() if memo is not None else None
    book_path = workbook.expanduser() if workbook is not None else None
    if artifact.is_dir():
        if memo_path is None:
            memo_path = _preferred_in_dir(artifact, _PREFERRED_EMAIL_NAMES, ".odt")
            if memo_path is None:
                memo_path = _preferred_in_dir(artifact, _PREFERRED_EMAIL_NAMES, ".docx")
        if book_path is None:
            book_path = _preferred_in_dir(artifact, _PREFERRED_WORKBOOK_NAMES, ".ods")
            if book_path is None:
                book_path = _preferred_in_dir(artifact, _PREFERRED_WORKBOOK_NAMES, ".xlsx")
        return memo_path, book_path
    suffix = artifact.suffix.lower()
    if suffix in {".ods", ".xlsx"}:
        book_path = book_path or artifact
        if memo_path is None:
            memo_path = _preferred_in_dir(artifact.parent, _PREFERRED_EMAIL_NAMES, ".odt")
            if memo_path is None:
                memo_path = _preferred_in_dir(artifact.parent, _PREFERRED_EMAIL_NAMES, ".docx")
        return memo_path, book_path
    memo_path = memo_path or artifact
    if book_path is None:
        book_path = _preferred_in_dir(artifact.parent, _PREFERRED_WORKBOOK_NAMES, ".ods")
        if book_path is None:
            book_path = _preferred_in_dir(artifact.parent, _PREFERRED_WORKBOOK_NAMES, ".xlsx")
    return memo_path, book_path


def score_pair(
    memo_text: str,
    workbook_text: str,
    *,
    para_count: int,
    nonempty_cells: int,
    sheet_count: int,
    store_id_count: int = 0,
) -> OracleResult:
    """Apply soft fail-closed checks to extracted email + workbook text."""
    failures: list[str] = []
    words = _word_count(memo_text)
    if not memo_text.strip():
        failures.append("memo body is empty")
    if words < _WORD_MIN:
        failures.append(f"word_count {words} < {_WORD_MIN} (Ready-empty / too short)")
    if words > _WORD_MAX:
        failures.append(f"word_count {words} > {_WORD_MAX}")
    if _HUSK_RE.search(memo_text) or _HUSK_RE.search(workbook_text):
        failures.append("body contains Error:/husk residue")
    if nonempty_cells < _MIN_NONEMPTY_CELLS:
        failures.append(
            f"workbook nonempty cells {nonempty_cells} < {_MIN_NONEMPTY_CELLS} "
            "(scaffold not written / research-only husk)"
        )
    if not _COST_COMPARE_RE.search(workbook_text):
        failures.append("workbook missing original/revised cost comparison")
    if store_id_count >= _RESEARCH_ONLY_STORE_IDS and not _COST_COMPARE_RE.search(
        workbook_text
    ):
        failures.append(
            "workbook looks like a store-list copy (research-only, not a write)"
        )
    combined = normalize_hyphen_like(f"{memo_text}\n{workbook_text}")
    memo_text = normalize_hyphen_like(memo_text)
    if not _FLOORSTAND_RE.search(combined):
        failures.append("missing floorstand / floor stand")
    if not _STORE_RE.search(combined):
        failures.append("missing store / stores")
    if not _SHELF_STRIP_RE.search(combined):
        failures.append("missing shelf strip")
    if not _BUDGET_CITE_RE.search(memo_text):
        failures.append("memo does not cite the budget / program workbook")
    if not _EMAIL_SUMMARY_RE.search(memo_text):
        failures.append("email missing floor-stand display budget summary")
    return OracleResult(
        passed=not failures,
        failures=failures,
        word_count=words,
        para_count=para_count,
        nonempty_cells=nonempty_cells,
        sheet_count=sheet_count,
    )


def score_artifacts(memo: Path | str, workbook: Path | str) -> OracleResult:
    memo_path = Path(memo)
    book_path = Path(workbook)
    if not memo_path.is_file():
        return OracleResult(passed=False, failures=[f"memo not found: {memo_path}"])
    if not book_path.is_file():
        return OracleResult(passed=False, failures=[f"workbook not found: {book_path}"])
    if _looks_research_workbook(book_path):
        return OracleResult(
            passed=False,
            failures=[f"refusing research-only store list as write target: {book_path.name}"],
        )
    try:
        paras = read_memo_paragraphs(memo_path)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read memo: {exc}"])
    try:
        sheets = read_workbook(book_path)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read workbook: {exc}"])
    memo_text = "\n".join(paras)
    nonempty, sheet_count, book_text, store_ids = workbook_stats(sheets)
    nonempty_paras = sum(1 for para in paras if para.strip())
    return score_pair(
        memo_text,
        book_text,
        para_count=nonempty_paras,
        nonempty_cells=nonempty,
        sheet_count=sheet_count,
        store_id_count=store_ids,
    )


def format_result(result: OracleResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        status,
        (
            f"  words: {result.word_count}  paras: {result.para_count}  "
            f"nonempty_cells: {result.nonempty_cells}  sheets: {result.sheet_count}"
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
        help="Saved email (.odt/.docx), workbook (.ods/.xlsx), or trial directory",
    )
    parser.add_argument("--workbook", type=Path, default=None, help="Calc budget path")
    parser.add_argument("--memo", type=Path, default=None, help="Writer email path")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args(argv)
    memo, workbook = resolve_floorstand_artifacts(
        args.artifact, workbook=args.workbook, memo=args.memo
    )
    if memo is None or workbook is None:
        result = OracleResult(
            passed=False,
            failures=[
                f"need both email and workbook (memo={memo}, workbook={workbook})",
            ],
        )
    else:
        result = score_artifacts(memo, workbook)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

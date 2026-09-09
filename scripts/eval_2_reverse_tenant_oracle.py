#!/usr/bin/env python3
# WriterAgent - eval-2 / Reverse Tenant (Theatre CBA) workbook oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Soft structural scorer for the eval-2 Reverse Tenant Theatre CBA workbook.

Pass/fail is document-local. Chat Ready / STREAM_DONE is never consulted.
The scored artifact is the **Calc deliverable**. The Writer CBA excerpt is a
research sibling and is only recorded as present when it sits next to the
workbook — missing brief does not fail a saved ``final_workbook``.

Checks stay soft: populated workbook, CBA / theatre / roster anchors, husk
ban. Exact gold payroll dollars are **not** required.

Usage:
  .venv/bin/python scripts/eval_2_reverse_tenant_oracle.py path/to/final_workbook.ods
  .venv/bin/python scripts/eval_2_headed.py --task reverse-tenant --score path/to/final_workbook.ods
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from eval_2_ods_oracle import Cell, cell_is_husk, read_workbook

CBA_EXCERPT_ODT_NAME = "CBA excerpt.odt"
THEATRE_CBA_ODS_NAME = "Theatre CBA.ods"
THEATRE_CBA_XLSX_NAME = "Theatre CBA.xlsx"

_MIN_SCORED_CELLS = 12
_MIN_INSTRUMENTS = 3
_MIN_PAY_CATEGORIES = 3

_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)

# CBA excerpt / gold-workbook aliases. Do not require the letters "CBA".
_CBA_RE = re.compile(
    r"\bcba\b|collective\s+bargaining|article\s+\d|base\s+wage|"
    r"weekly\s+guarantee|\bcontractor\b|\bcontract\b|\bwages?\b|\bpayroll\b",
    re.I,
)
# Gold workbook never says "theatre"; instruments + contractor/payroll still count.
_THEATRE_RE = re.compile(
    r"theatre|theater|musician|orchestra|broadway|contractor|"
    r"payroll|synthesizer|violin",
    re.I,
)
_ROSTER_OR_SCHEDULE_RE = re.compile(r"\broster\b|\bschedule\b", re.I)

_PAY_CATEGORY_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("audit", re.compile(r"\baudits?\b", re.I)),
    ("sound check", re.compile(r"sound\s*check", re.I)),
    ("rehearsal", re.compile(r"\brehearsals?\b", re.I)),
    ("performance", re.compile(r"\bperformances?\b", re.I)),
    ("premium", re.compile(r"\bpremiums?\b", re.I)),
    ("doubling", re.compile(r"\bdoubl(?:e|es|ing)\b", re.I)),
    ("vacation", re.compile(r"\bvacation\b", re.I)),
)

# Sample roster fixture instruments (not gold first names).
_INSTRUMENT_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("synthesizer", re.compile(r"synthesizer|keyboard", re.I)),
    ("violin", re.compile(r"\bviolin", re.I)),
    ("viola", re.compile(r"\bviola\b", re.I)),
    ("cello", re.compile(r"\bcello", re.I)),
    ("acoustic bass", re.compile(r"acoustic\s+bass|\bstring\s+bass\b", re.I)),
    ("guitar", re.compile(r"\bguitars?\b", re.I)),
    ("trumpet", re.compile(r"\btrumpet", re.I)),
    ("woodwind", re.compile(r"\bwoodwind", re.I)),
    ("french horn", re.compile(r"french\s+horn|\bhorn\b", re.I)),
)


@dataclass
class OracleResult:
    """Fail-closed workbook checks. Ready is never a field."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    sheet_names: list[str] = field(default_factory=list)
    scored_cells: int = 0
    husk_cells: int = 0
    pay_categories: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    brief_present: bool = False

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _cell_is_empty(cell: Cell) -> bool:
    if cell.formula.strip():
        return False
    value = cell.value
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _flatten_texts(sheets: dict[str, list[list[Cell]]]) -> tuple[str, int, int]:
    """Join sheet names + cell text; count scored cells and husks."""
    parts: list[str] = []
    scored = 0
    husks = 0
    for name, rows in sheets.items():
        if name:
            parts.append(name)
        for row in rows:
            for cell in row:
                if _cell_is_empty(cell):
                    continue
                scored += 1
                texts = cell.texts()
                parts.extend(texts)
                if cell_is_husk(cell) or any(_HUSK_RE.search(part) for part in texts):
                    husks += 1
    return "\n".join(parts), scored, husks


def _matched_labels(
    corpus: str,
    labeled: tuple[tuple[str, re.Pattern[str]], ...],
) -> list[str]:
    return [label for label, pattern in labeled if pattern.search(corpus)]


def score_sheets(sheets: dict[str, list[list[Cell]]]) -> OracleResult:
    """Apply soft fail-closed checks. Does not take a Ready/status argument."""
    failures: list[str] = []
    names = list(sheets)
    corpus, scored_cells, husk_cells = _flatten_texts(sheets)
    if scored_cells < _MIN_SCORED_CELLS:
        failures.append(
            f"workbook has {scored_cells} populated cells "
            f"(need >= {_MIN_SCORED_CELLS})"
        )
    if scored_cells and husk_cells * 2 >= scored_cells:
        failures.append(
            f"husk-dominated workbook ({husk_cells}/{scored_cells} scored cells)"
        )
    if not _CBA_RE.search(corpus):
        failures.append("missing CBA / contract / payroll / wage anchors")
    if not _THEATRE_RE.search(corpus):
        failures.append("missing theatre / musician / orchestra anchors")
    if not _ROSTER_OR_SCHEDULE_RE.search(corpus):
        failures.append("missing roster / schedule labels")
    pay_categories = _matched_labels(corpus, _PAY_CATEGORY_RES)
    if len(pay_categories) < _MIN_PAY_CATEGORIES:
        failures.append(
            f"payroll categories {pay_categories!r} "
            f"< {_MIN_PAY_CATEGORIES} of audit/sound check/rehearsal/"
            "performance/premium/doubling/vacation"
        )
    instruments = _matched_labels(corpus, _INSTRUMENT_RES)
    if len(instruments) < _MIN_INSTRUMENTS:
        failures.append(
            f"roster instruments {instruments!r} "
            f"< {_MIN_INSTRUMENTS} from the sample roster"
        )
    return OracleResult(
        passed=not failures,
        failures=failures,
        sheet_names=names,
        scored_cells=scored_cells,
        husk_cells=husk_cells,
        pay_categories=pay_categories,
        instruments=instruments,
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


def resolve_reverse_tenant_artifacts(
    artifact: Path,
    *,
    workbook: Path | None = None,
) -> tuple[Path | None, Path | None]:
    """Locate the Calc deliverable and optional Writer brief sibling."""
    artifact = artifact.expanduser()
    workbook_path = workbook.expanduser() if workbook is not None else None
    parent = artifact if artifact.is_dir() else artifact.parent
    if workbook_path is None:
        if artifact.is_file() and artifact.suffix.lower() in {
            ".ods",
            ".xlsx",
            ".xlsm",
            ".xltx",
            ".xltm",
        }:
            workbook_path = artifact
        else:
            workbook_path = _first_existing(
                parent / "final_workbook.ods",
                parent / "final_workbook.xlsx",
                parent / THEATRE_CBA_ODS_NAME,
                parent / THEATRE_CBA_XLSX_NAME,
                *sorted(parent.glob("*.ods")),
                *sorted(parent.glob("*.xlsx")),
            )
    brief = _first_existing(
        parent / CBA_EXCERPT_ODT_NAME,
        parent / "CBA excerpt.docx",
        *sorted(parent.glob("CBA excerpt.*")),
    )
    return workbook_path, brief


def score_workbook(path: Path | str, *, brief_present: bool = False) -> OracleResult:
    workbook = Path(path)
    if not workbook.is_file():
        return OracleResult(
            passed=False,
            failures=[f"workbook not found: {workbook}"],
            brief_present=brief_present,
        )
    try:
        sheets = read_workbook(workbook)
    except Exception as exc:
        return OracleResult(
            passed=False,
            failures=[f"cannot read workbook: {exc}"],
            brief_present=brief_present,
        )
    result = score_sheets(sheets)
    result.brief_present = brief_present
    return result


def format_result(result: OracleResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        status,
        f"  sheets: {', '.join(result.sheet_names) or '(none)'}",
        f"  scored_cells: {result.scored_cells}  husks: {result.husk_cells}",
        f"  pay_categories: {', '.join(result.pay_categories) or '(none)'}",
        f"  instruments: {', '.join(result.instruments) or '(none)'}",
        f"  brief_present: {result.brief_present}",
    ]
    for item in result.failures:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifact",
        type=Path,
        help="Saved Theatre CBA workbook (.ods/.xlsx) or trial directory",
    )
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args(argv)
    workbook, brief = resolve_reverse_tenant_artifacts(args.artifact)
    if workbook is None:
        result = OracleResult(
            passed=False,
            failures=[f"need a workbook under {args.artifact}"],
            brief_present=brief is not None,
        )
    else:
        result = score_workbook(workbook, brief_present=brief is not None)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

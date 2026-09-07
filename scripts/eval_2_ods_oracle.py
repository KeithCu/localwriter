#!/usr/bin/env python3
# WriterAgent - eval-2 / AFC harness ODS oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed structural scorer for an eval-2 AFC trial workbook.

Pass/fail is document-local. Chat Ready / STREAM_DONE is never consulted —
those green-washed empty Sample sheets in the six CLEAN Ready runs.

R comes from the in-workbook ``Sample Size Calculation`` tab (same source as
the eval-2 / gold rubric: the integer the SSC sheet reports). This module does
not recompute Cochran/FPC and does not letter-shift gold ``rubric_pretty.txt``.
Column K is the flag column because ``prompt.writeragent.txt`` says so.

Usage:
  .venv/bin/python scripts/eval_2_ods_oracle.py path/to/final_workbook.ods
  .venv/bin/python scripts/eval_2_headed.py --score path/to/final_workbook.ods
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

SAMPLE_SHEET = "Sample"
SSC_SHEET = "Sample Size Calculation"
# eval-2 writer prompt step 3: "indicate sampled rows in column K".
# Gold flags live in J on a different deliverable — do not letter-shift.
FLAG_COLUMN_INDEX = 10  # A=1 … K=11 → 0-based 10
# Empty LO padding uses huge number-rows-repeated; never materialize that.
_MAX_REPEAT = 10_000
_ANON_DB_SHEET = re.compile(r"^__Anonymous_Sheet_DB__", re.I)

_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_TABLE = f"{{{_TABLE_NS}}}table"
_TABLE_ROW = f"{{{_TABLE_NS}}}table-row"
_TABLE_CELL = f"{{{_TABLE_NS}}}table-cell"
_COVERED_CELL = f"{{{_TABLE_NS}}}covered-table-cell"
_TABLE_NAME = f"{{{_TABLE_NS}}}name"
_NCOLS_REP = f"{{{_TABLE_NS}}}number-columns-repeated"
_NROWS_REP = f"{{{_TABLE_NS}}}number-rows-repeated"
_FORMULA = f"{{{_TABLE_NS}}}formula"
_OFFICE_VALUE = f"{{{_OFFICE_NS}}}value"
_OFFICE_STRING = f"{{{_OFFICE_NS}}}string-value"
_OFFICE_BOOL = f"{{{_OFFICE_NS}}}boolean-value"
_TEXT_P = f"{{{_TEXT_NS}}}p"

# Dominant husks / residue observed on Ready-but-empty AFC trials.
_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|Error:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
# Labels the gold SSC uses ("Sample size") plus explicit R / required size.
_R_LABEL_RE = re.compile(
    r"(?i)^\s*(?:required\s+|final\s+(?:required\s+)?)?sample\s+size\s*$|^\s*r\s*$"
)
_R_INLINE_RE = re.compile(r"(?i)\bR\s*=\s*(\d+)\b")
_INT_RE = re.compile(r"^[+-]?\d+(?:\.0+)?$")


@dataclass(frozen=True)
class Cell:
    """One stored cell: displayed/office value plus any formula text."""

    value: object = None
    formula: str = ""

    def texts(self) -> tuple[str, ...]:
        parts = [self.formula]
        if self.value is not None:
            parts.append(str(self.value))
        return tuple(p for p in parts if p)


@dataclass
class OracleResult:
    """Fail-closed trial score. ``passed`` is true only when ``failures`` is empty."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    sheet_names: list[str] = field(default_factory=list)
    sample_data_rows: int = 0
    s_flags: int = 0
    r_required: int | None = None
    husk_cells: int = 0
    scored_cells: int = 0

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _norm_sheet(name: str) -> str:
    return " ".join((name or "").split()).casefold()


def _is_anon_db_sheet(name: str) -> bool:
    return bool(_ANON_DB_SHEET.match((name or "").strip()))


def _find_sheet(sheets: dict[str, list[list[Cell]]], wanted: str) -> list[list[Cell]] | None:
    target = _norm_sheet(wanted)
    for name, rows in sheets.items():
        if _is_anon_db_sheet(name):
            continue
        if _norm_sheet(name) == target:
            return rows
    return None


def _cell_is_empty(cell: Cell) -> bool:
    if cell.formula.strip():
        return False
    value = cell.value
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _row_is_empty(row: list[Cell]) -> bool:
    return all(_cell_is_empty(cell) for cell in row)


def is_husk_text(text: str) -> bool:
    return bool(text) and bool(_HUSK_RE.search(text))


def cell_is_husk(cell: Cell) -> bool:
    return any(is_husk_text(part) for part in cell.texts())


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        raw = value.strip().replace(",", "")
        if _INT_RE.match(raw):
            return int(float(raw))
    return None


def is_flag_one(cell: Cell) -> bool:
    """True for numeric/string 1. Husks that happen to contain '1' do not count."""
    if cell_is_husk(cell):
        return False
    if _as_int(cell.value) == 1:
        return True
    if isinstance(cell.value, str) and cell.value.strip() == "1":
        return True
    return False


def parse_required_sample_size(ssc_rows: list[list[Cell]]) -> int | None:
    """R from the SSC tab. Fail-closed caller requires R >= 1.

    Picks labeled values only (``Sample size``, ``R``, ``R = N``) so the
    population N sitting next to ``Dataset`` is not treated as R.
    """
    found: list[int] = []
    for row in ssc_rows:
        for idx, cell in enumerate(row):
            for text in cell.texts():
                inline = _R_INLINE_RE.search(text)
                if inline:
                    found.append(int(inline.group(1)))
                if _R_LABEL_RE.match(text.strip()):
                    for other in row[idx + 1 :]:
                        parsed = _as_int(other.value)
                        if parsed is not None:
                            found.append(parsed)
                            break
    if not found:
        return None
    return found[-1]


def _text_p_join(cell_el: ET.Element) -> str:
    texts = ["".join(paragraph.itertext()) for paragraph in cell_el.findall(_TEXT_P)]
    if texts:
        return "\n".join(texts)
    return "".join(cell_el.itertext())


def _ods_cell_from_el(el: ET.Element) -> Cell:
    formula = el.get(_FORMULA) or ""
    raw_value: object
    if el.get(_OFFICE_VALUE) is not None:
        try:
            raw_value = float(el.get(_OFFICE_VALUE) or "")
        except ValueError:
            raw_value = el.get(_OFFICE_VALUE)
    elif el.get(_OFFICE_STRING) is not None:
        raw_value = el.get(_OFFICE_STRING)
    elif el.get(_OFFICE_BOOL) is not None:
        raw_value = (el.get(_OFFICE_BOOL) or "").casefold() in {"true", "1"}
    else:
        raw_value = _text_p_join(el)
        if raw_value == "":
            raw_value = None
    return Cell(value=raw_value, formula=formula)


def _repeat(count_raw: str | None, *, empty: bool) -> int:
    try:
        count = int(count_raw or "1")
    except ValueError:
        count = 1
    if count < 1:
        return 1
    if empty:
        # Trailing LO padding (often 1e6 empty rows) is not Sample data.
        return 1 if count == 1 else 0
    return min(count, _MAX_REPEAT)


def _read_ods_rows(table: ET.Element) -> list[list[Cell]]:
    rows: list[list[Cell]] = []
    for row_el in table.findall(_TABLE_ROW):
        cells: list[Cell] = []
        for child in row_el:
            if child.tag not in (_TABLE_CELL, _COVERED_CELL):
                continue
            cell = Cell() if child.tag == _COVERED_CELL else _ods_cell_from_el(child)
            col_repeat = _repeat(child.get(_NCOLS_REP), empty=_cell_is_empty(cell))
            cells.extend([cell] * col_repeat)
        row_repeat = _repeat(row_el.get(_NROWS_REP), empty=_row_is_empty(cells))
        if row_repeat <= 0:
            continue
        rows.extend([list(cells) for _unused in range(row_repeat)])
    return rows


def read_ods(path: Path) -> dict[str, list[list[Cell]]]:
    """Read sheet → rows from an ODS via stdlib zip/XML. No soffice."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    sheets: dict[str, list[list[Cell]]] = {}
    for table in root.findall(f".//{_TABLE}"):
        name = table.get(_TABLE_NAME) or ""
        if _is_anon_db_sheet(name):
            continue
        sheets[name] = _read_ods_rows(table)
    return sheets


def read_xlsx(path: Path) -> dict[str, list[list[Cell]]]:
    from openpyxl import load_workbook

    # data_only=False: we need formula text to ban PYTHONFUNCTION husks
    # without a LibreOffice calc pass.
    wb = load_workbook(path, data_only=False, read_only=True)
    try:
        sheets: dict[str, list[list[Cell]]] = {}
        for name in wb.sheetnames:
            if _is_anon_db_sheet(name):
                continue
            rows: list[list[Cell]] = []
            for row in wb[name].iter_rows(values_only=False):
                cells: list[Cell] = []
                for cell in row:
                    formula = ""
                    value: object = cell.value
                    if isinstance(value, str) and value.startswith("="):
                        formula = value
                    cells.append(Cell(value=value, formula=formula))
                rows.append(cells)
            sheets[name] = rows
        return sheets
    finally:
        wb.close()


def read_workbook(path: Path) -> dict[str, list[list[Cell]]]:
    suffix = path.suffix.lower()
    if suffix == ".ods":
        return read_ods(path)
    if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return read_xlsx(path)
    raise ValueError(f"unsupported workbook type: {path.suffix}")


def _sample_data_rows(sample: list[list[Cell]]) -> list[list[Cell]]:
    if not sample:
        return []
    return [row for row in sample[1:] if not _row_is_empty(row)]


def _flag_cell(row: list[Cell]) -> Cell:
    if len(row) > FLAG_COLUMN_INDEX:
        return row[FLAG_COLUMN_INDEX]
    return Cell()


def _count_scored_husks(data_rows: list[list[Cell]]) -> tuple[int, int]:
    scored = 0
    husks = 0
    for row in data_rows:
        for cell in row:
            if _cell_is_empty(cell):
                continue
            scored += 1
            if cell_is_husk(cell):
                husks += 1
    return husks, scored


def score_sheets(sheets: dict[str, list[list[Cell]]]) -> OracleResult:
    """Apply the four fail-closed checks. Does not take a Ready/status argument."""
    failures: list[str] = []
    names = [name for name in sheets if not _is_anon_db_sheet(name)]
    sample = _find_sheet(sheets, SAMPLE_SHEET)
    ssc = _find_sheet(sheets, SSC_SHEET)
    if sample is None:
        failures.append(f"missing sheet {SAMPLE_SHEET!r}")
    if ssc is None:
        failures.append(f"missing sheet {SSC_SHEET!r}")

    data_rows = _sample_data_rows(sample) if sample is not None else []
    if sample is not None and not data_rows:
        # Empty Sample + Ready was the greenwash; fail closed here.
        failures.append("Sample has no data rows")

    r_required = parse_required_sample_size(ssc) if ssc is not None else None
    if ssc is not None and (r_required is None or r_required < 1):
        failures.append("R from Sample Size Calculation is missing or < 1")

    s_flags = 0
    if sample is not None:
        s_flags = sum(1 for row in data_rows if is_flag_one(_flag_cell(row)))
    if (
        sample is not None
        and r_required is not None
        and r_required >= 1
        and s_flags < r_required
    ):
        failures.append(f"S={s_flags} flag=1 in column K is < R={r_required}")

    husk_cells, scored_cells = _count_scored_husks(data_rows)
    if scored_cells and husk_cells * 2 >= scored_cells:
        failures.append(
            f"husk-dominated Sample ({husk_cells}/{scored_cells} scored cells)"
        )

    return OracleResult(
        passed=not failures,
        failures=failures,
        sheet_names=names,
        sample_data_rows=len(data_rows),
        s_flags=s_flags,
        r_required=r_required,
        husk_cells=husk_cells,
        scored_cells=scored_cells,
    )


def score_workbook(path: Path | str) -> OracleResult:
    workbook = Path(path)
    if not workbook.is_file():
        return OracleResult(passed=False, failures=[f"workbook not found: {workbook}"])
    try:
        sheets = read_workbook(workbook)
    except Exception as exc:
        # Fail closed: a workbook we cannot parse is not a pass, including
        # openpyxl/ODS XML surprises. Ready is still not consulted.
        return OracleResult(passed=False, failures=[f"cannot read workbook: {exc}"])
    return score_sheets(sheets)


def format_result(result: OracleResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        status,
        f"  sheets: {', '.join(result.sheet_names) or '(none)'}",
        f"  sample_data_rows: {result.sample_data_rows}",
        f"  S={result.s_flags} R={result.r_required}",
        f"  husks: {result.husk_cells}/{result.scored_cells} scored cells",
    ]
    for item in result.failures:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="Saved trial .ods (or .xlsx)")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args(argv)
    result = score_workbook(args.workbook)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

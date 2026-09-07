# WriterAgent tests for eval-2 AFC writer prompt column axes
# Copyright (c) 2026 KeithCu (modifications and relicensing)
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Writer prompt axes come from the Population fixture, not gold H/I."""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_AFC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "eval"
    / "eval-2"
    / "afc-sample-83d10b06"
)
_WRITER_PROMPT = _AFC / "prompt.writeragent.txt"
_GDPVAL_PROMPT = _AFC / "prompt.gdpval.txt"
_POPULATION = _AFC / "fixtures" / "Population v2.xlsx"
_SSML = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Locked eval-2 one-liner (fixture G=Q3, H=Q2; in-workbook J/K).
_AXES = "Q2 is in H, Q3 is in G; variance = (G−H)/H into J; flags in K"


def _xlsx_header_row(path: Path) -> list[str]:
    """First-row labels from an xlsx shared-string sheet. No LibreOffice."""
    with zipfile.ZipFile(path) as zf:
        shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        shared: list[str] = []
        for si in shared_root.findall(f"{{{_SSML}}}si"):
            shared.append("".join(t.text or "" for t in si.findall(f".//{{{_SSML}}}t")))
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        row = sheet.find(f"{{{_SSML}}}sheetData/{{{_SSML}}}row")
        assert row is not None, f"no rows in {path}"
        headers: list[str] = []
        for cell in row.findall(f"{{{_SSML}}}c"):
            value = cell.findtext(f"{{{_SSML}}}v") or ""
            if cell.get("t") == "s" and value.isdigit():
                headers.append(shared[int(value)])
            else:
                headers.append(value)
        return headers


def test_writer_prompt_uses_fixture_qh_axes() -> None:
    text = _WRITER_PROMPT.read_text(encoding="utf-8")
    assert _AXES in text
    assert "columns H and I" not in text
    # Gold copy stays the GDPval wording; do not “fix” it by letter-shift.
    gold = _GDPVAL_PROMPT.read_text(encoding="utf-8")
    assert "columns H and I" in gold


def test_population_fixture_headers_are_g_q3_h_q2() -> None:
    headers = _xlsx_header_row(_POPULATION)
    assert headers[:8] == [
        "No",
        "Division",
        "Sub-Division",
        "Country",
        "Legal Entity",
        "KRIs",
        "Q3 2024 KRI",
        "Q2 2024 KRI",
    ]
    # A–H only: I is not a Population field (gold H/I wording is wrong here).
    assert len([h for h in headers if h]) == 8

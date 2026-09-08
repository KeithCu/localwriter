# WriterAgent tests for scripts/eval_2_tenant_oracle.py
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from odf.opendocument import OpenDocumentText
from odf.text import P

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from eval_2_headed import main as headed_main  # noqa: E402
from eval_2_tenant_oracle import (  # noqa: E402
    main as oracle_main,
    score_memo,
    score_text,
)

_PASSING = """
Business Memo
Subject: Tenant Retention Strategy for Harborview Flats, Stamford, Connecticut

Objective: increase resident retention by 10% in the next 6 months.

1. Analysis of Departure Reasons
Exit Survey Feedback (20 comments):
- rent increase 9/20 (45%)
- lack of community / feeling disconnected 5/20 (25%)

2. Tiered Renewal Offer Structure
- early-bird offer at 90 days
- standard offer at 60 days
- month-to-month premium

3. Communication Plan
Touchpoints at 90-day, 60-day, and 30-day marks before lease end.

4. Community Engagement Initiatives
We will host two resident events next quarter on the front lawn and in the lounge.
"""


def _write_docx(path: Path, text: str) -> Path:
    doc = Document()
    for line in text.strip().splitlines():
        doc.add_paragraph(line)
    doc.save(str(path))
    return path


def _write_odt(path: Path, text: str) -> Path:
    doc = OpenDocumentText()
    for line in text.strip().splitlines():
        doc.text.addElement(P(text=line))
    doc.save(str(path))
    return path


def _padded() -> str:
    return _PASSING + (" Retention follow-through. " * 80)


def test_passing_memo_docx_and_odt(tmp_path: Path) -> None:
    text = _padded()
    docx = _write_docx(tmp_path / "ok.docx", text)
    odt = _write_odt(tmp_path / "ok.odt", text)
    for path in (docx, odt):
        result = score_memo(path)
        assert result.passed, (path.name, result.failures)
        assert 180 <= result.word_count <= 1400


def test_empty_memo_fails(tmp_path: Path) -> None:
    path = _write_odt(tmp_path / "empty.odt", "")
    result = score_memo(path)
    assert not result.passed
    assert any("empty" in item or "word_count" in item for item in result.failures)


def test_wrong_survey_counts_fail() -> None:
    text = _padded().replace("9/20 (45%)", "4/20 (20%)").replace("5/20 (25%)", "2/20 (10%)")
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("9/20" in item for item in result.failures)
    assert any("5/20" in item for item in result.failures)


def test_missing_stamford_fails() -> None:
    text = _padded().replace("Stamford, Connecticut", "elsewhere")
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("Stamford" in item for item in result.failures)


def test_husk_body_fails() -> None:
    text = _padded() + "\nError: tool failed\n"
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("husk" in item for item in result.failures)


def test_oracle_does_not_require_gold_typo() -> None:
    text = _padded()
    assert "Rentention" not in text
    result = score_text(text, para_count=12)
    assert result.passed, result.failures


def test_headed_score_routes_odt_to_tenant_oracle(tmp_path: Path) -> None:
    path = _write_odt(tmp_path / "final_memo.odt", _padded())
    assert headed_main(["--score", str(path)]) == 0
    empty = _write_odt(tmp_path / "empty.odt", "")
    assert headed_main(["--task", "tenant-retention", "--score", str(empty)]) == 1


def test_oracle_cli_json(tmp_path: Path, capsys) -> None:
    path = _write_odt(tmp_path / "final_memo.odt", _padded())
    assert oracle_main(["--json", str(path)]) == 0
    out = capsys.readouterr().out
    assert '"passed": true' in out

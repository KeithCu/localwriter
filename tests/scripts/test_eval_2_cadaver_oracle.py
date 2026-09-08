# WriterAgent tests for scripts/eval_2_cadaver_oracle.py
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from odf.opendocument import OpenDocumentText
from odf.text import H, P

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from eval_2_cadaver_oracle import (  # noqa: E402
    main as oracle_main,
    score_proposal,
    score_text,
)
from eval_2_headed import main as headed_main  # noqa: E402

_PASSING = """
Introduction
Collaborative Cadaver Program Proposal for General Surgery, Thoracic
Surgery, Otolaryngology, and Orthopedic Surgery.

Cost savings come first. Baseline is 4 cadavers/year for General Surgery.
Formula: (4 × per-cadaver) + Annual Cadaver Lab Fee. The analysis excludes
Supplies and Education. Graph and savings table for 1-4 departments below.

Ethical use: we maximize cadaver use to honor donors and respect final wishes.
Anatomy: abdomen for General Surgery; thorax for Thoracic Surgery; head and
neck for Otolaryngology; limbs for Orthopedic Surgery.

Freeze/thaw cycles are 10-12. Once thawed there is a 3-hour window.
Simple 30-45 minutes (up to 4 per window; totals 40-48). Standard 1-1.5
hours (2-3 per window; totals 20-36). Complex 2-3 hours (1 per window;
totals 10-12). This proposal does not account for mixing complexity.
"""


def _write_docx(path: Path, text: str) -> Path:
    doc = Document()
    for line in text.strip().splitlines():
        doc.add_paragraph(line)
    doc.save(str(path))
    return path


def _write_odt(path: Path, text: str, *, title_as_heading: bool = False) -> Path:
    doc = OpenDocumentText()
    lines = text.strip().splitlines()
    if title_as_heading and lines:
        heading = H(outlinelevel=1)
        heading.addText(lines[0])
        doc.text.addElement(heading)
        lines = lines[1:]
    for line in lines:
        doc.text.addElement(P(text=line))
    doc.save(str(path))
    return path


def _padded() -> str:
    return _PASSING + (" Shared cadaver training capacity. " * 80)


def test_passing_proposal_docx_and_odt(tmp_path: Path) -> None:
    text = _padded()
    docx = _write_docx(tmp_path / "ok.docx", text)
    odt = _write_odt(tmp_path / "ok.odt", text)
    for path in (docx, odt):
        result = score_proposal(path)
        assert result.passed, (path.name, result.failures)
        assert 250 <= result.word_count <= 2500


def test_odt_heading_title_is_scored(tmp_path: Path) -> None:
    """Headed Writer puts the title in text:h; body stays text:p."""
    body = _padded().replace("Collaborative Cadaver Program Proposal", "Working draft", 1)
    path = _write_odt(tmp_path / "headed.odt", "Collaborative Cadaver Program Proposal\n" + body, title_as_heading=True)
    result = score_proposal(path)
    assert result.passed, result.failures


def test_empty_proposal_fails(tmp_path: Path) -> None:
    path = _write_odt(tmp_path / "empty.odt", "")
    result = score_proposal(path)
    assert not result.passed
    assert any("empty" in item or "word_count" in item for item in result.failures)


def test_missing_exclude_wording_fails() -> None:
    text = _padded().replace("excludes\nSupplies and Education", "mentions Supplies and Education")
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("exclude" in item for item in result.failures)


def test_missing_formula_fails() -> None:
    text = _padded().replace("(4 × per-cadaver) + Annual Cadaver Lab Fee", "some shared costs")
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("formula" in item for item in result.failures)


def test_cost_savings_must_come_before_ethics() -> None:
    text = _padded()
    ethics = "Ethical use: we maximize cadaver use to honor donors and respect final wishes."
    cost = "Cost savings come first."
    swapped = text.replace(ethics, "PLACEHOLDER_ETHICS").replace(cost, ethics).replace("PLACEHOLDER_ETHICS", cost)
    result = score_text(swapped, para_count=12)
    assert not result.passed
    assert any("not first" in item for item in result.failures)


def test_missing_standard_36_fails() -> None:
    text = _padded().replace("20-36", "20-24")
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("20-36" in item for item in result.failures)


def test_does_not_require_exact_dollars() -> None:
    text = _padded()
    assert "$" not in text
    assert "2,000" not in text
    result = score_text(text, para_count=12)
    assert result.passed, result.failures


def test_does_not_require_hope_or_silverview() -> None:
    text = _padded()
    assert "Hope Hospital" not in text
    assert "Silverview" not in text
    result = score_text(text, para_count=12)
    assert result.passed, result.failures


def test_husk_body_fails() -> None:
    text = _padded() + "\nError: tool failed\n"
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("husk" in item for item in result.failures)


def test_headed_score_routes_to_cadaver_oracle(tmp_path: Path) -> None:
    path = _write_odt(tmp_path / "final_proposal.odt", _padded())
    assert headed_main(["--task", "cadaver-proposal", "--score", str(path)]) == 0
    empty = _write_odt(tmp_path / "empty.odt", "")
    assert headed_main(["--task", "cadaver-proposal", "--score", str(empty)]) == 1


def test_oracle_cli_json(tmp_path: Path, capsys) -> None:
    path = _write_odt(tmp_path / "final_proposal.odt", _padded())
    assert oracle_main(["--json", str(path)]) == 0
    out = capsys.readouterr().out
    assert '"passed": true' in out

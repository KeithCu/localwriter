# WriterAgent tests for scripts/eval_2_cadaver_oracle.py
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from odf.opendocument import OpenDocumentText
from odf.text import P

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
Collaborative Cadaver Program Proposal
Introduction
Hope Hospital General Surgery proposes a Collaborative Cadaver Program
with Thoracic Surgery, Otolaryngology, and Orthopedic Surgery.

Cost savings: baseline uses 4 cadavers at $3,000 each plus a $1,000
annual lab fee. Supplies and education are excluded. The graph of
annual savings versus 1-4 participating departments is below.

Ethical use: we maximize cadaver use to respect donor final wishes.
Anatomy assignments: abdomen for General Surgery; thorax for Thoracic
Surgery; head and neck for Otolaryngology; limbs for Orthopedic Surgery.

Freeze/thaw cycles are 10-12. Once thawed there is a 3-hour window.
Simple procedures take 30-45 minutes (40-48 per cadaver). Standard
takes 1-1.5 hours. Complex takes 2-3 hours. This proposal does not
account for mixing complexity.
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
    return _PASSING + (" Shared cadaver training capacity. " * 80)


def test_passing_proposal_docx_and_odt(tmp_path: Path) -> None:
    text = _padded()
    docx = _write_docx(tmp_path / "ok.docx", text)
    odt = _write_odt(tmp_path / "ok.odt", text)
    for path in (docx, odt):
        result = score_proposal(path)
        assert result.passed, (path.name, result.failures)
        assert 250 <= result.word_count <= 3000


def test_empty_proposal_fails(tmp_path: Path) -> None:
    path = _write_odt(tmp_path / "empty.odt", "")
    result = score_proposal(path)
    assert not result.passed
    assert any("empty" in item or "word_count" in item for item in result.failures)


def test_wrong_budget_cells_fail() -> None:
    text = (
        _padded()
        .replace("$3,000", "$9,999")
        .replace("$1,000", "$50")
    )
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("2,000" in item or "3,000" in item for item in result.failures)
    assert any("1,000" in item for item in result.failures)


def test_missing_hope_hospital_fails() -> None:
    text = _padded().replace("Hope Hospital", "Silverview Hospital")
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("Hope Hospital" in item for item in result.failures)


def test_husk_body_fails() -> None:
    text = _padded() + "\nError: tool failed\n"
    result = score_text(text, para_count=12)
    assert not result.passed
    assert any("husk" in item for item in result.failures)


def test_oracle_does_not_require_silverview() -> None:
    text = _padded()
    assert "Silverview" not in text
    result = score_text(text, para_count=12)
    assert result.passed, result.failures


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

#!/usr/bin/env python3
# WriterAgent - eval-2 / GMP Change Control oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Soft structural scorer for the eval-2 GMP Change Control pair.

Pass/fail is document-local. Chat Ready / STREAM_DONE is never consulted.
Identity facts are gold-hard (RMS-3333, CompCello, QY-GEL / Antifoam,
endotoxin mismatch). Hyphen-like characters fold to ASCII before those
id checks (RMS‑3333 still counts). Form fill is a count/length band, not
gold-string matching. Expert gold uses XX-CELL / Lot A23-044 — those are
**not** required (and contradict the prompt / COA).

Usage:
  .venv/bin/python scripts/eval_2_gmp_oracle.py path/to/final_memo.odt
  .venv/bin/python scripts/eval_2_gmp_oracle.py path/to/runs/<stamp>/
  .venv/bin/python scripts/eval_2_headed.py --task gmp-change-control --score path/to/final_memo.odt
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from eval_2_headed import GMP_FILLABLE_FIELDS, GMP_FORM_ODG_NAME

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_DRAW_NS = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
_TEXT_P = f"{{{_TEXT_NS}}}p"
_TEXT_H = f"{{{_TEXT_NS}}}h"
_DRAW_FRAME = f"{{{_DRAW_NS}}}frame"
_WORD_MIN = 200
# Headed risk memo + QA email + Teams note can run long; Ready-empty is far shorter.
_WORD_MAX = 2500
_MIN_FILLED_FIELDS = 5
_MIN_FILLED_CHARS = 80
_FILLABLE_NAMES = {name for name, _label in GMP_FILLABLE_FIELDS}

_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
_RMS_RE = re.compile(r"rms[\s\-]*3333", re.I)
_VENDOR_RE = re.compile(r"compcello", re.I)
_MATERIAL_RE = re.compile(r"qy[\s\-]*gel|antifoam|antiform", re.I)
_REPORT_RESULT_RE = re.compile(r"report\s+result", re.I)
_EU_LIMIT_RE = re.compile(
    r"(?:<\s*1|<1|less\s+than\s+1|below\s+1).{0,24}eu"
    r"|eu.{0,24}(?:<\s*1|<1|less\s+than\s+1|below\s+1)"
    r"|endotoxin.{0,40}(?:<\s*1|<1|less\s+than\s+1)",
    re.I,
)
_MISMATCH_RE = re.compile(
    r"mismatch|discrepanc|non[\s\-]*conform|spec(?:ification)?\s+gap",
    re.I,
)
_QUARANTINE_RE = re.compile(r"quarantine|qa\s+hold|\bon\s+hold\b|material\s+hold", re.I)
_RMS_UPDATE_RE = re.compile(
    r"update.{0,24}rms|rms.{0,24}update|change\s+control|form[\s\-]*920",
    re.I,
)
# Prompt names the Draw deliverable a Change Control Request; headed
# HAPPY memos cite that / CCR / "completed … change control" instead of
# "tracking form" / Form-920. Keep a form-side cite — "change control"
# alone is the RMS-update theme, not this check.
_FORM_CITE_RE = re.compile(
    r"change\s+control(?:\s+tracking)?\s+form"
    r"|filled\s+form"
    r"|draft(?:ed)?(?:\s+a)?\s+change\s+control"
    r"|change\s+control\s+request"
    r"|completed.{0,40}change\s+control"
    r"|form[\s\-]*920"
    r"|\bCCR\b",
    re.I,
)
_QA_EMAIL_RE = re.compile(
    r"(?:qa|quality\s+assurance).{0,40}(?:escalat|email|leadership)"
    r"|(?:escalat|email).{0,40}(?:qa|quality\s+assurance)"
    r"|subject\s*:",
    re.I,
)
_DEVIATION_RE = re.compile(r"deviation|requalif", re.I)
_TEAMS_RE = re.compile(
    r"internal\s+summary|teams|status\s+(?:update|note)|stakeholder",
    re.I,
)
_DEPARTED_RE = re.compile(
    r"left\s+the\s+company|former\s+employee|ex[\s\-]?employee|departed|no\s+longer\s+works",
    re.I,
)
_VENDOR_MEMO_RE = re.compile(
    r"(?:change\s+notification|vendor\s+memo|two\s+months|2\s+months|report\s+only)",
    re.I,
)
_CENTRAL_RE = re.compile(
    r"central(?:ized)?|shared\s+mailbox|qms|vendor\s+communication",
    re.I,
)
_SOP_RE = re.compile(r"\bsops?\b|standard\s+operating", re.I)
_ENDOTOXIN_RE = re.compile(r"endotoxin", re.I)

# Word/LO often emit U+2011 (non-breaking hyphen) in ids such as RMS‑3333.
# Fold those to ASCII '-' before identity searches so the gold id still
# required, without a false-red on encoding. NBSP-adjacent spaces fold too.
_HYPHEN_LIKE_TO_ASCII = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2212": "-",  # minus sign
    "\u00a0": " ",  # NBSP
    "\u202f": " ",  # narrow NBSP
})


def normalize_hyphen_like(text: str) -> str:
    """Fold hyphen-like / NBSP so identity ids match ASCII needles (RMS-3333)."""
    return (text or "").translate(_HYPHEN_LIKE_TO_ASCII)


@dataclass
class OracleResult:
    """Fail-closed pair checks. Ready is never a field."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    word_count: int = 0
    para_count: int = 0
    filled_fields: int = 0
    filled_chars: int = 0

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


def read_odg_frames(path: Path) -> list[tuple[str, str]]:
    """``(draw:name, text)`` for every frame on the Draw stand-in."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    frames: list[tuple[str, str]] = []
    for frame in root.iter(_DRAW_FRAME):
        name = frame.get(f"{{{_DRAW_NS}}}name") or ""
        text = "".join(frame.itertext())
        frames.append((name, text))
    return frames


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _form_fill_stats(frames: list[tuple[str, str]]) -> tuple[int, int, str]:
    filled = 0
    chars = 0
    parts: list[str] = []
    for name, text in frames:
        stripped = text.strip()
        parts.append(stripped)
        if name in _FILLABLE_NAMES and stripped:
            filled += 1
            chars += len(stripped)
    return filled, chars, "\n".join(parts)


def resolve_gmp_artifacts(
    artifact: Path,
    *,
    form: Path | None = None,
    memo: Path | None = None,
) -> tuple[Path | None, Path | None]:
    """Pick the Writer memo and Draw form from a file or trial directory."""
    artifact = artifact.expanduser()
    memo_path = memo.expanduser() if memo is not None else None
    form_path = form.expanduser() if form is not None else None
    if artifact.is_dir():
        if memo_path is None:
            memo_path = _first_existing(
                artifact / "final_memo.odt",
                artifact / "MR Risk Assessment Summary.odt",
                *sorted(artifact.glob("*.odt")),
                *sorted(artifact.glob("*.docx")),
            )
        if form_path is None:
            form_path = _first_existing(
                artifact / "final_form.odg",
                artifact / GMP_FORM_ODG_NAME,
                *sorted(artifact.glob("*.odg")),
            )
        return memo_path, form_path
    suffix = artifact.suffix.lower()
    if suffix == ".odg":
        form_path = form_path or artifact
        if memo_path is None:
            memo_path = _first_existing(
                artifact.with_name("final_memo.odt"),
                artifact.with_name("MR Risk Assessment Summary.odt"),
                *sorted(artifact.parent.glob("*.odt")),
                *sorted(artifact.parent.glob("*.docx")),
            )
        return memo_path, form_path
    memo_path = memo_path or artifact
    if form_path is None:
        form_path = _first_existing(
            artifact.with_name("final_form.odg"),
            artifact.with_name(GMP_FORM_ODG_NAME),
            *sorted(artifact.parent.glob("*.odg")),
        )
    return memo_path, form_path


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


def score_pair(
    memo_text: str,
    form_text: str,
    *,
    para_count: int,
    filled_fields: int,
    filled_chars: int,
) -> OracleResult:
    """Apply soft fail-closed checks to extracted memo + form text."""
    failures: list[str] = []
    words = _word_count(memo_text)
    if not memo_text.strip():
        failures.append("memo body is empty")
    if words < _WORD_MIN:
        failures.append(f"word_count {words} < {_WORD_MIN} (Ready-empty / too short)")
    if words > _WORD_MAX:
        failures.append(f"word_count {words} > {_WORD_MAX}")
    if _HUSK_RE.search(memo_text) or _HUSK_RE.search(form_text):
        failures.append("body contains Error:/husk residue")
    if filled_fields < _MIN_FILLED_FIELDS:
        failures.append(
            f"form fields filled {filled_fields} < {_MIN_FILLED_FIELDS} "
            "(stand-in not substantially filled)"
        )
    if filled_chars < _MIN_FILLED_CHARS:
        failures.append(
            f"form filled chars {filled_chars} < {_MIN_FILLED_CHARS} "
            "(too thin to count as filled)"
        )
    combined = normalize_hyphen_like(f"{memo_text}\n{form_text}")
    memo_text = normalize_hyphen_like(memo_text)
    if not _RMS_RE.search(combined):
        failures.append("missing RMS-3333")
    if not _VENDOR_RE.search(combined):
        failures.append("missing CompCello")
    if not _MATERIAL_RE.search(combined):
        failures.append("missing QY-GEL / Antifoam")
    if not _ENDOTOXIN_RE.search(combined):
        failures.append("missing Endotoxin")
    if not _REPORT_RESULT_RE.search(combined):
        failures.append("missing COA Report Result")
    if not _EU_LIMIT_RE.search(combined):
        failures.append("missing RMS endotoxin < 1 EU")
    if not _MISMATCH_RE.search(combined):
        failures.append("missing specification mismatch / discrepancy")
    if not _QUARANTINE_RE.search(combined):
        failures.append("missing quarantine / hold")
    if not _RMS_UPDATE_RE.search(combined):
        failures.append("missing RMS update / change control")
    if not _FORM_CITE_RE.search(memo_text):
        failures.append("memo does not cite the filled change-control form")
    if not _QA_EMAIL_RE.search(memo_text):
        failures.append("missing QA escalation email section")
    if not _DEVIATION_RE.search(memo_text):
        failures.append("QA email missing deviation / requalification ask")
    if not _TEAMS_RE.search(memo_text):
        failures.append("missing internal / Teams summary note")
    if not _VENDOR_MEMO_RE.search(memo_text):
        failures.append("missing vendor change-notification / report-only theme")
    if not _DEPARTED_RE.search(memo_text):
        failures.append("missing departed-employee / leftover-inbox theme")
    if not _CENTRAL_RE.search(memo_text):
        failures.append("missing centralized vendor-communication mitigation")
    if not _SOP_RE.search(memo_text):
        failures.append("missing SOP update mitigation")
    return OracleResult(
        passed=not failures,
        failures=failures,
        word_count=words,
        para_count=para_count,
        filled_fields=filled_fields,
        filled_chars=filled_chars,
    )


def score_artifacts(memo: Path | str, form: Path | str) -> OracleResult:
    memo_path = Path(memo)
    form_path = Path(form)
    if not memo_path.is_file():
        return OracleResult(passed=False, failures=[f"memo not found: {memo_path}"])
    if not form_path.is_file():
        return OracleResult(passed=False, failures=[f"form not found: {form_path}"])
    try:
        paras = read_memo_paragraphs(memo_path)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read memo: {exc}"])
    try:
        frames = read_odg_frames(form_path)
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read form: {exc}"])
    memo_text = "\n".join(paras)
    filled_fields, filled_chars, form_text = _form_fill_stats(frames)
    nonempty = sum(1 for para in paras if para.strip())
    return score_pair(
        memo_text,
        form_text,
        para_count=nonempty,
        filled_fields=filled_fields,
        filled_chars=filled_chars,
    )


def format_result(result: OracleResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        status,
        (
            f"  words: {result.word_count}  paras: {result.para_count}  "
            f"filled_fields: {result.filled_fields}  filled_chars: {result.filled_chars}"
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
        help="Saved memo (.odt/.docx), form (.odg), or trial directory",
    )
    parser.add_argument("--form", type=Path, default=None, help="Draw stand-in path")
    parser.add_argument("--memo", type=Path, default=None, help="Writer memo path")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args(argv)
    memo, form = resolve_gmp_artifacts(args.artifact, form=args.form, memo=args.memo)
    if memo is None or form is None:
        result = OracleResult(
            passed=False,
            failures=[
                f"need both memo and form (memo={memo}, form={form})",
            ],
        )
    else:
        result = score_artifacts(memo, form)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

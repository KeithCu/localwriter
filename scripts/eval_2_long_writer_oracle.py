#!/usr/bin/env python3
# WriterAgent - eval-2 / Long Writer pack oracle
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Soft structural scorer for the eval-2 native long Writer pack.

Pass/fail is document-local. Chat Ready / STREAM_DONE is never consulted.
This sibling is WriterAgent-native (no HF gold tree). Fail-closed checks
are TOC / named heading styles / review comments plus fixture identity
and a husk ban. Exact heading wording and comment authors stay out of v1.

Usage:
  .venv/bin/python scripts/eval_2_long_writer_oracle.py path/to/final_pack.odt
  .venv/bin/python scripts/eval_2_headed.py --task long-writer-pack --score path/to/final_pack.odt
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
_OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_TEXT_P = f"{{{_TEXT_NS}}}p"
_TEXT_H = f"{{{_TEXT_NS}}}h"
_TEXT_TOC = f"{{{_TEXT_NS}}}table-of-content"
_OFFICE_ANNOTATION = f"{{{_OFFICE_NS}}}annotation"
_WORD_MIN = 300
# A multi-section capital brief can run long; Ready-empty husks are far shorter.
_WORD_MAX = 4000
_MIN_HEADINGS = 3
_MIN_COMMENT_CHARS = 8

_HUSK_RE = re.compile(
    r"(?:#DIV/0!|Err:507|\bError:|_deal_|DEAL_|PYTHONFUNCTION)",
    re.IGNORECASE,
)
_NORTHHAVEN_RE = re.compile(r"northhaven", re.I)
_LIBRARY_RE = re.compile(r"civic\s+library", re.I)
_PROJECT_RE = re.compile(r"cl[\s\-]*2026[\s\-]*annex", re.I)
_BASE_BUDGET_RE = re.compile(r"4(?:\.|,)?2\s*(?:million|m)\b|\$\s*4(?:\.|,)?2", re.I)
_ANNEX_COST_RE = re.compile(
    r"1(?:\.|,)?8\s*(?:million|m)\b|\$\s*1(?:\.|,)?8"
    r"|2(?:\.|,)?4\s*(?:million|m)\b|\$\s*2(?:\.|,)?4",
    re.I,
)
_START_RE = re.compile(r"april\s+2027", re.I)
_END_RE = re.compile(r"october\s+2028", re.I)
_PURPOSE_RE = re.compile(
    r"\bpurpose\b|\bprogram\s+overview\b|\bintroduction\b|\bscope\s+of\s+work\b",
    re.I,
)
_BUDGET_RE = re.compile(r"\bbudget\b|\bschedule\b|construction\s+window", re.I)
_HOURS_RE = re.compile(
    r"public[\s\-]*access|\bweekend\b|\bsaturday\b|\bhours\b",
    re.I,
)
_DECISION_RE = re.compile(
    r"open\s+decisions?|annex\s+(?:option|siting)|funding\s+split|weekend\s+staff",
    re.I,
)
_CONTENTS_HEAD_RE = re.compile(r"^(?:table\s+of\s+)?contents?\b", re.I)
_HEADING_STYLE_RE = re.compile(
    r"^(?:Heading(?:_20_)?\d+|Title|Heading)$",
    re.I,
)
_TOC_STYLE_RE = re.compile(r"Contents_20_|TOC", re.I)


@dataclass
class OracleResult:
    """Fail-closed pack checks. Ready is never a field."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    word_count: int = 0
    para_count: int = 0
    heading_count: int = 0
    comment_count: int = 0
    has_toc: bool = False

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _style_name(node: ET.Element) -> str:
    for key, value in node.attrib.items():
        if _local_name(key) in {"style-name", "pStyle"}:
            return value or ""
    return ""


def _odt_root(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as zf:
        return ET.fromstring(zf.read("content.xml"))


def _docx_root(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as zf:
        return ET.fromstring(zf.read("word/document.xml"))


def _odt_blocks(root: ET.Element) -> list[str]:
    """Body blocks in document order: ``text:p`` and ``text:h``.

    Paragraphs that live *inside* ``office:annotation`` are skipped so
    comment text is not treated as a body heading. The host paragraph
    that *contains* an annotation is kept (``itertext`` includes the
    comment, which is fine for identity / husk checks).
    """
    inner_ids = {
        id(child)
        for ann in root.iter(_OFFICE_ANNOTATION)
        for child in ann.iter()
        if child.tag in (_TEXT_P, _TEXT_H)
    }
    blocks: list[str] = []
    for node in root.iter():
        if node.tag in (_TEXT_P, _TEXT_H) and id(node) not in inner_ids:
            blocks.append("".join(node.itertext()))
    return blocks


def _docx_blocks(root: ET.Element) -> list[str]:
    paras: list[str] = []
    for para in root.iter(f"{{{_W_NS}}}p"):
        text = "".join(node.text or "" for node in para.iter(f"{{{_W_NS}}}t"))
        paras.append(text)
    return paras


def read_pack_paragraphs(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_blocks(_docx_root(path))
    if suffix == ".odt":
        return _odt_blocks(_odt_root(path))
    raise ValueError(f"unsupported pack type: {path.suffix}")


def _odt_has_toc_field(root: ET.Element) -> bool:
    return root.find(f".//{_TEXT_TOC}") is not None


def _docx_has_toc_field(root: ET.Element) -> bool:
    xml = ET.tostring(root, encoding="unicode")
    if re.search(r"\bTOC\\", xml) or re.search(r">TOC<", xml):
        return True
    for node in root.iter():
        if _local_name(node.tag) == "instrText" and "TOC" in (node.text or ""):
            return True
        if _local_name(node.tag) == "docPartGallery":
            val = node.get(f"{{{_W_NS}}}val") or ""
            if "Table of Contents" in val or val.lower() == "tableofcontents":
                return True
    # Some writers store the TOC SDT only in document.xml aliases.
    return "tableofcontents" in xml.lower()


def _has_contents_index(blocks: list[str], headings: list[str]) -> bool:
    """Typed Contents list at the start that names later headings.

    Headings alone are not a TOC. A Contents block that repeats later
    section titles is an equivalent index for v1.
    """
    if not blocks:
        return False
    start_idx = None
    for idx, block in enumerate(blocks[:12]):
        if _CONTENTS_HEAD_RE.match(block.strip()):
            start_idx = idx
            break
    if start_idx is None:
        return False
    window = [b.strip() for b in blocks[start_idx + 1 : start_idx + 12] if b.strip()]
    heading_set = {h.strip().lower() for h in headings if h.strip()}
    hits = 0
    for line in window:
        lowered = line.lower()
        if lowered in heading_set:
            hits += 1
            continue
        for heading in heading_set:
            if heading and heading in lowered:
                hits += 1
                break
    return hits >= 3


def detect_toc(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix == ".odt":
        root = _odt_root(path)
        if _odt_has_toc_field(root):
            return True
        blocks = _odt_blocks(root)
        headings = ["".join(n.itertext()) for n in root.iter(_TEXT_H)]
        return _has_contents_index(blocks, headings)
    if suffix == ".docx":
        root = _docx_root(path)
        if _docx_has_toc_field(root):
            return True
        blocks = _docx_blocks(root)
        headings = _docx_heading_texts(root)
        return _has_contents_index(blocks, headings)
    return False


def _is_named_heading_style(style: str) -> bool:
    if not style or _TOC_STYLE_RE.search(style):
        return False
    compact = style.replace(" ", "")
    return bool(_HEADING_STYLE_RE.match(style) or _HEADING_STYLE_RE.match(compact))


def count_named_headings(path: Path) -> int:
    suffix = path.suffix.lower()
    if suffix == ".odt":
        root = _odt_root(path)
        count = 0
        for node in root.iter(_TEXT_H):
            text = "".join(node.itertext()).strip()
            if text and not _CONTENTS_HEAD_RE.match(text):
                count += 1
        for node in root.iter(_TEXT_P):
            style = _style_name(node)
            if _is_named_heading_style(style):
                text = "".join(node.itertext()).strip()
                if text and not _CONTENTS_HEAD_RE.match(text):
                    count += 1
        return count
    if suffix == ".docx":
        return len(_docx_heading_texts(_docx_root(path)))
    return 0


def _docx_heading_texts(root: ET.Element) -> list[str]:
    headings: list[str] = []
    for para in root.iter(f"{{{_W_NS}}}p"):
        style = ""
        ppr = para.find(f"{{{_W_NS}}}pPr")
        if ppr is not None:
            pstyle = ppr.find(f"{{{_W_NS}}}pStyle")
            if pstyle is not None:
                style = pstyle.get(f"{{{_W_NS}}}val") or ""
        outline = para.find(f"{{{_W_NS}}}pPr/{{{_W_NS}}}outlineLvl")
        text = "".join(node.text or "" for node in para.iter(f"{{{_W_NS}}}t")).strip()
        if not text or _CONTENTS_HEAD_RE.match(text):
            continue
        if _is_named_heading_style(style) or (outline is not None):
            headings.append(text)
    return headings


def read_comments(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    comments: list[str] = []
    if suffix == ".odt":
        root = _odt_root(path)
        for node in root.iter(_OFFICE_ANNOTATION):
            text = " ".join(part.strip() for part in node.itertext() if part.strip())
            if text:
                comments.append(text)
        return comments
    if suffix == ".docx":
        with zipfile.ZipFile(path) as zf:
            if "word/comments.xml" not in zf.namelist():
                return []
            root = ET.fromstring(zf.read("word/comments.xml"))
        for node in root.iter(f"{{{_W_NS}}}comment"):
            text = "".join(t.text or "" for t in node.iter(f"{{{_W_NS}}}t")).strip()
            if text:
                comments.append(text)
        return comments
    return []


def _nonempty_comments(comments: list[str]) -> list[str]:
    kept: list[str] = []
    for text in comments:
        body = text.strip()
        if len(body) < _MIN_COMMENT_CHARS:
            continue
        if _HUSK_RE.search(body):
            continue
        kept.append(body)
    return kept


def score_text(
    text: str,
    *,
    para_count: int,
    heading_count: int,
    comment_count: int,
    has_toc: bool,
) -> OracleResult:
    """Apply fail-closed checks to extracted pack text + structure."""
    failures: list[str] = []
    words = _word_count(text)
    if not text.strip():
        failures.append("pack body is empty")
    if words < _WORD_MIN:
        failures.append(f"word_count {words} < {_WORD_MIN} (Ready-empty / too short)")
    if words > _WORD_MAX:
        failures.append(f"word_count {words} > {_WORD_MAX}")
    if _HUSK_RE.search(text):
        failures.append("body contains Error:/husk residue")
    if not _NORTHHAVEN_RE.search(text):
        failures.append("missing Northhaven")
    if not _LIBRARY_RE.search(text):
        failures.append("missing Civic Library")
    if not _PROJECT_RE.search(text):
        failures.append("missing project code CL-2026-ANNEX")
    if not _BASE_BUDGET_RE.search(text):
        failures.append("missing base renovation $4.2 million")
    if not _ANNEX_COST_RE.search(text):
        failures.append("missing annex option cost ($1.8M or $2.4M)")
    if not _START_RE.search(text):
        failures.append("missing April 2027 construction start")
    if not _END_RE.search(text):
        failures.append("missing October 2028 construction end")
    if not _PURPOSE_RE.search(text):
        failures.append("missing purpose / scope section")
    if not _BUDGET_RE.search(text):
        failures.append("missing budget / schedule section")
    if not _HOURS_RE.search(text):
        failures.append("missing public-access / hours theme")
    if not _DECISION_RE.search(text):
        failures.append("missing open-decision theme")
    if not has_toc:
        failures.append("missing table of contents / equivalent index at the start")
    if heading_count < _MIN_HEADINGS:
        failures.append(
            f"named heading styles {heading_count} < {_MIN_HEADINGS} "
            "(bold Default is not enough)"
        )
    if comment_count < 1:
        failures.append("missing review comment on a real span")
    return OracleResult(
        passed=not failures,
        failures=failures,
        word_count=words,
        para_count=para_count,
        heading_count=heading_count,
        comment_count=comment_count,
        has_toc=has_toc,
    )


def score_pack(path: Path | str) -> OracleResult:
    pack = Path(path)
    if not pack.is_file():
        return OracleResult(passed=False, failures=[f"pack not found: {pack}"])
    try:
        paras = read_pack_paragraphs(pack)
        has_toc = detect_toc(pack)
        heading_count = count_named_headings(pack)
        comments = _nonempty_comments(read_comments(pack))
    except Exception as exc:
        return OracleResult(passed=False, failures=[f"cannot read pack: {exc}"])
    text = "\n".join(paras)
    nonempty = sum(1 for para in paras if para.strip())
    return score_text(
        text,
        para_count=nonempty,
        heading_count=heading_count,
        comment_count=len(comments),
        has_toc=has_toc,
    )


def format_result(result: OracleResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        status,
        (
            f"  words: {result.word_count}  paras: {result.para_count}  "
            f"headings: {result.heading_count}  comments: {result.comment_count}  "
            f"toc: {result.has_toc}"
        ),
    ]
    for item in result.failures:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path, help="Saved trial .odt (or .docx)")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args(argv)
    result = score_pack(args.pack)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

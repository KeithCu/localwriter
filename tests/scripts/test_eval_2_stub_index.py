# WriterAgent tests for eval-2 sibling stubs 5–10
# Copyright (c) 2026 KeithCu (modifications and relicensing)
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stub folders stay light: required files, no fake gold, no product internals."""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_EVAL2 = _REPO / "docs" / "eval" / "eval-2"
_README = _EVAL2 / "README.md"

# Ready siblings already have headed helper + oracle. Stubs 5–10 do not.
_READY = (
    "tenant-retention-ed2bc14c",
    "cadaver-proposal-61b0946a",
    "afc-sample-83d10b06",
    "gmp-change-control-58ac1cc5",
)
_STUBS = (
    "writer-calc-peer-write",
    "calc-primary-model",
    "writer-headed-template",
    "draw-primary-deliverable",
    "reverse-tenant",
    "long-writer-pack",
)
_STUB_FILES = (
    "notes.md",
    "SOURCE.md",
    "run.md",
    "prompt.writeragent.txt",
    "rubric.eval2.md",
    "fixtures/.gitkeep",
    "runs/.gitkeep",
)
_BANNED_PRODUCT_INTERNALS = (
    "send_peer_message",
    "fill_draw_fields",
    "document_research",
    "specialized_workflow_finished",
    "peer_inner",
)
_BANNED_STEERING = (
    "don't invent",
    "do not invent",
    "don't make up",
    "from knowledge",
    "web not required",
    "already named",
)
_IN_TREE_GOLD_IDS = (
    "ed2bc14c-99ac-4a2a-8467-482a1a5d67f3",
    "61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0",
    "83d10b06-26d1-4636-a32c-23f92c57f30b",
    "58ac1cc5-5754-4580-8c9c-8c67e1a9d619",
)


def test_readme_lists_siblings_1_to_10() -> None:
    text = _README.read_text(encoding="utf-8")
    for slug in _READY + _STUBS:
        assert f"`{slug}/`" in text or f"({slug}/)" in text, slug
    assert "Ready" in text
    assert "Stub" in text
    assert "PARKED" in text
    assert "5–10 are not wired" in text or "5-10 are not wired" in text


def test_stub_folders_have_required_files() -> None:
    for slug in _STUBS:
        root = _EVAL2 / slug
        for rel in _STUB_FILES:
            path = root / rel
            assert path.is_file(), path


def test_stub_source_is_todo_not_in_tree_gold() -> None:
    """Stubs must not claim an in-repo gdpval package they do not have."""
    for slug in _STUBS:
        source = (_EVAL2 / slug / "SOURCE.md").read_text(encoding="utf-8")
        assert "Needs gold materials" in source, slug
        assert "docs/eval/gdpval/" in source
        # Candidate HF ids are fine; claiming an in-tree gold tree is not.
        assert "Gold task id | TODO" in source or "Gold task id" in source
        assert "TODO — not in-repo" in source, slug
        for gold_id in _IN_TREE_GOLD_IDS:
            claimed = f"docs/eval/gdpval/{gold_id}/"
            assert claimed not in source, (slug, gold_id)


def test_stub_prompts_are_todo_and_avoid_product_internals() -> None:
    for slug in _STUBS:
        text = (_EVAL2 / slug / "prompt.writeragent.txt").read_text(encoding="utf-8")
        assert text.lstrip().startswith("TODO"), slug
        lowered = text.lower()
        for banned in _BANNED_PRODUCT_INTERNALS:
            assert banned not in lowered, (slug, banned)
        for banned in _BANNED_STEERING:
            assert banned not in lowered, (slug, banned)


def test_writer_headed_template_is_parked() -> None:
    notes = (_EVAL2 / "writer-headed-template" / "notes.md").read_text(encoding="utf-8")
    run = (_EVAL2 / "writer-headed-template" / "run.md").read_text(encoding="utf-8")
    assert "PARKED" in notes
    assert "#634" in notes
    assert "Do not run a headed trial" in run or "Do not run" in run


def test_stub_run_md_does_not_invent_helper_flags() -> None:
    for slug in _STUBS:
        run = (_EVAL2 / slug / "run.md").read_text(encoding="utf-8")
        assert "Not wired" in run or "not wired" in run, slug
        assert f"--task {slug}" not in run, slug
        assert "openai/gpt-oss-120b:nitro" in run
        assert "make deploy" in run


def test_user_facing_stub_notes_omit_duckdb() -> None:
    """Keep DuckDB off user-facing eval-2 stub notes."""
    for slug in _STUBS:
        for name in (
            "notes.md",
            "SOURCE.md",
            "run.md",
            "prompt.writeragent.txt",
            "rubric.eval2.md",
        ):
            text = (_EVAL2 / slug / name).read_text(encoding="utf-8")
            assert "duckdb" not in text.lower(), (slug, name)

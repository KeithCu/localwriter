# WriterAgent tests for scripts/eval_2_headed.py
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from eval_2_headed import (  # noqa: E402
    DEFAULT_MAX_TOOL_ROUNDS,
    EVAL_2_MAX_TOOL_ROUNDS,
    MAX_TOOL_ROUNDS_KEY,
    POPULATION_ODS_NAME,
    _AFC_DIR,
    apply_max_tool_rounds,
    default_eval2_trial_dir,
    find_writeragent_json,
    read_max_tool_rounds,
    restore_max_tool_rounds,
    stage_clean_trial_ods,
    temporary_max_tool_rounds,
)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_read_max_tool_rounds_absent_is_15() -> None:
    assert read_max_tool_rounds({}) == DEFAULT_MAX_TOOL_ROUNDS
    assert DEFAULT_MAX_TOOL_ROUNDS == 15


def test_apply_and_restore_removes_absent_key() -> None:
    data: dict[str, object] = {"text_model": "keep"}
    previous = apply_max_tool_rounds(data, 50)
    assert previous is None
    assert data[MAX_TOOL_ROUNDS_KEY] == 50
    restore_max_tool_rounds(data, previous)
    assert MAX_TOOL_ROUNDS_KEY not in data
    assert data["text_model"] == "keep"


def test_apply_and_restore_keeps_prior_value() -> None:
    data: dict[str, object] = {MAX_TOOL_ROUNDS_KEY: 20}
    previous = apply_max_tool_rounds(data, EVAL_2_MAX_TOOL_ROUNDS)
    assert previous == 20
    assert data[MAX_TOOL_ROUNDS_KEY] == 50
    restore_max_tool_rounds(data, previous)
    assert data[MAX_TOOL_ROUNDS_KEY] == 20


def test_temporary_max_tool_rounds_removes_key_when_absent(tmp_path: Path) -> None:
    config = tmp_path / "writeragent.json"
    _write(config, '{\n    "text_model": "keep-me"\n}\n')
    with temporary_max_tool_rounds(config):
        data = json.loads(config.read_text(encoding="utf-8"))
        assert data[MAX_TOOL_ROUNDS_KEY] == EVAL_2_MAX_TOOL_ROUNDS
        assert data["text_model"] == "keep-me"
    restored = json.loads(config.read_text(encoding="utf-8"))
    assert MAX_TOOL_ROUNDS_KEY not in restored
    assert restored["text_model"] == "keep-me"


def test_temporary_max_tool_rounds_restores_prior_value(tmp_path: Path) -> None:
    config = tmp_path / "writeragent.json"
    _write(config, json.dumps({MAX_TOOL_ROUNDS_KEY: 20, "endpoint": "http://x"}, indent=4) + "\n")
    with temporary_max_tool_rounds(config):
        assert json.loads(config.read_text(encoding="utf-8"))[MAX_TOOL_ROUNDS_KEY] == 50
    assert json.loads(config.read_text(encoding="utf-8"))[MAX_TOOL_ROUNDS_KEY] == 20


def test_temporary_max_tool_rounds_restores_after_error(tmp_path: Path) -> None:
    config = tmp_path / "writeragent.json"
    _write(config, '{"ok": true}\n')
    with pytest.raises(RuntimeError, match="boom"):
        with temporary_max_tool_rounds(config):
            raise RuntimeError("boom")
    assert MAX_TOOL_ROUNDS_KEY not in json.loads(config.read_text(encoding="utf-8"))


def test_temporary_max_tool_rounds_keeps_comment_header(tmp_path: Path) -> None:
    config = tmp_path / "writeragent.json"
    _write(config, "// schema\n{\n    \"text_model\": \"gpt\"\n}\n")
    with temporary_max_tool_rounds(config):
        text = config.read_text(encoding="utf-8")
        assert text.startswith("// schema")
        assert json.loads(text.split("\n", 1)[1])[MAX_TOOL_ROUNDS_KEY] == 50
    restored = config.read_text(encoding="utf-8")
    assert restored.startswith("// schema")
    assert MAX_TOOL_ROUNDS_KEY not in json.loads(restored.split("\n", 1)[1])


def test_find_writeragent_json_explicit(tmp_path: Path) -> None:
    path = tmp_path / "custom.json"
    _write(path, "{}")
    assert find_writeragent_json(path) == path


def test_find_writeragent_json_missing() -> None:
    with pytest.raises(FileNotFoundError, match="writeragent.json"):
        find_writeragent_json(candidates=[])


def _afc_style_tree(root: Path) -> Path:
    """Task dir + fixtures siblings that document_research would otherwise see."""
    fixtures = root / "fixtures"
    fixtures.mkdir()
    (fixtures / POPULATION_ODS_NAME).write_bytes(b"ODS-BYTES")
    (fixtures / "Population v2.xlsx").write_bytes(b"XLSX")
    (fixtures / "min-range-too-large.ods").write_bytes(b"MIN")
    (root / "prompt.writeragent.txt").write_text("PROMPT-LEAK", encoding="utf-8")
    (root / "rubric_pretty.txt").write_text("RUBRIC-LEAK", encoding="utf-8")
    (root / "notes.md").write_text("NOTES-LEAK", encoding="utf-8")
    gold = root / "gold"
    gold.mkdir()
    (gold / "Sample v2.xlsx").write_bytes(b"GOLD")
    return fixtures / POPULATION_ODS_NAME


def test_stage_clean_trial_dir_contains_only_population_ods(tmp_path: Path) -> None:
    source = _afc_style_tree(tmp_path / "afc-sample")
    dest = tmp_path / "trial"
    result = stage_clean_trial_ods(source, dest)
    names = sorted(p.name for p in dest.iterdir())
    assert names == [POPULATION_ODS_NAME]
    assert result == dest / POPULATION_ODS_NAME
    assert result.read_bytes() == b"ODS-BYTES"


def test_stage_clean_trial_dir_wipes_leftovers(tmp_path: Path) -> None:
    source = _afc_style_tree(tmp_path / "afc-sample")
    dest = tmp_path / "trial"
    dest.mkdir()
    (dest / "prompt.writeragent.txt").write_text("old", encoding="utf-8")
    (dest / "extra.ods").write_bytes(b"extra")
    leftover_dir = dest / "notes"
    leftover_dir.mkdir()
    (leftover_dir / "rubric.txt").write_text("old", encoding="utf-8")
    stage_clean_trial_ods(source, dest)
    assert sorted(p.name for p in dest.iterdir()) == [POPULATION_ODS_NAME]


def test_stage_clean_trial_dir_refuses_fixture_folder(tmp_path: Path) -> None:
    source = _afc_style_tree(tmp_path / "afc-sample")
    with pytest.raises(ValueError, match="protected"):
        stage_clean_trial_ods(source, source.parent)


def test_stage_clean_trial_dir_refuses_real_afc_task_dir(tmp_path: Path) -> None:
    source = _afc_style_tree(tmp_path / "afc-sample")
    with pytest.raises(ValueError, match="protected"):
        stage_clean_trial_ods(source, _AFC_DIR)


def test_stage_clean_trial_dir_missing_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Population fixture"):
        stage_clean_trial_ods(tmp_path / "missing.ods", tmp_path / "trial")


def test_default_eval2_trial_dir_is_tmp_subdir() -> None:
    path = default_eval2_trial_dir()
    assert path.name == "writeragent-eval2-afc"
    assert path.parent == Path(tempfile.gettempdir())

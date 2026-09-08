# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2026 KeithCu
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for native-runner progress and CLI filter helpers."""

from __future__ import annotations

from pathlib import Path

from plugin.testing_runner import (
    _cli_filters,
    _function_name_matches,
    _is_case_id,
    _module_matches_filters,
    _test_function_filters,
)


def test_test_function_filters_skips_module_path_tokens() -> None:
    assert _test_function_filters(["test_cells_uno", "tests/calc/foo.py"]) == []
    assert _test_function_filters(["test_read_range_format_info_performance"]) == [
        "test_read_range_format_info_performance"
    ]


def test_test_function_filters_accepts_packet_letter_and_case_id() -> None:
    assert _test_function_filters(["E", "f3a", "B"]) == ["E", "f3a", "B"]
    assert _test_function_filters(["tests/chatbot/test_mock_llm_sidebar_uno.py", "E"]) == ["E"]


def test_is_case_id() -> None:
    assert _is_case_id("f3a") is True
    assert _is_case_id("e9") is True
    assert _is_case_id("b1a") is True
    assert _is_case_id("f") is False
    assert _is_case_id("f10") is True
    assert _is_case_id("test_f1") is False


def test_function_name_matches_packet_letter() -> None:
    assert _function_name_matches("test_f18_event_ping_then_hello", ["F"]) is True
    assert _function_name_matches("test_f3a_hang_the_stream_then_hello", ["f"]) is True
    assert _function_name_matches("test_b1a_stop_ramble_then_hello", ["B"]) is True
    assert _function_name_matches("test_e9c_hitl_change", ["E"]) is True
    assert _function_name_matches("test_c1_say_nothing_truncated_then_hello", ["C"]) is True
    assert _function_name_matches("test_d1_think_out_loud_thinking_then_html", ["D"]) is True
    assert _function_name_matches("test_foo_bar", ["F"]) is False
    assert _function_name_matches("test_e7_outline_delegate", ["B"]) is False
    assert _function_name_matches("test_p1_total_row_peer_roundtrip", ["P"]) is True
    assert _function_name_matches("test_p2_wait_after_accepted_deadlocks_peer", ["p"]) is True
    assert _function_name_matches("test_p3_busy_then_queue_reply", ["P"]) is True
    assert _function_name_matches("test_panel_factory", ["P"]) is False


def test_function_name_matches_case_id_no_prefix_bleed() -> None:
    assert _function_name_matches("test_f1_crash_the_stream_then_hello", ["f1"]) is True
    assert _function_name_matches("test_f10_truncated_json_then_hello", ["f1"]) is False
    assert _function_name_matches("test_f10_truncated_json_then_hello", ["f10"]) is True
    assert _function_name_matches("test_e9a_hitl_accept", ["e9"]) is False
    assert _function_name_matches("test_e9a_hitl_accept", ["e9a"]) is True


def test_function_name_matches_full_test_name() -> None:
    name = "test_e7_outline_delegate"
    assert _function_name_matches(name, [name]) is True
    assert _function_name_matches("test_e7_outline_delegate_extra", ["test_e7_outline_delegate"]) is True
    assert _function_name_matches("test_e70_other", ["test_e7"]) is False


def test_module_matches_filters_by_path_or_def_name(tmp_path: Path) -> None:
    path = tmp_path / "test_cells_uno.py"
    path.write_text("def test_read_range_format_info_performance(ctx, doc):\n    return\n", encoding="utf-8")
    full = str(path)
    assert _module_matches_filters(full, path.name, ["test_cells_uno"]) is True
    assert _module_matches_filters(full, path.name, ["test_read_range_format_info_performance"]) is True
    assert _module_matches_filters(full, path.name, ["test_unrelated_other"]) is False


def test_module_matches_filters_by_packet_letter(tmp_path: Path) -> None:
    path = tmp_path / "test_mock_llm_sidebar_uno.py"
    path.write_text(
        "def test_f1_crash(ctx):\n    return\n\ndef test_e7_outline(ctx):\n    return\n",
        encoding="utf-8",
    )
    full = str(path)
    assert _module_matches_filters(full, path.name, ["E"]) is True
    assert _module_matches_filters(full, path.name, ["B"]) is False
    assert _module_matches_filters(full, path.name, ["f1"]) is True
    assert _module_matches_filters(full, path.name, ["f10"]) is False


def test_cli_filters_default_empty() -> None:
    assert isinstance(_cli_filters, list)

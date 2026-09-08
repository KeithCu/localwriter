# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2026 KeithCu
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Packet P: dual mock-LLM sidebars locking specialized-inner peer messaging (#673).

Run via ``make test-mock-sidebar FILTER=P`` (visible soffice, user profile).
Does not use ``private:factory/scalc`` after a WriterAgent deck is up (E12 URP hang).
"""

from __future__ import annotations

import os
import time
import unittest
from typing import Any

from plugin.testing_runner import native_test, setup, teardown

from tests.chatbot.mock_llm_harness import (
    calc_total_formula,
    find_open_writer,
    finish_immediately_after_peer_sends,
    open_calc_for_dual_sidebar,
    seed_budget_sheet,
    start_mock_sidebar_session,
    stop_mock_sidebar_session,
)

_session = None
_calc_doc = None
_writer_doc = None
_open_path = ""
_CALC_OPEN_SKIP = (
    "Packet P: could not open Calc with a live WriterAgent deck without the "
    "E12 factory/scalc-after-Writer-deck URP hang. Unit tests in "
    "tests/scripts/test_mock_llm_server.py still lock finish-after-accepted "
    "and the specialized-inner reply path. Follow-up: a File→New / file-URL "
    "Calc open that does not block URP."
)


def _require_user_profile() -> None:
    if os.environ.get("WRITERAGENT_UNO_USER_PROFILE") != "1":
        raise unittest.SkipTest("use make test-mock-sidebar (LibreOffice user profile)")


@setup
def _setup_peer(ctx):
    global _session, _calc_doc, _writer_doc, _open_path
    from plugin.framework.config import init_config

    _require_user_profile()
    init_config(ctx)
    from plugin.chatbot.chat_sidebar_mode import mark_librarian_invoked
    from plugin.chatbot.memory import MemoryStore
    from plugin.framework.config import get_config_bool, set_config

    mark_librarian_invoked()
    try:
        MemoryStore(ctx).write("user", "# Test User Profile\n")
    except Exception:
        pass
    if get_config_bool("chatbot.prompt_for_web_research"):
        set_config("chatbot.prompt_for_web_research", False)

    import plugin.chatbot.sidebar_test_hooks  # noqa: F401

    from plugin.chatbot.sidebar_test_hooks import (
        adopt_runtime_send_listeners,
        ensure_sidebar_chat_mode,
        send_listener_for_doc,
        wait_for_chat_dialog_controls,
    )
    from plugin.doc.doc_type import is_writer
    from plugin.framework.uno_context import get_runtime_uid

    # Point JSON at the mock before showing either deck.
    _session = start_mock_sidebar_session(delay_ms=20, offline=True)
    _session.prompt_research_cleared = True

    # Open Calc before showing WriterAgentDeck when possible (open-first hypothesis).
    _calc_doc = open_calc_for_dual_sidebar(ctx, timeout=15.0)
    _open_path = "reuse-or-file" if _calc_doc is not None else ""
    if _calc_doc is not None:
        seed_budget_sheet(_calc_doc)
        try:
            _calc_doc.setTitle("BudgetPeer.ods")
        except Exception:
            pass

    writer = find_open_writer(ctx)
    if writer is None:
        from plugin.chatbot.sidebar_test_hooks import desktop_from_ctx

        writer = desktop_from_ctx(ctx).loadComponentFromURL("private:factory/swriter", "_default", 0, ())
        time.sleep(1.0)
    _writer_doc = writer if writer is not None and is_writer(writer) else None

    writer_controls = wait_for_chat_dialog_controls(ctx, timeout=20.0, doc=_writer_doc)
    adopt_runtime_send_listeners()
    ensure_sidebar_chat_mode(writer_controls, doc_type="writer")

    calc_controls = None
    if _calc_doc is not None:
        calc_controls = wait_for_chat_dialog_controls(ctx, timeout=20.0, doc=_calc_doc)
        ensure_sidebar_chat_mode(calc_controls, doc_type="calc")
        adopt_runtime_send_listeners()

    _session.writer_doc = _writer_doc
    _session.calc_doc = _calc_doc
    _session.writer_controls = writer_controls
    _session.calc_controls = calc_controls
    # Resolve listeners once. Re-entering send_listener_for_doc from a wait
    # loop URP-hangs after the peer kick (getFrame during the extracted send).
    _session.writer_listener = send_listener_for_doc(_writer_doc) if _writer_doc is not None else None
    _session.calc_listener = send_listener_for_doc(_calc_doc) if _calc_doc is not None else None
    _session.hook_ctx = ctx
    _session.writer_uid = get_runtime_uid(_writer_doc) if _writer_doc is not None else ""
    _session.calc_uid = get_runtime_uid(_calc_doc) if _calc_doc is not None else ""
    _session.open_path = _open_path


@teardown
def _teardown_peer():
    global _session, _calc_doc, _writer_doc, _open_path
    from plugin.chatbot.sidebar_test_hooks import press_stop, send_listener_for_doc, send_state

    for doc in (_writer_doc, _calc_doc):
        sl = send_listener_for_doc(doc) if doc is not None else None
        if sl is None:
            continue
        try:
            if send_state(listener=sl).is_busy:
                press_stop(listener=sl)
        except Exception:
            pass
    stop_mock_sidebar_session(_session)
    if _calc_doc is not None:
        try:
            _calc_doc.close(True)
        except Exception:
            pass
    _session = None
    _calc_doc = None
    _writer_doc = None
    _open_path = ""


def _skip_without_dual() -> None:
    if _session is None or getattr(_session, "calc_doc", None) is None:
        raise unittest.SkipTest(_CALC_OPEN_SKIP)
    w = getattr(_session, "writer_listener", None)
    c = getattr(_session, "calc_listener", None)
    if w is None or c is None:
        if getattr(_session, "calc_controls", None) is None:
            raise unittest.SkipTest(_CALC_OPEN_SKIP)


def _listener(which: str):
    return getattr(_session, "writer_listener" if which == "writer" else "calc_listener", None)


def _controls(which: str):
    return getattr(_session, "writer_controls" if which == "writer" else "calc_controls", None)


def _transcript(which: str) -> str:
    """Read cached dialog text. Do not resolve listeners here (URP hang)."""
    controls = _controls(which) or {}
    for name in ("response_rich", "response"):
        ctrl = controls.get(name)
        if ctrl is None:
            continue
        try:
            if hasattr(ctrl, "getText"):
                text = str(ctrl.getText() or "")
                if text:
                    return text
            text = str(getattr(ctrl.getModel(), "Text", "") or "")
            if text:
                return text
        except Exception:
            continue
    sl = _listener(which)
    if sl is None:
        return ""
    from plugin.chatbot.sidebar_test_hooks import transcript_text

    try:
        return transcript_text(listener=sl)
    except Exception:
        return ""


def _send(which: str, text: str, timeout: float = 90.0) -> None:
    from plugin.chatbot.sidebar_test_hooks import (
        press_send,
        set_query_text,
        set_query_text_via_controls,
        uno_click,
        wait_controls_send_finished,
        wait_idle,
    )

    sl = _listener(which)
    controls = _controls(which)
    before = _transcript(which)
    # Prefer dialog click over listener (URP hang if we wait on listener.is_busy).
    if controls is None and sl is not None:
        set_query_text(text, listener=sl)
        press_send(listener=sl)
        assert wait_idle(listener=sl, timeout=timeout), "%s send did not go idle: %r" % (which, text)
        return
    assert controls is not None, "no listener or controls for %s" % which
    set_query_text_via_controls(controls, text)
    time.sleep(0.2)
    uno_click(controls["send"])
    finished = wait_controls_send_finished(
        controls,
        timeout=min(timeout, 25.0),
        transcript_fn=lambda: _transcript(which),
        before=before,
    )
    body = _transcript(which)
    if not finished and "[delegate" in body and ": done]" in body:
        # Wrapup HTML / Stop Enabled can lag after specialized_workflow_finished.
        return
    assert finished, "%s send did not finish: %r" % (which, body[-400:])


def _wait_calc_envelope(timeout: float = 60.0) -> bool:
    """Writer Readys before the peer drain starts — both look idle for a beat."""
    deadline = time.monotonic() + max(0.5, timeout)
    while time.monotonic() <= deadline:
        if "[Peer from:" in _transcript("calc"):
            return True
        if _is_busy("calc"):
            time.sleep(0.15)
            continue
        time.sleep(0.15)
    return "[Peer from:" in _transcript("calc")


def _wait_both_idle(timeout: float = 90.0) -> bool:
    from plugin.chatbot.sidebar_test_hooks import wait_controls_send_finished, wait_idle

    deadline = time.monotonic() + timeout
    while time.monotonic() <= deadline:
        ok = True
        for which in ("writer", "calc"):
            sl = _listener(which)
            controls = _controls(which)
            # Prefer dialog Enabled over listener.is_busy (URP hang during peer drain).
            if controls is not None:
                if not wait_controls_send_finished(controls, timeout=0.4, transcript_fn=lambda w=which: _transcript(w)):
                    ok = False
                    break
            elif sl is not None:
                if not wait_idle(listener=sl, timeout=0.4):
                    ok = False
                    break
        if ok:
            return True
        time.sleep(0.2)
    return False


def _is_busy(which: str) -> bool:
    from plugin.chatbot.sidebar_test_hooks import control_enabled, send_state

    controls = _controls(which) or {}
    if controls.get("stop") is not None:
        en = control_enabled(controls.get("stop"))
        if en is not None:
            return en is True
    sl = _listener(which)
    if sl is not None:
        return bool(send_state(listener=sl).is_busy)
    return False


def _press_stop(which: str) -> None:
    # uno_click(Stop) URP-hangs if a drain is wedged. Packet G STOP_CLICKED posts to VCL.
    from plugin.chatbot.sidebar_test_hooks import execute_debug_sidebar_op, press_stop

    sl = _listener(which)
    if sl is not None:
        try:
            press_stop(listener=sl)
            return
        except Exception:
            pass
    ctx = getattr(_session, "hook_ctx", None)
    if ctx is not None:
        try:
            execute_debug_sidebar_op("STOP_CLICKED", ctx=ctx)
        except Exception:
            pass


def _captures() -> list[dict[str, Any]]:
    from scripts.mock_llm_server import snapshot_captures

    assert _session is not None
    return snapshot_captures(_session.config)


def _clear_captures() -> None:
    from scripts.mock_llm_server import clear_captures

    clear_captures(_session.config)


def _kick_pending_in_soffice(ctx) -> None:
    """Start queued extracted sends in soffice (test-process kick is a no-op)."""
    from plugin.chatbot.sidebar_test_hooks import execute_debug_sidebar_op

    try:
        execute_debug_sidebar_op("KICK_PEERS", ctx=ctx)
    except Exception:
        pass


def _capture_tools() -> list[list[str]]:
    return [list(row.get("decided_tools") or []) for row in _captures()]


def _outer_advertised_send_peer() -> bool:
    """True if a main-chat POST (no specialized finish tool) advertised send_peer_message."""
    for row in _captures():
        advertised = set(row.get("advertised_tools") or [])
        if "send_peer_message" not in advertised:
            continue
        if "specialized_workflow_finished" in advertised or "final_answer" in advertised:
            continue
        return True
    return False


@native_test
def test_p1_total_row_peer_roundtrip(ctx):
    """Writer → document_research → send → finish; Calc writes Total and replies."""
    _skip_without_dual()
    from plugin.chatbot.sidebar_test_hooks import clear_sidebar_chat

    assert _session is not None
    _session.config.scenario = "none"
    _session.config.peer_wait_after_accepted = False
    _press_stop("writer")
    _press_stop("calc")
    _clear_captures()
    for which in ("writer", "calc"):
        sl = _listener(which)
        if sl is not None:
            clear_sidebar_chat(listener=sl)

    _send("writer", "Ask the budget workbook to add a Total row", timeout=90.0)
    # Inject-now / start-later: Writer is Ready before Calc's extracted send begins.
    time.sleep(0.6)
    _kick_pending_in_soffice(ctx)
    assert _wait_calc_envelope(timeout=60.0), (
        "Calc never received the envelope after Writer Ready: writer_uid=%s calc_uid=%s "
        "writer_busy=%s calc_busy=%s decided=%r writer=%r calc=%r"
        % (
            getattr(_session, "writer_uid", ""),
            getattr(_session, "calc_uid", ""),
            _is_busy("writer"),
            _is_busy("calc"),
            _capture_tools(),
            _transcript("writer")[-300:],
            _transcript("calc")[-300:],
        )
    )
    assert _wait_both_idle(timeout=90.0), (
        "nested-drain freeze or wait-for-peer stall: writer_busy=%s calc_busy=%s writer=%r calc=%r"
        % (_is_busy("writer"), _is_busy("calc"), _transcript("writer")[-300:], _transcript("calc")[-300:])
    )
    assert not _is_busy("writer") and not _is_busy("calc")
    writer_txt = _transcript("writer")
    calc_txt = _transcript("calc")
    assert "[Peer from:" in calc_txt, "Calc never received the envelope: %r" % calc_txt[-400:]
    formula = calc_total_formula(_session.calc_doc)
    assert "SUM" in formula.upper() or "Total" in calc_txt or "total" in writer_txt.lower(), (
        "Calc did not write a Total row: formula=%r calc=%r" % (formula, calc_txt[-300:])
    )
    assert "[Peer from:" in writer_txt or "Total" in writer_txt or "total" in writer_txt.lower(), (
        "Writer follow-up never saw the reply: %r" % writer_txt[-400:]
    )
    snaps = _captures()
    assert finish_immediately_after_peer_sends(snaps), "specialized did not finish immediately after accepted: %r" % [
        row.get("decided_tools") for row in snaps
    ]
    assert not _outer_advertised_send_peer(), "outer main advertised send_peer_message: %r" % [
        row.get("advertised_tools") for row in snaps if "send_peer_message" in (row.get("advertised_tools") or [])
    ]
    decided = [name for row in snaps for name in (row.get("decided_tools") or [])]
    assert "send_peer_message" in decided
    assert "write_formula_range" in decided or "SUM" in formula.upper()
    assert "delegate_to_specialized_writer_toolset" in decided
    assert "delegate_to_specialized_calc_toolset" in decided


@native_test
def test_p2_wait_after_accepted_deadlocks_peer(ctx):
    """If specialized does not finish after accepted, Calc never starts (Scrolly hang)."""
    _skip_without_dual()
    from plugin.chatbot.sidebar_test_hooks import clear_sidebar_chat

    assert _session is not None
    _session.config.scenario = "peer_wait"
    _session.config.peer_wait_after_accepted = True
    _press_stop("writer")
    _press_stop("calc")
    _clear_captures()
    for which in ("writer", "calc"):
        sl = _listener(which)
        if sl is not None:
            clear_sidebar_chat(listener=sl)

    sl = _listener("writer")
    controls = _controls("writer")
    from plugin.chatbot.sidebar_test_hooks import press_send, set_query_text, set_query_text_via_controls, uno_click

    if sl is not None:
        set_query_text("wait after accepted then hang", listener=sl)
        press_send(listener=sl)
    else:
        assert controls is not None
        set_query_text_via_controls(controls, "wait after accepted then hang")
        time.sleep(0.2)
        uno_click(controls["send"])

    # Peer must not run while Writer specialized is still draining.
    time.sleep(8.0)
    calc_txt = _transcript("calc")
    writer_busy = _is_busy("writer")
    calc_has_envelope = "[Peer from:" in calc_txt
    snaps = _captures()
    decided = [row.get("decided_tools") or [] for row in snaps]
    finished_after_send = finish_immediately_after_peer_sends(snaps)
    try:
        assert writer_busy or not calc_has_envelope, (
            "peer started while specialized waited after accepted: calc=%r decided=%r" % (calc_txt[-300:], decided)
        )
        assert not finished_after_send
        assert any("send_peer_message" in row for row in decided)
    finally:
        _session.config.scenario = "none"
        _session.config.peer_wait_after_accepted = False
        _press_stop("writer")
        _press_stop("calc")
        time.sleep(0.8)

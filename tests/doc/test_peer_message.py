"""Unit tests for A1 send_peer_message (no live soffice)."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from plugin.doc.peer_message import (
    PEER_QUEUE_CAP,
    PEER_TOOL_NAME,
    PeerPendingTurn,
    SendPeerMessage,
    drop_listener_queue,
    enqueue_peer_turn,
    filter_peer_message_schemas,
    format_peer_envelope,
    identity_from_doc,
    is_v1_peer_model,
    kick_pending_peer_starts,
    listener_queue_len,
    reset_peer_queues,
    resolve_peer_target,
    schedule_peer_turn,
    v1_peer_type_label,
)
from plugin.framework.async_drain_guard import drain_owner_scope, reset_sentry_state
from plugin.framework.tool import ToolContext, ToolRegistry


class _Listener:
    """Weakref-capable stand-in for SendButtonListener."""

    def __init__(self):
        self.session = MagicMock()
        self.session.messages = []
        self.appended = []
        self.started = []
        self.sidebar_state = MagicMock()
        self.sidebar_state.send.is_busy = False
        self._active_q = None
        self._send_cancellation = None
        self.chat_mode_selector = None

    def _append_response(self, text, role="assistant"):
        self.appended.append((text, role))

    def start_extracted_peer_send(self, query_text, *, already_appended):
        self.started.append((query_text, already_appended))
        return True


def setup_function():
    reset_peer_queues()
    reset_sentry_state()


def teardown_function():
    reset_peer_queues()
    reset_sentry_state()


def _ctx(caller="chat", doc=None):
    if doc is None:
        doc = MagicMock()
        doc.getURL.return_value = "file:///tmp/self.odt"
        doc.getTitle.return_value = "self.odt"
        doc.getRuntimeUID.return_value = "self-uid"
        doc.RuntimeUID = "self-uid"
        doc.supportsService.side_effect = lambda s: s == "com.sun.star.text.TextDocument"
    return ToolContext(doc=doc, ctx=object(), doc_type="writer", services=None, caller=caller)


def test_peer_message_module_does_not_import_panel_factory():
    src = Path("plugin/doc/peer_message.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert "plugin.chatbot.panel_factory" not in imported
    assert "plugin.chatbot.panel" not in imported
    assert not any(name.endswith("panel_factory") for name in imported)


def test_envelope_from_ctx_doc():
    doc = MagicMock()
    doc.getURL.return_value = "file:///tmp/Budget%202026.ods"
    doc.getTitle.return_value = "Budget 2026.ods"
    doc.getRuntimeUID.return_value = "uid-budget"
    doc.RuntimeUID = "uid-budget"
    with patch("plugin.doc.document_research._system_path_from_url", return_value="/tmp/Budget 2026.ods"):
        ident = identity_from_doc(doc)
    assert ident["name"] == "Budget 2026.ods"
    assert ident["uid"] == "uid-budget"
    assert ident["url"] == "file:///tmp/Budget%202026.ods"
    wrapped = format_peer_envelope(
        name=ident["name"],
        uid=ident["uid"],
        url=ident["url"],
        peer_ask_id="ask-1",
        message="Compute Q4.",
    )
    assert wrapped.startswith("[Peer from: Budget 2026.ods | uid=uid-budget |")
    assert "peer_ask_id=ask-1" in wrapped
    assert wrapped.endswith("Compute Q4.")


def test_envelope_untitled_url_empty():
    doc = MagicMock()
    doc.getURL.return_value = ""
    doc.getTitle.return_value = "Untitled 1"
    doc.getRuntimeUID.return_value = "uid-untitled"
    doc.RuntimeUID = "uid-untitled"
    ident = identity_from_doc(doc)
    assert ident["url"] == ""
    assert ident["uid"] == "uid-untitled"
    assert ident["name"] == "Untitled 1"


def test_impress_rejected_on_model_not_catalog_draw():
    impress = MagicMock()
    impress.supportsService.side_effect = lambda s: s in (
        "com.sun.star.drawing.DrawingDocument",
        "com.sun.star.presentation.PresentationDocument",
    )
    assert is_v1_peer_model(impress) is False
    assert v1_peer_type_label(impress) is None

    draw = MagicMock()
    draw.supportsService.side_effect = lambda s: s == "com.sun.star.drawing.DrawingDocument"
    assert is_v1_peer_model(draw) is True
    assert v1_peer_type_label(draw) == "draw"


def test_visibility_filter_alone_hides_tool():
    schemas = [
        {"type": "function", "function": {"name": PEER_TOOL_NAME, "description": "base"}},
        {"type": "function", "function": {"name": "undo", "description": "u"}},
    ]
    out = filter_peer_message_schemas(schemas, ctx=object(), doc=object())
    names = [s["function"]["name"] for s in out]
    assert PEER_TOOL_NAME not in names
    assert "undo" in names


def test_visibility_filter_two_writer_shows_catalog():
    schemas = [
        {"type": "function", "function": {"name": PEER_TOOL_NAME, "description": "base"}},
    ]
    peers = [{"name": "Other.odt", "uid": "u2", "url": "file:///tmp/Other.odt", "type": "writer"}]
    with patch("plugin.doc.peer_message.list_v1_peers", return_value=peers):
        out = filter_peer_message_schemas(schemas, ctx=object(), doc=object())
    assert len(out) == 1
    desc = out[0]["function"]["description"]
    assert "Other.odt" in desc
    assert "uid=u2" in desc
    assert "type=writer" in desc


def test_addressing_self_rejected():
    self_doc = MagicMock()
    self_doc.getRuntimeUID.return_value = "uid-self"
    self_doc.RuntimeUID = "uid-self"
    peer = MagicMock()
    peer.getRuntimeUID.return_value = "uid-self"
    peer.RuntimeUID = "uid-self"
    peer.supportsService.side_effect = lambda s: s == "com.sun.star.text.TextDocument"
    with patch("plugin.framework.uno_context.resolve_document_by_url", return_value=(peer, "writer")):
        with patch("plugin.framework.uno_context.get_runtime_uid", return_value="uid-self"):
            model, code, _msg = resolve_peer_target(object(), self_doc, "uid-self")
    assert model is None
    assert code == "PEER_SELF"


def test_addressing_missing():
    self_doc = MagicMock()
    with patch("plugin.framework.uno_context.resolve_document_by_url", return_value=(None, None)):
        with patch("plugin.doc.peer_message.list_v1_peers", return_value=[]):
            model, code, _msg = resolve_peer_target(object(), self_doc, "file:///missing.odt")
    assert model is None
    assert code == "PEER_NOT_FOUND"


def test_addressing_ambiguous_name():
    self_doc = MagicMock()
    peers = [
        {"name": "Budget.ods", "uid": "a", "url": "", "type": "calc"},
        {"name": "Budget.ods", "uid": "b", "url": "", "type": "calc"},
    ]
    with patch("plugin.framework.uno_context.resolve_document_by_url", return_value=(None, None)):
        with patch("plugin.doc.peer_message.list_v1_peers", return_value=peers):
            model, code, _msg = resolve_peer_target(object(), self_doc, "Budget.ods")
    assert model is None
    assert code == "PEER_AMBIGUOUS"


def test_addressing_unique_name():
    self_doc = MagicMock()
    self_doc.getRuntimeUID.return_value = "self"
    peer = MagicMock()
    peer.getRuntimeUID.return_value = "peer-uid"
    peer.supportsService.side_effect = lambda s: s == "com.sun.star.sheet.SpreadsheetDocument"
    peers = [{"name": "Budget.ods", "uid": "peer-uid", "url": "", "type": "calc"}]

    def _resolve(_ctx, target):
        if target == "peer-uid":
            return peer, "calc"
        return None, None

    with patch("plugin.framework.uno_context.resolve_document_by_url", side_effect=_resolve):
        with patch("plugin.doc.peer_message.list_v1_peers", return_value=peers):
            with patch("plugin.framework.uno_context.get_runtime_uid", side_effect=lambda m: "self" if m is self_doc else "peer-uid"):
                model, code, _msg = resolve_peer_target(object(), self_doc, "Budget.ods")
    assert code is None
    assert model is peer


def test_queue_fifo_cap_overflow_and_stop_drops():
    listener = _Listener()
    turns = [PeerPendingTurn(f"t{i}", False, f"id{i}") for i in range(PEER_QUEUE_CAP)]
    for turn in turns:
        assert enqueue_peer_turn(listener, turn) is None
    assert listener_queue_len(listener) == PEER_QUEUE_CAP
    overflow = enqueue_peer_turn(listener, PeerPendingTurn("extra", False, "x"))
    assert overflow == "PEER_QUEUE_FULL"
    drop_listener_queue(listener)
    assert listener_queue_len(listener) == 0


def test_schedule_does_not_start_while_drain_owned():
    listener = _Listener()
    turn = PeerPendingTurn("wrapped", True, "ask")
    with drain_owner_scope("stream"):
        err = schedule_peer_turn(listener, turn)
        assert err is None
        assert listener_queue_len(listener) == 1
        assert listener.started == []
    # idle callback may schedule but testing post is deferred; kick explicitly
    kick_pending_peer_starts()
    assert listener.started == [("wrapped", True)]
    assert listener_queue_len(listener) == 0


def test_user_busy_wins_over_queued_inject():
    listener = _Listener()
    listener.sidebar_state.send.is_busy = True
    turn = PeerPendingTurn("wrapped", False, "ask")
    assert schedule_peer_turn(listener, turn) is None
    assert listener.started == []
    assert listener_queue_len(listener) == 1
    listener.sidebar_state.send.is_busy = False
    kick_pending_peer_starts()
    assert listener.started == [("wrapped", False)]


def test_execute_status_ok_accepted():
    tool = SendPeerMessage()
    ctx = _ctx()
    peer = MagicMock()
    listener = _Listener()
    panel = MagicMock()
    panel.send_listener = listener
    with patch("plugin.doc.peer_message.resolve_peer_target", return_value=(peer, None, "")):
        with patch("plugin.framework.uno_context.get_runtime_uid", return_value="peer-uid"):
            with patch("plugin.doc.live_panels.get_live_panel", return_value=panel):
                with drain_owner_scope("stream"):
                    result = tool.execute(ctx, document_url="peer-uid", message="Do the thing")
    assert result["status"] == "ok"
    assert result["accepted"] is True
    assert result["peer_ask_id"]
    assert listener.session.add_user_message.called
    assert listener.appended


def test_execute_refuses_non_chat_caller():
    tool = SendPeerMessage()
    ctx = _ctx(caller="mcp")
    result = tool.execute(ctx, document_url="x", message="hi")
    assert result["status"] == "error"
    assert result["code"] == "PEER_CHAT_ONLY"


def test_execute_missing_sidebar():
    tool = SendPeerMessage()
    ctx = _ctx()
    peer = MagicMock()
    with patch("plugin.doc.peer_message.resolve_peer_target", return_value=(peer, None, "")):
        with patch("plugin.framework.uno_context.get_runtime_uid", return_value="peer-uid"):
            with patch("plugin.doc.live_panels.get_live_panel", return_value=None):
                result = tool.execute(ctx, document_url="peer-uid", message="hi")
    assert result["status"] == "error"
    assert result["code"] == "PEER_SIDEBAR_NOT_OPEN"
    assert "sidebar" in result["message"].lower()


def test_execute_queue_full():
    tool = SendPeerMessage()
    ctx = _ctx()
    peer = MagicMock()
    listener = _Listener()
    panel = MagicMock()
    panel.send_listener = listener
    for i in range(PEER_QUEUE_CAP):
        enqueue_peer_turn(listener, PeerPendingTurn(f"t{i}", False, str(i)))
    with patch("plugin.doc.peer_message.resolve_peer_target", return_value=(peer, None, "")):
        with patch("plugin.framework.uno_context.get_runtime_uid", return_value="peer-uid"):
            with patch("plugin.doc.live_panels.get_live_panel", return_value=panel):
                with drain_owner_scope("stream"):
                    result = tool.execute(ctx, document_url="peer-uid", message="one more")
    assert result["status"] == "error"
    assert result["code"] == "PEER_QUEUE_FULL"


def test_registry_chat_tier_on_default_list():
    registry = ToolRegistry(services=None)
    registry.register(SendPeerMessage())
    names = {t.name for t in registry.get_tools(doc_type="writer")}
    assert PEER_TOOL_NAME in names
    mcp_names = {t.name for t in registry.get_tools(exclude_tiers=frozenset({"specialized", "specialized_control", "chat"}))}
    assert PEER_TOOL_NAME not in mcp_names


def test_is_mutation_false_and_sync():
    tool = SendPeerMessage()
    assert tool.detects_mutation() is False
    assert tool.is_async() is False
    assert tool.tier == "chat"
    assert tool.name == "send_peer_message"


def test_prompts_ready_after_accepted_not_wait():
    from plugin.framework.prompts import PEER_MESSAGING_RULES

    assert "Ready" in PEER_MESSAGING_RULES
    assert "do not wait" in PEER_MESSAGING_RULES.lower()
    assert "don't Ready" not in PEER_MESSAGING_RULES
    assert "do not Ready" not in PEER_MESSAGING_RULES


def test_chat_tier_excluded_from_mcp_frozensets():
    from plugin.mcp.mcp_protocol import MCP_DELEGATE_EXCLUDE_TIERS, MCP_DIRECT_FLAT_EXCLUDE_TIERS

    assert "chat" in MCP_DELEGATE_EXCLUDE_TIERS
    assert "chat" in MCP_DIRECT_FLAT_EXCLUDE_TIERS

"""Unit tests for DrawBridge chat-context helper (no UNO)."""

import pytest
from unittest.mock import MagicMock, patch

from plugin.draw.bridge import get_draw_context_for_chat
from plugin.framework.errors import UnoObjectError


def test_get_draw_context_for_chat_disposed_returns_fallback():
    with patch("plugin.draw.bridge.check_disposed", side_effect=UnoObjectError("gone")):
        out = get_draw_context_for_chat(MagicMock())
    assert "Unable to read Draw/Impress context" in out


def test_get_draw_context_for_chat_summarizes_active_page():
    page = MagicMock()
    pages = MagicMock()
    pages.getCount.return_value = 1
    pages.getByIndex.return_value = page

    shape = MagicMock()
    shape.getShapeType.return_value = "com.sun.star.drawing.TextShape"
    pos = MagicMock(X=10, Y=20)
    size = MagicMock(Width=100, Height=50)
    shape.getPosition.return_value = pos
    shape.getSize.return_value = size
    shape.getString.return_value = "Hello"

    model = MagicMock()
    model.supportsService.return_value = False
    model.getURL.return_value = "file:///tmp/demo.odg"

    bridge = MagicMock()
    bridge.get_pages.return_value = pages
    bridge.get_active_page.return_value = page
    bridge.get_shapes.return_value = [shape]

    with (
        patch("plugin.draw.bridge.check_disposed"),
        patch("plugin.draw.bridge.DrawBridge", return_value=bridge),
        patch("plugin.draw.bridge.safe_call", side_effect=lambda fn, _msg, *args: fn(*args) if args else fn()),
    ):
        out = get_draw_context_for_chat(model, 8000)

    assert "Draw Document" in out
    assert "Total Pages: 1" in out
    assert "Hello" in out


class _FakeDrawPages:
    def __init__(self, n=2):
        self._n = n

    def getCount(self):
        return self._n

    def getByIndex(self, i):
        if i < 0 or i >= self._n:
            raise IndexError(i)
        return object()


def test_draw_bridge_uses_get_draw_pages_when_present():
    from plugin.draw.bridge import DrawBridge

    page_coll = _FakeDrawPages(3)

    class Doc:
        def getDrawPages(self):
            return page_coll

    bridge = DrawBridge(Doc())
    assert bridge.get_pages() is page_coll
    assert bridge.get_pages().getCount() == 3


def test_draw_bridge_writer_single_draw_page():
    from plugin.draw.bridge import DrawBridge

    page = object()

    class WriterDoc:
        def getDrawPage(self):
            return page

    bridge = DrawBridge(WriterDoc())
    pages = bridge.get_pages()
    assert pages.getCount() == 1
    assert pages.getByIndex(0) is page


def test_draw_bridge_calc_active_sheet_draw_page():
    from plugin.draw.bridge import DrawBridge

    page = object()

    class Sheet:
        def getDrawPage(self):
            return page

    class CalcDoc:
        def getSheets(self):
            return MagicMock()

        def getCurrentController(self):
            ctrl = MagicMock()
            ctrl.getActiveSheet.return_value = Sheet()
            return ctrl

    bridge = DrawBridge(CalcDoc())
    assert bridge.get_pages().getCount() == 1
    assert bridge.get_pages().getByIndex(0) is page


def test_draw_bridge_rejects_document_without_draw_page():
    from plugin.draw.bridge import DrawBridge

    class Empty:
        pass

    with pytest.raises(RuntimeError, match="no draw page"):
        DrawBridge(Empty())


def test_get_slide_for_tool_returns_resolved_slide():
    from plugin.draw.bridge import DrawBridge

    slide = object()
    with patch.object(DrawBridge, "resolve_slide", return_value=slide) as resolve:
        out = DrawBridge.get_slide_for_tool("doc", 1)
    assert out is slide
    resolve.assert_called_once_with("doc", 1)


def test_get_slide_for_tool_index_error_is_tool_error():
    from plugin.draw.bridge import DrawBridge
    from plugin.framework.errors import ToolExecutionError

    with patch.object(DrawBridge, "resolve_slide", side_effect=IndexError("Page index 9 out of range.")):
        with pytest.raises(ToolExecutionError, match="Page index 9 out of range"):
            DrawBridge.get_slide_for_tool("doc", 9)


def test_get_slide_for_tool_reraises_disposed():
    from plugin.draw.bridge import DrawBridge

    class DisposedException(Exception):
        pass

    boom = DisposedException("Binary URP bridge disposed during call")
    with patch.object(DrawBridge, "resolve_slide", side_effect=boom):
        with pytest.raises(DisposedException, match="URP"):
            DrawBridge.get_slide_for_tool("doc", 0)


def test_get_active_page_index_matches_via_uno_same():
    from plugin.draw.bridge import DrawBridge

    pages = MagicMock()
    pages.getCount.return_value = 2
    first, second = object(), object()
    pages.getByIndex.side_effect = lambda i: (first, second)[i]

    class Doc:
        def getDrawPages(self):
            return pages

    bridge = DrawBridge(Doc())
    with patch.object(bridge, "get_active_page", return_value=second):
        assert bridge.get_active_page_index() == 1


def test_get_slide_for_tool_wraps_other_errors():
    from plugin.draw.bridge import DrawBridge
    from plugin.framework.errors import ToolExecutionError

    with patch.object(DrawBridge, "resolve_slide", side_effect=RuntimeError("No draw page available.")):
        with pytest.raises(ToolExecutionError, match="No draw page available"):
            DrawBridge.get_slide_for_tool("doc")

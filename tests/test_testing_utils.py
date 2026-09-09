# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2026 KeithCu
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for shared pytest stubs in testing_utils."""

import pytest

from plugin.framework.tool import ToolContext
from plugin.tests.testing_utils import CalcDocStub, MockContext, TestingFactory, WriterDocStub


def test_calc_doc_stub_defaults():
    doc = CalcDocStub()
    assert doc.supportsService("com.sun.star.sheet.SpreadsheetDocument")
    assert not doc.supportsService("com.sun.star.text.TextDocument")
    assert doc.getURL() == "test://calc"
    sheets = doc.getSheets()
    assert sheets.getCount() == 1
    assert sheets.hasByName("Sheet1")
    sheet = sheets.getByName("Sheet1")
    assert sheet.getName() == "Sheet1"
    assert doc.getCurrentController().getActiveSheet() is sheet
    assert doc.CurrentController.ActiveSheet is sheet
    sel = doc.CurrentController.Selection
    addr = sel.getRangeAddress()
    assert (addr.StartColumn, addr.StartRow, addr.EndColumn, addr.EndRow) == (0, 0, 0, 0)


def test_calc_doc_stub_seed_data_and_a1_range():
    doc = CalcDocStub(data=(("hello", 2.5), ("=A1", "")))
    sheet = doc.getSheets().getByIndex(0)
    assert sheet.getCellByPosition(0, 0).getString() == "hello"
    assert sheet.getCellByPosition(1, 0).getValue() == 2.5
    assert sheet.getCellByPosition(0, 1).getFormula() == "=A1"
    b2 = sheet.getCellRangeByName("B2")
    assert b2.getRangeAddress().StartColumn == 1
    assert b2.getRangeAddress().StartRow == 1
    rng = sheet.getCellRangeByName("A1:B1")
    assert rng.getDataArray() == (("hello", 2.5),)


def test_calc_doc_stub_insert_sheet_and_selection_override():
    doc = CalcDocStub(selection="B2")
    sheets = doc.getSheets()
    sheets.insertNewByName("Extra", 1)
    assert sheets.hasByName("Extra")
    assert sheets.getCount() == 2
    assert sheets.getByIndex(1).getName() == "Extra"
    addr = doc.getCurrentController().getSelection().getRangeAddress()
    assert (addr.StartColumn, addr.StartRow) == (1, 1)


def test_testing_factory_create_doc_calc():
    doc = TestingFactory.create_doc(doc_type="calc")
    assert isinstance(doc, CalcDocStub)
    assert doc.supportsService("com.sun.star.sheet.SpreadsheetDocument")
    assert doc.getSheets().hasByName("Sheet1")

    seeded = TestingFactory.create_doc(doc_type="calc", data=(("x",),))
    assert seeded.getSheets().getByIndex(0).getCellByPosition(0, 0).getString() == "x"


def test_calc_sheet_query_content_cells_formulas():
    doc = CalcDocStub(
        data=(
            ('=PY("a")', "plain"),
            ("=SUM(A1)", '=PY("b")'),
        )
    )
    sheet = doc.getSheets().getByName("Sheet1")
    enum = sheet.queryContentCells(16)
    assert enum.getCount() == 1
    rng = enum.getByIndex(0)
    addr = rng.getRangeAddress()
    assert (addr.StartColumn, addr.StartRow, addr.EndColumn, addr.EndRow) == (0, 0, 1, 1)
    formulas = rng.getFormulas()
    assert formulas[0][0] == '=PY("a")'
    assert formulas[1][1] == '=PY("b")'


def test_calc_doc_stub_calculate_all_and_props_listeners():
    doc = CalcDocStub(props={"RuntimeUID": "uid-1"})
    assert doc.getPropertyValue("RuntimeUID") == "uid-1"
    doc.setPropertyValue("RuntimeUID", "uid-2")
    assert doc.getPropertyValue("RuntimeUID") == "uid-2"
    doc.calculateAll()
    doc.calculateAll()
    assert doc.calculate_all_count == 2
    doc.addDocumentEventListener(object())
    assert len(doc._document_event_listeners) == 1


def test_testing_factory_create_doc_writer():
    doc = TestingFactory.create_doc(doc_type="writer")
    assert isinstance(doc, WriterDocStub)
    assert doc.supportsService("com.sun.star.text.TextDocument")
    assert not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument")

    seeded = TestingFactory.create_doc(
        doc_type="writer",
        content=[],
        items={"ParagraphStyles": object()},
    )
    assert isinstance(seeded, WriterDocStub)
    assert seeded.getStyleFamilies().hasByName("ParagraphStyles")
    assert seeded.getStyleFamilies().getElementNames() == ("ParagraphStyles",)


def test_testing_factory_create_context_mock():
    writer_ctx = TestingFactory.create_context(doc_type="writer")
    assert isinstance(writer_ctx, ToolContext)
    assert isinstance(writer_ctx.doc, WriterDocStub)
    assert isinstance(writer_ctx.ctx, MockContext)
    assert writer_ctx.doc_type == "writer"

    calc_ctx = TestingFactory.create_context(doc_type="calc")
    assert isinstance(calc_ctx.doc, CalcDocStub)
    assert calc_ctx.doc_type == "calc"


def test_testing_factory_create_context_native_requires_doc():
    with pytest.raises(ValueError, match="requires doc="):
        TestingFactory.create_context(env="native", doc_type="writer")


def test_with_native_doc_logs_teardown_for_insert_cell_html(capsys):
    """GHA 33703959362: no TEST end after execute-done — name body vs teardown."""
    from unittest.mock import patch

    from plugin.tests.testing_utils import TestingFactory, with_native_doc

    @with_native_doc("calc")
    def test_insert_cell_html(ctx, doc):
        return "ok"

    with patch.object(TestingFactory, "native_doc") as mock_cm:
        mock_cm.return_value.__enter__.return_value = object()
        mock_cm.return_value.__exit__.return_value = None
        assert test_insert_cell_html(ctx=object()) == "ok"
    from plugin.tests import testing_utils as tu

    err = capsys.readouterr().err
    assert "with_native_doc: enter name=test_insert_cell_html doc_type=calc" in err
    assert "with_native_doc: body returned name=test_insert_cell_html; teardown start" in err
    assert "with_native_doc: teardown done name=test_insert_cell_html" in err
    assert tu._LOG_NATIVE_DOC_TEARDOWN is False


def test_with_native_doc_skips_teardown_log_for_other_tests(capsys):
    from unittest.mock import patch

    from plugin.tests.testing_utils import TestingFactory, with_native_doc

    @with_native_doc("calc")
    def test_other(ctx, doc):
        return "ok"

    with patch.object(TestingFactory, "native_doc") as mock_cm:
        mock_cm.return_value.__enter__.return_value = object()
        mock_cm.return_value.__exit__.return_value = None
        assert test_other(ctx=object()) == "ok"
    err = capsys.readouterr().err
    assert "with_native_doc:" not in err


def _calc_doc_for_reset():
    from unittest.mock import MagicMock

    empty = MagicMock()
    empty.getElementNames.return_value = ()
    sheets = MagicMock()
    sheets.getCount.return_value = 1
    sheet = MagicMock()
    sheet.Name = "Sheet1"
    sheet.getCharts.return_value = empty
    sheet.NamedRanges = None
    sheets.getByIndex.return_value = sheet
    doc = MagicMock()
    doc.getSheets.return_value = sheets
    doc.getEmbeddedObjects.return_value = empty
    doc.NamedRanges = None
    doc.DatabaseRanges = None
    return doc


def test_reset_calc_doc_logs_when_teardown_flag_set(capsys):
    from unittest.mock import MagicMock

    from plugin.tests import testing_utils as tu

    tu._LOG_NATIVE_DOC_TEARDOWN = True
    try:
        tu._reset_calc_doc(_calc_doc_for_reset(), MagicMock())
    finally:
        tu._LOG_NATIVE_DOC_TEARDOWN = False
    err = capsys.readouterr().err
    assert "native_doc: _reset_calc_doc start" in err
    assert "native_doc: _reset_calc_doc clearContents start" in err
    assert "native_doc: _reset_calc_doc clearContents done" in err
    assert "udprops probe: RuntimeUID start" in err
    assert "udprops clear: DOCUMENT_SCRIPTS start" in err
    assert "native_doc: _reset_calc_doc done" in err


def test_reset_calc_doc_silent_by_default(capsys):
    from unittest.mock import MagicMock

    from plugin.tests import testing_utils as tu

    tu._reset_calc_doc(_calc_doc_for_reset(), MagicMock())
    err = capsys.readouterr().err
    assert "native_doc:" not in err


def test_clear_writeragent_udprops_skips_set_document_scripts():
    """GHA 33707990007: wipe must not call isReadonly via set_document_scripts."""
    from unittest.mock import MagicMock, patch

    from plugin.scripting.document_scripts import DOCUMENT_SCRIPTS_UDPROP
    from plugin.scripting.session_manager import PYTHON_WORKBOOK_SESSION_PROP
    from plugin.tests import testing_utils as tu

    doc = MagicMock()
    doc.isReadonly = MagicMock(side_effect=AssertionError("isReadonly must not run"))

    with (
        patch("plugin.scripting.document_scripts.set_document_scripts") as set_scripts,
        patch("plugin.doc.udprops.set_document_property") as set_prop,
    ):
        tu._clear_writeragent_udprops(doc)

    set_scripts.assert_not_called()
    doc.isReadonly.assert_not_called()
    written = {call.args[1]: call.args[2] for call in set_prop.call_args_list}
    assert written[DOCUMENT_SCRIPTS_UDPROP] == ""
    assert written[PYTHON_WORKBOOK_SESSION_PROP] == ""
    assert written["WriterAgentSessionID"] == ""


def test_reraise_native_open_failure_names_previous_test(capsys, monkeypatch):
    """Factory-open DisposedException must name the previous TEST end in the message."""
    import plugin.testing_runner as tr
    from plugin.tests.testing_utils import _reraise_native_open_failure

    monkeypatch.setattr(tr, "_soffice_pids", lambda: "7")
    tr.reset_lifecycle_breadcrumb()
    tr.record_test_end("draw.test_draw_uno.test_duplicate_slide_copies_shapes", "OK")
    tr.record_test_start("draw.test_draw_uno.test_duplicate_rename_move_slide")

    with pytest.raises(RuntimeError, match="previous=draw.test_draw_uno.test_duplicate_slide_copies_shapes") as caught:
        try:
            raise RuntimeError("Binary URP bridge disposed during call")
        except RuntimeError as exc:
            _reraise_native_open_failure(exc, "private:factory/sdraw")
    assert "create_native_doc loadComponentFromURL(private:factory/sdraw)" in str(caught.value)
    assert "Binary URP bridge" in str(caught.value)
    err = capsys.readouterr().err
    assert "LIFECYCLE native_doc open FAIL" in err
    assert "previous=draw.test_draw_uno.test_duplicate_slide_copies_shapes" in err
    tr.reset_lifecycle_breadcrumb()


def test_reraise_native_open_failure_passthrough_non_urp():
    from plugin.tests.testing_utils import _reraise_native_open_failure

    with pytest.raises(ValueError, match="not a bridge"):
        try:
            raise ValueError("not a bridge")
        except ValueError as exc:
            _reraise_native_open_failure(exc, "private:factory/sdraw")


def test_create_native_doc_wraps_disposed_exception(monkeypatch):
    from unittest.mock import MagicMock, patch

    import plugin.testing_runner as tr
    from plugin.tests.testing_utils import TestingFactory

    tr.reset_lifecycle_breadcrumb()
    tr.record_test_end("draw.test_draw_uno.test_get_draw_tree", "OK")
    tr.record_test_start("draw.test_draw_uno.test_insert_math_draw")

    desktop = MagicMock()
    desktop.loadComponentFromURL.side_effect = RuntimeError("Binary URP bridge disposed during call")
    with (
        patch("plugin.framework.uno_context.get_desktop", return_value=desktop),
        patch("uno.createUnoStruct", return_value=MagicMock()),
        pytest.raises(RuntimeError, match="previous=draw.test_draw_uno.test_get_draw_tree"),
    ):
        TestingFactory.create_native_doc(object(), "draw")
    tr.reset_lifecycle_breadcrumb()


def test_log_close_doc_failure_and_office_health(capsys, monkeypatch):
    from unittest.mock import MagicMock, patch

    import plugin.testing_runner as tr
    from plugin.tests.testing_utils import _log_close_doc_failure, _log_office_health_after_close

    monkeypatch.setattr(tr, "_soffice_pids", lambda: "-")
    tr.reset_lifecycle_breadcrumb()
    tr.record_test_end("draw.test_draw_uno.test_get_draw_tree", "OK")

    _log_close_doc_failure(RuntimeError("Binary URP bridge disposed during call"))
    err = capsys.readouterr().err
    assert "LIFECYCLE close_doc dispose" in err
    assert "previous=draw.test_draw_uno.test_get_draw_tree" in err

    desktop = MagicMock()
    desktop.getComponents.side_effect = RuntimeError("Binary URP bridge disposed during call")
    with patch("plugin.framework.uno_context.get_desktop", return_value=desktop):
        _log_office_health_after_close(object(), "draw")
    err = capsys.readouterr().err
    assert "LIFECYCLE office dead after close doc_type=draw" in err
    assert "previous=draw.test_draw_uno.test_get_draw_tree" in err
    tr.reset_lifecycle_breadcrumb()


def test_close_doc_logs_urp_dispose(capsys, monkeypatch):
    from unittest.mock import MagicMock

    import plugin.testing_runner as tr
    from plugin.tests.testing_utils import TestingFactory

    monkeypatch.setattr(tr, "_soffice_pids", lambda: "8")
    tr.reset_lifecycle_breadcrumb()
    tr.record_test_start("draw.test_draw_uno.test_get_draw_tree")
    doc = MagicMock()
    doc.close.side_effect = RuntimeError("Binary URP bridge disposed during call")
    TestingFactory.close_doc(doc)
    err = capsys.readouterr().err
    assert "LIFECYCLE close_doc dispose" in err
    tr.reset_lifecycle_breadcrumb()


def test_testing_factory_execute_tool_unknown_name():
    from unittest.mock import MagicMock, patch

    doc = CalcDocStub()
    ctx = MockContext()
    fake_tools = MagicMock()
    fake_tools.execute.side_effect = KeyError("bad_tool")
    with (
        patch("plugin.main.get_tools", return_value=fake_tools),
        patch("plugin.main.get_services", return_value={}),
    ):
        res = TestingFactory.execute_tool(doc, ctx, "bad_tool", {}, doc_type="calc")
    assert res["status"] == "error"
    assert "bad_tool" in res["error"]

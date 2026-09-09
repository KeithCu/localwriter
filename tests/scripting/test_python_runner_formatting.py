# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2026 KeithCu (modifications and relicensing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import unittest
from plugin.scripting.python_runner import format_result_for_writer, format_elapsed_time, is_shape_tool_status_result

class TestPythonRunnerFormatting(unittest.TestCase):
    def test_format_elapsed_time(self):
        # Minutes and seconds
        self.assertEqual(format_elapsed_time(60.0), "1m 0s")
        self.assertEqual(format_elapsed_time(75.3), "1m 15s")
        self.assertEqual(format_elapsed_time(125.9), "2m 5s")
        
        # Seconds and hundreds
        self.assertEqual(format_elapsed_time(1.0), "1.00s")
        self.assertEqual(format_elapsed_time(3.45), "3.45s")
        self.assertEqual(format_elapsed_time(59.999), "60.00s") # boundary case (or minutes)

        # Milliseconds (1-999 ms)
        self.assertEqual(format_elapsed_time(0.999), "999 ms")
        self.assertEqual(format_elapsed_time(0.5), "500 ms")
        self.assertEqual(format_elapsed_time(0.001), "1 ms")

        # Less than 1 millisecond
        self.assertEqual(format_elapsed_time(0.0005), "<1 ms")
        self.assertEqual(format_elapsed_time(0.0), "<1 ms")

    def test_format_string(self):
        self.assertEqual(format_result_for_writer("hello"), "hello")
        self.assertEqual(format_result_for_writer(123), "123")

    def test_format_escapes_html_specials_for_insert_unescape(self):
        # Double-escape so html.unescape in insert_content_at_position still
        # leaves entities the StarWriter filter will render as text.
        self.assertEqual(format_result_for_writer("<b>&</b>"), "&amp;lt;b&amp;gt;&amp;amp;&amp;lt;/b&amp;gt;")
        table = format_result_for_writer([["<td>", "a&b"]])
        self.assertIn("<td>&amp;lt;td&amp;gt;</td>", table)
        self.assertIn("<td>a&amp;amp;b</td>", table)

    def test_format_zero(self):
        self.assertEqual(format_result_for_writer(0), "0")
        self.assertEqual(format_result_for_writer(0.0), "0.0")

    def test_is_shape_tool_status_result(self):
        self.assertTrue(is_shape_tool_status_result({
            "status": "ok",
            "message": "Created star24",
            "index": 0,
            "page": 0,
            "shape_count_after": 1,
            "geometry_applied": True,
        }))
        self.assertTrue(is_shape_tool_status_result({
            "status": "ok",
            "message": "Shape updated",
            "page": 0,
            "index": 1,
            "name": "Box1",
        }))
        self.assertFalse(is_shape_tool_status_result({"title": "Hello", "summary": "world"}))
        self.assertFalse(is_shape_tool_status_result("Created star24"))
        self.assertFalse(is_shape_tool_status_result(None))


    def test_format_list_of_lists(self):
        data = [["A", "B"], [1, 2]]
        expected = '<table border="1"><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>'
        self.assertEqual(format_result_for_writer(data), expected)

    def test_format_list_of_dicts(self):
        data = [{"Name": "Alice", "Age": 30}, {"Name": "Bob", "Age": 25}]
        expected = '<table border="1"><thead><tr><th>Name</th><th>Age</th></tr></thead><tbody><tr><td>Alice</td><td>30</td></tr><tr><td>Bob</td><td>25</td></tr></tbody></table>'
        self.assertEqual(format_result_for_writer(data), expected)

    def test_format_complex_dict_order(self):
        # We now respect insertion order strictly.
        data = {
            "title": "My Title",
            "data": [{"A": 1}],
            "total": 100,
            "summary_text": "Finish"
        }
        res = format_result_for_writer(data)
        
        # Order should be: title, data, total, summary_text
        title_idx = res.find("My Title")
        data_idx = res.find("data")
        total_idx = res.find("total")
        summary_idx = res.find("Finish")
        
        self.assertLess(title_idx, data_idx)
        self.assertLess(data_idx, total_idx)
        self.assertLess(total_idx, summary_idx)
        
        # Priority keys (title, summary_text) should NOT have labels
        # but SHOULD be bold
        self.assertIn("<p><b>My Title</b></p>", res)
        self.assertIn("<p><b>Finish</b></p>", res)
        self.assertNotIn("<b>title:</b>", res)
        self.assertNotIn("<b>summary_text:</b>", res)
        # Non-priority keys SHOULD have labels
        self.assertIn("<b>total:</b>", res)

    def test_format_priority_keys_non_string(self):
        data = {
            "title": 12345,
            "summary": 99.9,
            "message": True,
            "result": {"nested": "value"}
        }
        res = format_result_for_writer(data)
        self.assertIn("<p><b>12345</b></p>", res)
        self.assertIn("<p><b>99.9</b></p>", res)
        self.assertIn("<p><b>True</b></p>", res)
        self.assertIn("<p><b>{&amp;#x27;nested&amp;#x27;: &amp;#x27;value&amp;#x27;}</b></p>", res)
        self.assertNotIn("<b>title:</b>", res)
        self.assertNotIn("<b>summary:</b>", res)
        self.assertNotIn("<b>message:</b>", res)
        self.assertNotIn("<b>result:</b>", res)

    def test_empty_or_none(self):
        self.assertEqual(format_result_for_writer(None), "")
        self.assertEqual(format_result_for_writer([]), "")
        self.assertEqual(format_result_for_writer(""), "")


def _calc_doc_with_selection(start_col: int = 0, start_row: int = 0):
    from unittest.mock import MagicMock

    addr = MagicMock()
    addr.StartColumn = start_col
    addr.StartRow = start_row
    selection = MagicMock()
    selection.getRangeAddress.return_value = addr
    controller = MagicMock()
    controller.getSelection.return_value = selection
    doc = MagicMock()
    doc.getCurrentController.return_value = controller
    return doc


def test_insert_result_into_calc_primitive():
    from unittest.mock import MagicMock, patch

    from plugin.scripting.python_runner import insert_result_into_calc

    doc = _calc_doc_with_selection(0, 0)
    ctx = MagicMock()
    with patch("plugin.calc.rich_html.insert_cell_html_rich") as mock_rich:
        insert_result_into_calc(doc, ctx, 42)
    mock_rich.assert_called_once_with(doc, ctx, "A1", "42")


def test_insert_result_into_calc_list_at_selection():
    from unittest.mock import MagicMock, patch

    from plugin.scripting.python_runner import insert_result_into_calc

    doc = _calc_doc_with_selection(1, 2)
    ctx = MagicMock()
    rows = [["a", "b"], [1, 2]]
    with patch("plugin.calc.rich_html.insert_cell_html_rich") as mock_rich:
        insert_result_into_calc(doc, ctx, rows)
    mock_rich.assert_called_once()
    assert mock_rich.call_args[0][2] == "B3"
    assert '<table border="1">' in mock_rich.call_args[0][3]


def test_insert_result_into_calc_dict_title_and_table():
    from unittest.mock import MagicMock, patch

    from plugin.scripting.python_runner import insert_result_into_calc

    doc = _calc_doc_with_selection(0, 0)
    ctx = MagicMock()
    result = {"title": "My Title", "rows": [{"A": 1, "B": 2}]}
    with patch("plugin.calc.rich_html.insert_cell_html_rich") as mock_rich:
        insert_result_into_calc(doc, ctx, result)
    mock_rich.assert_called_once()
    assert mock_rich.call_args[0][2] == "A1"
    html_arg = mock_rich.call_args[0][3]
    assert "My Title" in html_arg
    assert '<table border="1">' in html_arg


def test_insert_result_into_calc_dataframe_envelope():
    from unittest.mock import MagicMock, patch

    from plugin.scripting.payload_codec import PAYLOAD_DATAFRAME
    from plugin.scripting.python_runner import insert_result_into_calc

    doc = _calc_doc_with_selection(0, 0)
    ctx = MagicMock()
    envelope = {"__wa_payload__": PAYLOAD_DATAFRAME, "columns": ["a"], "data": [[1]]}
    with patch("plugin.calc.rich_html.insert_cell_html_rich") as mock_rich:
        insert_result_into_calc(doc, ctx, envelope)
    mock_rich.assert_called_once()
    assert mock_rich.call_args[0][2] == "A1"
    html_arg = mock_rich.call_args[0][3]
    assert "<th>a</th>" in html_arg
    assert "<td>1</td>" in html_arg


def test_insert_result_into_calc_exception_shows_msgbox():
    from unittest.mock import MagicMock, patch

    from plugin.scripting.python_runner import insert_result_into_calc

    doc = MagicMock()
    doc.getCurrentController.side_effect = RuntimeError("no controller")
    with patch("plugin.scripting.python_runner.msgbox") as box:
        insert_result_into_calc(doc, MagicMock(), 1)
    box.assert_called_once()
    assert "Failed to insert result into Calc" in box.call_args[0][2]



def test_insert_result_into_calc_skips_shape_status_dict():
    from unittest.mock import MagicMock, patch
    from plugin.scripting.python_runner import insert_result_into_calc

    doc = MagicMock()
    with patch("plugin.calc.rich_html.insert_cell_html_rich") as rich:
        insert_result_into_calc(
            doc,
            MagicMock(),
            {
                "status": "ok",
                "message": "Created star24",
                "index": 0,
                "page": 0,
                "shape_count_after": 1,
                "geometry_applied": True,
            },
        )
    rich.assert_not_called()

if __name__ == "__main__":
    unittest.main()

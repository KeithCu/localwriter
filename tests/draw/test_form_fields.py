# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2026 KeithCu
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for paper-form helpers (no live soffice)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from plugin.draw.form_fields import (
    FillDrawFields,
    annotate_paper_form_nodes,
    apply_control_value,
    apply_shape_field_value,
    find_shape_on_page,
    is_near_empty_text,
    is_paper_form_text_type,
    parse_control_state,
    resolve_fill_field,
    snapshot_control,
)


def test_near_empty_text_detects_placeholders():
    assert is_near_empty_text(None)
    assert is_near_empty_text("")
    assert is_near_empty_text("   ")
    assert is_near_empty_text("___")
    assert is_near_empty_text("...")
    assert is_near_empty_text("— —")
    assert not is_near_empty_text("Patient name")
    assert not is_near_empty_text("X")


def test_paper_form_type_excludes_lines_and_controls():
    assert is_paper_form_text_type("TextShape")
    assert is_paper_form_text_type("com.sun.star.drawing.RectangleShape")
    assert not is_paper_form_text_type("ConnectorShape")
    assert not is_paper_form_text_type("com.sun.star.drawing.ControlShape")
    assert not is_paper_form_text_type("GraphicObjectShape")


def test_annotate_marks_textshape_blank_and_left_label():
    nodes = [
        {
            "type": "TextShape",
            "index": 0,
            "text": "Name:",
            "geometry": {"x": 0, "y": 100, "width": 2000, "height": 800},
        },
        {
            "type": "TextShape",
            "index": 1,
            "geometry": {"x": 2200, "y": 100, "width": 4000, "height": 800},
        },
    ]
    annotate_paper_form_nodes(nodes)
    assert nodes[1]["blank"] is True
    assert nodes[1]["fillable"] is True
    assert nodes[1]["label_hint"] == "Name:"
    assert "fillable" not in nodes[0]


def test_annotate_empty_rectangle_fillable_only_with_neighbor():
    lonely = [{"type": "RectangleShape", "index": 0, "geometry": {"x": 0, "y": 0, "width": 1000, "height": 1000}}]
    annotate_paper_form_nodes(lonely)
    assert lonely[0].get("blank") is True
    assert "fillable" not in lonely[0]

    pair = [
        {
            "type": "TextShape",
            "index": 0,
            "text": "Date",
            "geometry": {"x": 0, "y": 0, "width": 1500, "height": 400},
        },
        {
            "type": "RectangleShape",
            "index": 1,
            "geometry": {"x": 0, "y": 500, "width": 1500, "height": 400},
        },
    ]
    annotate_paper_form_nodes(pair)
    assert pair[1]["fillable"] is True
    assert pair[1]["label_hint"] == "Date"


def test_parse_and_apply_checkbox_state():
    assert parse_control_state(True) == 1
    assert parse_control_state("yes") == 1
    assert parse_control_state("off") == 0
    assert parse_control_state("maybe") is None

    class _Box:
        def __init__(self):
            self.State = 0

        def supportsService(self, service):
            return service.endswith("CheckBox")

    model = _Box()
    out = apply_control_value(model, "checked")
    assert out["status"] == "ok"
    assert out["state"] == 1
    assert model.State == 1


def test_snapshot_control_includes_state_not_empty_checkbox_text():
    class _Box:
        Name = "Agree"
        Label = "I agree"
        State = 1
        Text = ""

        def supportsService(self, service):
            return service.endswith("CheckBox")

    snap = snapshot_control(_Box())
    assert snap["type"] == "checkbox"
    assert snap["name"] == "Agree"
    assert snap["state"] == 1
    assert "text" not in snap


def test_find_shape_on_page_prefers_name():
    class _Shape:
        def __init__(self, name, shape_type="com.sun.star.drawing.TextShape"):
            self.Name = name
            self._type = shape_type

        def getShapeType(self):
            return self._type

    shapes = [_Shape(" deco "), _Shape("PatientName")]
    page = MagicMock()
    page.getCount.return_value = 2
    page.getByIndex.side_effect = lambda i: shapes[i]

    found = find_shape_on_page(page, name="patientname")
    assert found is not None
    assert found[1] == 1
    assert found[0].Name == "PatientName"


def test_resolve_fill_field_miss_and_label_hint():
    class _Shape:
        def __init__(self, name, text, x, y, w, h, shape_type="com.sun.star.drawing.TextShape"):
            self.Name = name
            self._text = text
            self._type = shape_type
            self._pos = type("P", (), {"X": x, "Y": y})()
            self._size = type("S", (), {"Width": w, "Height": h})()

        def getShapeType(self):
            return self._type

        def getString(self):
            return self._text

        def setString(self, value):
            self._text = value

        def getPosition(self):
            return self._pos

        def getSize(self):
            return self._size

    label = _Shape("lbl", "Lot number", 0, 0, 2000, 600)
    blank = _Shape("LotField", "", 2200, 0, 3000, 600)
    page = MagicMock()
    page.getCount.return_value = 2
    page.getByIndex.side_effect = lambda i: (label, blank)[i]

    hit = resolve_fill_field(page, {"label_hint": "Lot number"})
    assert not isinstance(hit, str)
    assert hit[0] is blank

    miss = resolve_fill_field(page, {"name": "NoSuchField"})
    assert miss.startswith("No shape matching")


def test_apply_shape_field_value_setstring():
    class _Shape:
        def __init__(self):
            self._text = ""

        def getShapeType(self):
            return "com.sun.star.drawing.TextShape"

        def setString(self, value):
            self._text = value

    shape = _Shape()
    out = apply_shape_field_value(shape, "ABC-1")
    assert out["status"] == "ok"
    assert shape._text == "ABC-1"


def test_fill_draw_fields_happy_and_miss():
    class _Shape:
        def __init__(self, name):
            self.Name = name
            self._text = ""

        def getShapeType(self):
            return "com.sun.star.drawing.TextShape"

        def setString(self, value):
            self._text = value

        def getPosition(self):
            return type("P", (), {"X": 0, "Y": 0})()

        def getSize(self):
            return type("S", (), {"Width": 100, "Height": 100})()

        def getString(self):
            return self._text

    shapes = [_Shape("FieldA")]
    page = MagicMock()
    page.getCount.return_value = 1
    page.getByIndex.side_effect = lambda i: shapes[i]

    ctx = MagicMock()
    with patch("plugin.draw.shapes._resolve_shape_page", return_value=(page, 0, None)):
        result = FillDrawFields().execute(
            ctx,
            fields=[
                {"name": "FieldA", "value": "filled"},
                {"name": "Missing", "value": "nope"},
            ],
        )
    assert result["status"] == "partial"
    assert result["filled"] == 1
    assert result["failed"] == 1
    assert shapes[0]._text == "filled"
    assert result["results"][0]["status"] == "ok"
    assert result["results"][1]["status"] == "error"


def test_shape_upsert_validate_accepts_name_without_index():
    from plugin.draw.shapes import UpsertShape

    ok, err = UpsertShape().validate(action="edit", name="PatientName", text="Ada")
    assert ok
    assert err is None
    ok, err = UpsertShape().validate(action="edit")
    assert not ok
    assert "index" in err and "name" in err

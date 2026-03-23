import pytest
from unittest.mock import MagicMock

from plugin.modules.calc.manipulator import CellManipulator
from plugin.modules.calc.__init__ import CalcError

import sys
sys.modules['com.sun.star.table'] = MagicMock()


@pytest.fixture
def mock_bridge():
    return MagicMock()


@pytest.fixture
def manipulator(mock_bridge):
    return CellManipulator(mock_bridge)


def test_safe_get_cell_value_sheet_none(manipulator):
    with pytest.raises(CalcError) as exc_info:
        manipulator.safe_get_cell_value(None, "A1")
    assert exc_info.value.code == "CALC_SHEET_NULL"
    assert "Sheet is None" in exc_info.value.message


def test_safe_get_cell_value_invalid_address(manipulator):
    sheet = MagicMock()
    with pytest.raises(CalcError) as exc_info:
        manipulator.safe_get_cell_value(sheet, "1A")
    assert exc_info.value.code == "CALC_INVALID_ADDRESS"
    assert "Invalid cell address" in exc_info.value.message


def test_safe_get_cell_value_cell_not_found(manipulator):
    sheet = MagicMock()
    sheet.getCellRangeByName.side_effect = Exception("Not found")
    with pytest.raises(CalcError) as exc_info:
        manipulator.safe_get_cell_value(sheet, "A1")
    assert exc_info.value.code == "CALC_CELL_NOT_FOUND"


def test_safe_get_cell_value_empty(manipulator):
    from com.sun.star.table import CellContentType as CCT
    sheet = MagicMock()
    cell = MagicMock()
    cell.getType.return_value = CCT.EMPTY
    sheet.getCellRangeByName.return_value = cell

    assert manipulator.safe_get_cell_value(sheet, "A1") is None


def test_safe_get_cell_value_value(manipulator):
    from com.sun.star.table import CellContentType as CCT
    sheet = MagicMock()
    cell = MagicMock()
    cell.getType.return_value = CCT.VALUE
    cell.getValue.return_value = 42.0
    sheet.getCellRangeByName.return_value = cell

    assert manipulator.safe_get_cell_value(sheet, "A1") == 42.0


def test_safe_get_cell_value_text(manipulator):
    from com.sun.star.table import CellContentType as CCT
    sheet = MagicMock()
    cell = MagicMock()
    cell.getType.return_value = CCT.TEXT
    cell.getString.return_value = "Hello"
    sheet.getCellRangeByName.return_value = cell

    assert manipulator.safe_get_cell_value(sheet, "A1") == "Hello"


def test_safe_get_cell_value_formula_success(manipulator):
    from com.sun.star.table import CellContentType as CCT
    sheet = MagicMock()
    cell = MagicMock()
    cell.getType.return_value = CCT.FORMULA
    cell.getError.return_value = 0
    cell.getValue.return_value = 100.0
    sheet.getCellRangeByName.return_value = cell

    assert manipulator.safe_get_cell_value(sheet, "A1") == 100.0


def test_safe_get_cell_value_formula_error(manipulator):
    from com.sun.star.table import CellContentType as CCT
    sheet = MagicMock()
    cell = MagicMock()
    cell.getType.return_value = CCT.FORMULA
    cell.getError.return_value = 503  # #NUM!
    sheet.getCellRangeByName.return_value = cell

    with pytest.raises(CalcError) as exc_info:
        manipulator.safe_get_cell_value(sheet, "A1")
    assert exc_info.value.code == "CALC_FORMULA_ERROR"
    assert "Formula error in A1: #NUM!" in exc_info.value.message
    assert exc_info.value.details["error_code"] == 503
    assert exc_info.value.details["error_name"] == "#NUM!"


def test_safe_get_cell_value_unknown_type(manipulator):
    sheet = MagicMock()
    cell = MagicMock()
    cell.getType.return_value = 999  # Unknown
    sheet.getCellRangeByName.return_value = cell

    with pytest.raises(CalcError) as exc_info:
        manipulator.safe_get_cell_value(sheet, "A1")
    assert exc_info.value.code == "CALC_UNKNOWN_CELL_TYPE"


def test_safe_get_cell_value_unexpected_error(manipulator):
    sheet = MagicMock()
    cell = MagicMock()
    cell.getType.side_effect = RuntimeError("Something bad happened")
    sheet.getCellRangeByName.return_value = cell

    with pytest.raises(CalcError) as exc_info:
        manipulator.safe_get_cell_value(sheet, "A1")
    assert exc_info.value.code == "CALC_CELL_VALUE_ERROR"
    assert "Failed to get cell value" in exc_info.value.message
from plugin.modules.draw.shapes import DrawShapes, DrawError

def test_draw_shapes_safe_create_shape_valid():
    """Test safe_create_shape with valid inputs creates and adds the shape."""
    draw_shapes = DrawShapes()

    doc = MagicMock()
    page = MagicMock()
    shape = MagicMock()
    doc.createInstance.return_value = shape

    position = MagicMock()
    position.X = 100
    position.Y = 200

    size = MagicMock()
    size.Width = 300
    size.Height = 400

    shape_type = "RectangleShape"

    result = draw_shapes.safe_create_shape(doc, page, shape_type, position, size)

    doc.createInstance.assert_called_once_with("com.sun.star.drawing.RectangleShape")
    shape.setPosition.assert_called_once_with(position)
    shape.setSize.assert_called_once_with(size)
    page.add.assert_called_once_with(shape)

    assert result == shape

def test_draw_shapes_safe_create_shape_invalid_page():
    """Test safe_create_shape raises DrawError when page is None."""
    draw_shapes = DrawShapes()
    doc = MagicMock()

    position = MagicMock()
    position.X = 100
    position.Y = 200

    size = MagicMock()
    size.Width = 300
    size.Height = 400

    with pytest.raises(DrawError) as exc_info:
        draw_shapes.safe_create_shape(doc, None, "RectangleShape", position, size)

    assert exc_info.value.code == "DRAW_PAGE_NULL"

def test_draw_shapes_safe_create_shape_invalid_position():
    """Test safe_create_shape raises DrawError when position is invalid."""
    draw_shapes = DrawShapes()

    doc = MagicMock()
    page = MagicMock()

    # Missing X/Y
    position = MagicMock()
    del position.X

    size = MagicMock()
    size.Width = 300
    size.Height = 400

    with pytest.raises(DrawError) as exc_info:
        draw_shapes.safe_create_shape(doc, page, "RectangleShape", position, size)

    assert exc_info.value.code == "DRAW_INVALID_POSITION"

def test_draw_shapes_safe_create_shape_invalid_size():
    """Test safe_create_shape raises DrawError when size is invalid."""
    draw_shapes = DrawShapes()

    doc = MagicMock()
    page = MagicMock()

    position = MagicMock()
    position.X = 100
    position.Y = 200

    # Missing Width/Height
    size = MagicMock()
    size.Width = 0 # Invalid
    size.Height = 400

    with pytest.raises(DrawError) as exc_info:
        draw_shapes.safe_create_shape(doc, page, "RectangleShape", position, size)

    assert exc_info.value.code == "DRAW_INVALID_SIZE"

def test_draw_shapes_safe_create_shape_creation_failed():
    """Test safe_create_shape raises DrawError when shape creation fails."""
    draw_shapes = DrawShapes()

    doc = MagicMock()
    doc.createInstance.return_value = None
    page = MagicMock()

    position = MagicMock()
    position.X = 100
    position.Y = 200

    size = MagicMock()
    size.Width = 300
    size.Height = 400

    with pytest.raises(DrawError) as exc_info:
        draw_shapes.safe_create_shape(doc, page, "UnknownShape", position, size)

    assert exc_info.value.code == "DRAW_SHAPE_CREATION_FAILED"

def test_draw_shapes_safe_create_shape_exception_handling():
    """Test safe_create_shape wraps generic exceptions in DrawError."""
    draw_shapes = DrawShapes()

    doc = MagicMock()
    doc.createInstance.side_effect = Exception("Some UNO error")
    page = MagicMock()

    position = MagicMock()
    position.X = 100
    position.Y = 200

    size = MagicMock()
    size.Width = 300
    size.Height = 400

    with pytest.raises(DrawError) as exc_info:
        draw_shapes.safe_create_shape(doc, page, "RectangleShape", position, size)

    assert exc_info.value.code == "DRAW_SHAPE_CREATION_ERROR"
    assert "Some UNO error" in exc_info.value.details["original_error"]

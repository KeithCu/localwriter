"""Cell inspector - Reads detailed information of LibreOffice Calc cells.

Ported from core/calc_inspector.py for the plugin framework.
"""

import logging
import re
from plugin.modules.calc.address_utils import parse_address

try:
    from com.sun.star.table.CellContentType import EMPTY, VALUE, TEXT, FORMULA
    UNO_AVAILABLE = True
except ImportError:
    EMPTY, VALUE, TEXT, FORMULA = 0, 1, 2, 3
    UNO_AVAILABLE = False

logger = logging.getLogger("localwriter.calc")


class CellInspector:
    """Class that examines cell contents and properties."""

    def __init__(self, bridge):
        """
        CellInspector initializer.

        Args:
            bridge: CalcBridge instance.
        """
        self.bridge = bridge

    @staticmethod
    def _cell_type_name(cell_type) -> str:
        """Returns UNO Enum compatible cell type name."""
        if cell_type == EMPTY:
            return "empty"
        if cell_type == VALUE:
            return "value"
        if cell_type == TEXT:
            return "text"
        if cell_type == FORMULA:
            return "formula"
        return "unknown"

    @staticmethod
    def _safe_prop(cell, name, default=None):
        try:
            return cell.getPropertyValue(name)
        except Exception:
            return default

    def _get_cell(self, address: str):
        """
        Returns the cell object according to the address.

        Args:
            address: Cell address (e.g. "A1").

        Returns:
            Cell object.
        """
        col, row = parse_address(address)
        sheet = self.bridge.get_active_sheet()
        return self.bridge.get_cell(sheet, col, row)

    def read_cell(self, address: str) -> dict:
        """
        Reads basic cell information.

        Args:
            address: Cell address (e.g. "A1").

        Returns:
            Dictionary containing cell information:
            - address: Cell address
            - value: Cell value
            - formula: Formula (if any)
            - type: Cell type (empty, value, text, formula)
        """
        try:
            cell = self._get_cell(address)
            cell_type = cell.getType()

            if cell_type == EMPTY:
                value = None
            elif cell_type == VALUE:
                value = cell.getValue()
            elif cell_type == TEXT:
                value = cell.getString()
            elif cell_type == FORMULA:
                value = cell.getValue() if cell.getValue() != 0 else cell.getString()
            else:
                value = cell.getString()

            formula = cell.getFormula() if cell_type == FORMULA else None

            return {
                "address": address.upper(),
                "value": value,
                "formula": formula,
                "type": self._cell_type_name(cell_type),
            }
        except Exception as e:
            logger.error("Cell reading error (%s): %s", address, str(e))
            raise

    def get_cell_details(self, address: str) -> dict:
        """
        Returns all detailed cell information.

        Args:
            address: Cell address (e.g. "A1").

        Returns:
            Detailed cell info dictionary:
            - address: Cell address
            - value: Cell value
            - formula: Formula
            - formula_local: Local formula
            - type: Cell type
            - background_color: Background color (int)
            - number_format: Number format
        """
        try:
            cell = self._get_cell(address)
            cell_type = cell.getType()

            if cell_type == EMPTY:
                value = None
            elif cell_type == VALUE:
                value = cell.getValue()
            elif cell_type == TEXT:
                value = cell.getString()
            elif cell_type == FORMULA:
                value = cell.getValue() if cell.getValue() != 0 else cell.getString()
            else:
                value = cell.getString()

            return {
                "address": address.upper(),
                "value": value,
                "formula": cell.getFormula(),
                "formula_local": self._safe_prop(cell, "FormulaLocal"),
                "type": self._cell_type_name(cell_type),
                "background_color": self._safe_prop(cell, "CellBackColor"),
                "number_format": self._safe_prop(cell, "NumberFormat"),
                "font_color": self._safe_prop(cell, "CharColor"),
                "font_size": self._safe_prop(cell, "CharHeight"),
                "bold": self._safe_prop(cell, "CharWeight"),
                "italic": self._safe_prop(cell, "CharPosture"),
                "h_align": self._safe_prop(cell, "HoriJustify"),
                "v_align": self._safe_prop(cell, "VertJustify"),
                "wrap_text": self._safe_prop(cell, "IsTextWrapped"),
            }
        except Exception as e:
            logger.error("Cell detailed reading error (%s): %s", address, str(e))
            raise

    def read_range(self, range_name: str) -> list[list[dict]]:
        """
        Reads values and formulas in a cell range.

        Args:
            range_name: Cell range (e.g. "A1:D10", "B2").

        Returns:
            2D list: dict containing {address, value, formula, type} for each cell.
        """
        try:
            sheet = self.bridge.get_active_sheet()

            # Check if it's a single cell
            if ":" not in range_name:
                cell_info = self.read_cell(range_name)
                return [[cell_info]]

            cell_range = self.bridge.get_cell_range(sheet, range_name)
            addr = cell_range.getRangeAddress()

            result = []
            for row in range(addr.StartRow, addr.EndRow + 1):
                row_data = []
                for col in range(addr.StartColumn, addr.EndColumn + 1):
                    cell = sheet.getCellByPosition(col, row)
                    cell_type = cell.getType()

                    if cell_type == EMPTY:
                        value = None
                    elif cell_type == VALUE:
                        value = cell.getValue()
                    elif cell_type == TEXT:
                        value = cell.getString()
                    elif cell_type == FORMULA:
                        value = cell.getValue() if cell.getValue() != 0 else cell.getString()
                    else:
                        value = cell.getString()

                    col_letter = self.bridge._index_to_column(col)
                    address = f"{col_letter}{row + 1}"
                    formula = cell.getFormula() if cell_type == FORMULA else None

                    row_data.append({
                        "address": address,
                        "value": value,
                        "formula": formula,
                        "type": self._cell_type_name(cell_type),
                    })
                result.append(row_data)

            return result
        except Exception as e:
            logger.error("Range reading error (%s): %s", range_name, str(e))
            raise

    def get_all_formulas(self, sheet_name: str = None) -> list[dict]:
        """
        Lists all formulas in the sheet.

        Args:
            sheet_name: Sheet name (active sheet if None).

        Returns:
            Formula list: [{address, formula, value, precedents}, ...]
        """
        try:
            if sheet_name:
                doc = self.bridge.get_active_document()
                sheets = doc.getSheets()
                sheet = sheets.getByName(sheet_name)
            else:
                sheet = self.bridge.get_active_sheet()

            # Find used area
            cursor = sheet.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)

            addr = cursor.getRangeAddress()
            formulas = []

            for row in range(addr.StartRow, addr.EndRow + 1):
                for col in range(addr.StartColumn, addr.EndColumn + 1):
                    cell = sheet.getCellByPosition(col, row)
                    if cell.getType() == FORMULA:
                        col_letter = self.bridge._index_to_column(col)
                        address = f"{col_letter}{row + 1}"
                        formula = cell.getFormula()
                        value = cell.getValue() if cell.getValue() != 0 else cell.getString()

                        # Find referenced cells
                        refs = re.findall(r'\$?([A-Z]+)\$?(\d+)', formula.upper())
                        precedents = list(set([f"{c}{r}" for c, r in refs]))

                        formulas.append({
                            "address": address,
                            "formula": formula,
                            "value": value,
                            "precedents": precedents,
                        })

            return formulas
        except Exception as e:
            logger.error("Formula listing error: %s", str(e))
            raise

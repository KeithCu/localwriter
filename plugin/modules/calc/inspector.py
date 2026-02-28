"""Cell inspector - Reads detailed information of LibreOffice Calc cells."""

import logging
import re
from plugin.modules.calc.address_utils import parse_address

try:
    from com.sun.star.table.CellContentType import EMPTY, VALUE, TEXT, FORMULA
    UNO_AVAILABLE = True
except ImportError:
    EMPTY, VALUE, TEXT, FORMULA = 0, 1, 2, 3
    UNO_AVAILABLE = False

logger = logging.getLogger(__name__)


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

    def get_cell_precedents(self, address: str) -> list:
        """
        Returns cells that the cell depends on (precedents).

        Finds other cells referenced in the formula.

        Args:
            address: Cell address (e.g. "B2").

        Returns:
            List of precedent cell addresses.
        """
        try:
            cell = self._get_cell(address)
            formula = cell.getFormula()

            if not formula:
                return []

            # Find cell references in the formula
            references = re.findall(
                r'\$?([A-Z]+)\$?(\d+)', formula.upper()
            )

            precedents = []
            for col_str, row_str in references:
                ref_address = f"{col_str}{row_str}"
                if ref_address not in precedents:
                    precedents.append(ref_address)

            return precedents

        except Exception as e:
            logger.error(
                "Precedent cell detection error (%s): %s", address, str(e)
            )
            raise

    def get_cell_dependents(self, address: str) -> list:
        """
        Returns cells that depend on this cell (dependents).

        Scans formulas in the used area of the active sheet to find
        cells referencing this cell.

        Args:
            address: Cell address (e.g. "A1").

        Returns:
            List of dependent cell addresses.
        """
        try:
            sheet = self.bridge.get_active_sheet()
            target = address.strip().upper()

            # Determine the used area of the sheet
            cursor = sheet.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)

            addr = cursor.getRangeAddress()
            end_col = addr.EndColumn
            end_row = addr.EndRow

            dependents = []

            # More efficient search: try to find the row/col strings
            col_target = re.match(r'^([A-Z]+)', target).group(1)
            row_target = re.match(r'^[A-Z]+(\d+)$', target).group(1)
            # Pattern matches common A1 references with or without $
            pattern = rf'\$?{re.escape(col_target)}\$?{re.escape(row_target)}(?![0-9A-Z])'

            for row in range(addr.StartRow, end_row + 1):
                for col in range(addr.StartColumn, end_col + 1):
                    cell = sheet.getCellByPosition(col, row)
                    if cell.getType() == FORMULA:
                        formula = cell.getFormula().upper()
                        if re.search(pattern, formula):
                            dep_col = self.bridge._index_to_column(col)
                            dep_address = f"{dep_col}{row + 1}"
                            dependents.append(dep_address)

            return dependents

        except Exception as e:
            logger.error(
                "Dependent cell detection error (%s): %s", address, str(e)
            )
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

    def analyze_spreadsheet_structure(self, sheet_name: str = None) -> dict:
        """
        Analyzes table structure and formula network.

        Args:
            sheet_name: Sheet name (active sheet if None).

        Returns:
            Structure analysis: {
                input_cells: Cells where data is entered (without formulas),
                output_cells: Result cells (with formulas but not used by another formula),
                intermediate_cells: Intermediate calculation cells,
                formula_chain: Formula chain (dependency order),
            }
        """
        try:
            formulas = self.get_all_formulas(sheet_name)

            if not formulas:
                return {
                    "input_cells": [],
                    "output_cells": [],
                    "intermediate_cells": [],
                    "formula_chain": [],
                    "summary": "No formulas found on this sheet."
                }

            # Collect all formula cells and their references
            formula_cells = {f["address"] for f in formulas}
            all_precedents = set()
            for f in formulas:
                all_precedents.update(f["precedents"])

            # Input cells: Cells referenced by formulas but that don't contains formulas themselves
            input_cells = list(all_precedents - formula_cells)

            # Output cells: Contain formulas but are not referenced by any other formula
            referenced_formulas = set()
            for f in formulas:
                for p in f["precedents"]:
                    if p in formula_cells:
                        referenced_formulas.add(p)

            output_cells = [f["address"] for f in formulas if f["address"] not in referenced_formulas]

            # Intermediate cells
            intermediate_cells = list(formula_cells - set(output_cells))

            # Create formula chain
            formula_chain = []
            for f in formulas:
                formula_chain.append({
                    "cell": f["address"],
                    "formula": f["formula"],
                    "depends_on": f["precedents"],
                })

            return {
                "input_cells": sorted(input_cells),
                "output_cells": sorted(output_cells),
                "intermediate_cells": sorted(intermediate_cells),
                "formula_chain": formula_chain,
                "summary": f"Analysis: {len(input_cells)} input, {len(intermediate_cells)} intermediate, {len(output_cells)} output cells."
            }

        except Exception as e:
            logger.error("Structure analysis error: %s", str(e))
            raise

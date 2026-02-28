"""In-process UNO bridge for Calc."""

import uno
from plugin.modules.calc.address_utils import index_to_column, column_to_index, parse_range_string

class CalcBridge:
    def __init__(self, doc):
        self.doc = doc

    def get_active_document(self):
        return self.doc

    def get_active_sheet(self):
        doc = self.get_active_document()
        # Spreadsheet documents support XSpreadsheetDocument
        if not hasattr(doc, "getSheets"):
             raise RuntimeError("Active document is not a spreadsheet.")
        
        controller = doc.getCurrentController()
        if hasattr(controller, "getActiveSheet"):
            sheet = controller.getActiveSheet()
        else:
            # Fallback for situations where ActiveSheet is not directly available
            sheets = doc.getSheets()
            sheet = sheets.getByIndex(0)
            
        if sheet is None:
            raise RuntimeError("No active sheet found.")
        return sheet

    def get_cell(self, sheet, col: int, row: int):
        return sheet.getCellByPosition(col, row)

    def get_cell_range(self, sheet, range_str: str):
        start, end = parse_range_string(range_str)
        return sheet.getCellRangeByPosition(start[0], start[1], end[0], end[1])

    @staticmethod
    def _index_to_column(index: int) -> str:
        return index_to_column(index)

    @staticmethod
    def _column_to_index(col_str: str) -> int:
        return column_to_index(col_str)

    @staticmethod
    def parse_range_string(range_str: str):
        return parse_range_string(range_str)

"""Sheet analyzer - Analyzes the structure and statistics of LibreOffice Calc sheets."""

import logging
import math
import re

try:
    from com.sun.star.table.CellContentType import EMPTY, VALUE, TEXT, FORMULA
    UNO_AVAILABLE = True
except ImportError:
    EMPTY, VALUE, TEXT, FORMULA = 0, 1, 2, 3
    UNO_AVAILABLE = False

logger = logging.getLogger(__name__)


class SheetAnalyzer:
    """Class that analyzes the structure and data of a worksheet."""

    def __init__(self, bridge):
        """
        SheetAnalyzer initializer.

        Args:
            bridge: CalcBridge instance.
        """
        self.bridge = bridge

    def get_sheet_summary(self, sheet_name=None) -> dict:
        """
        Returns a general summary of the active sheet or specified sheet.

        Args:
            sheet_name: Optional name of the sheet to analyze.

        Returns:
            Sheet summary info dictionary:
            - sheet_name: Sheet name
            - used_range: Used range (e.g. "A1:F100")
            - row_count: Number of used rows
            - col_count: Number of used columns
            - headers: List of headers in the first row
        """
        try:
            if sheet_name:
                doc = self.bridge.get_active_document()
                sheet = doc.getSheets().getByName(sheet_name)
            else:
                sheet = self.bridge.get_active_sheet()
            
            cursor = sheet.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)

            range_addr = cursor.getRangeAddress()
            start_col = range_addr.StartColumn
            start_row = range_addr.StartRow
            end_col = range_addr.EndColumn
            end_row = range_addr.EndRow

            row_count = end_row - start_row + 1
            col_count = end_col - start_col + 1

            start_col_str = self.bridge._index_to_column(start_col)
            end_col_str = self.bridge._index_to_column(end_col)
            used_range = f"{start_col_str}{start_row + 1}:{end_col_str}{end_row + 1}"

            # Read headers in the first row
            headers = []
            for col in range(start_col, end_col + 1):
                cell = sheet.getCellByPosition(col, start_row)
                cell_value = cell.getString()
                headers.append(cell_value if cell_value else None)

            return {
                "sheet_name": sheet.getName(),
                "used_range": used_range,
                "row_count": row_count,
                "col_count": col_count,
                "headers": headers,
            }

        except Exception as e:
            logger.error("Error creating sheet summary: %s", str(e))
            raise

    def detect_data_regions(self) -> list:
        """
        Detects data regions in the sheet.

        Finds data blocks separated by empty rows or columns.

        Returns:
            List of data regions. Each region is a dictionary:
            - range: Region range (e.g. "A1:D10")
            - row_count: Number of rows
            - col_count: Number of columns
        """
        try:
            sheet = self.bridge.get_active_sheet()
            cursor = sheet.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)

            range_addr = cursor.getRangeAddress()
            end_col = range_addr.EndColumn
            end_row = range_addr.EndRow

            # Check occupancy by row
            row_empty = []
            for row in range(end_row + 1):
                is_empty = True
                for col in range(end_col + 1):
                    cell = sheet.getCellByPosition(col, row)
                    if cell.getType() != EMPTY:
                        is_empty = False
                        break
                row_empty.append(is_empty)

            # Separate regions according to empty rows
            regions = []
            region_start = None

            for row in range(len(row_empty)):
                if not row_empty[row]:
                    if region_start is None:
                        region_start = row
                elif region_start is not None:
                    # End of region - find column boundaries for this region
                    region = self._find_region_bounds(
                        sheet, region_start, row - 1, end_col
                    )
                    if region:
                        regions.append(region)
                    region_start = None

            # Last region
            if region_start is not None:
                region = self._find_region_bounds(
                    sheet, region_start, end_row, end_col
                )
                if region:
                    regions.append(region)

            return regions

        except Exception as e:
            logger.error("Data region detection error: %s", str(e))
            raise

    def _find_region_bounds(
        self, sheet, start_row: int, end_row: int, max_col: int
    ) -> dict:
        """
        Determines the column boundaries of a data region.

        Args:
            sheet: Worksheet.
            start_row: Start row.
            end_row: End row.
            max_col: Maximum column index.

        Returns:
            Region info dictionary or None.
        """
        min_col = max_col
        actual_max_col = 0

        for row in range(start_row, end_row + 1):
            for col in range(max_col + 1):
                cell = sheet.getCellByPosition(col, row)
                if cell.getType() != EMPTY:
                    min_col = min(min_col, col)
                    actual_max_col = max(actual_max_col, col)

        if actual_max_col < min_col:
            return None

        start_col_str = self.bridge._index_to_column(min_col)
        end_col_str = self.bridge._index_to_column(actual_max_col)

        return {
            "range": f"{start_col_str}{start_row + 1}:{end_col_str}{end_row + 1}",
            "row_count": end_row - start_row + 1,
            "col_count": actual_max_col - min_col + 1,
        }

    def find_empty_cells(self, range_str: str) -> list:
        """
        Finds empty cells in the specified range.

        Args:
            range_str: Cell range (e.g. "A1:D10").

        Returns:
            List of empty cell addresses.
        """
        try:
            sheet = self.bridge.get_active_sheet()
            start, end = self.bridge.parse_range_string(range_str)

            empty_cells = []
            for row in range(start[1], end[1] + 1):
                for col in range(start[0], end[0] + 1):
                    cell = sheet.getCellByPosition(col, row)
                    if cell.getType() == EMPTY:
                        col_str = self.bridge._index_to_column(col)
                        empty_cells.append(f"{col_str}{row + 1}")

            return empty_cells

        except Exception as e:
            logger.error(
                "Empty cell search error (%s): %s", range_str, str(e)
            )
            raise

    def get_column_statistics(self, col_letter: str) -> dict:
        """
        Calculates statistics of numeric data in a column.

        Args:
            col_letter: Column letter (e.g. "A", "B").

        Returns:
            Statistics dictionary:
            - column: Column letter
            - count: Number of numeric values
            - sum: Sum
            - mean: Mean
            - min: Minimum
            - max: Maximum
            - std: Standard deviation
        """
        try:
            sheet = self.bridge.get_active_sheet()
            col_index = self.bridge._column_to_index(col_letter.upper())

            cursor = sheet.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)
            end_row = cursor.getRangeAddress().EndRow

            values = []
            for row in range(end_row + 1):
                cell = sheet.getCellByPosition(col_index, row)
                cell_type = cell.getType()
                if cell_type == VALUE:
                    values.append(cell.getValue())
                elif cell_type == FORMULA:
                     # For formulas, we can try to get the current value
                    try:
                        val = cell.getValue()
                        # Often Calc returns 0 for non-numeric formulas, but we want to exclude errors if possible
                        values.append(val)
                    except Exception:
                        pass

            if not values:
                return {
                    "column": col_letter.upper(),
                    "count": 0,
                    "sum": 0,
                    "mean": 0,
                    "min": None,
                    "max": None,
                    "std": 0,
                }

            count = len(values)
            total = sum(values)
            mean = total / count
            min_val = min(values)
            max_val = max(values)

            # Standard deviation calculation
            if count > 1:
                variance = sum((x - mean) ** 2 for x in values) / (count - 1)
                std = math.sqrt(variance)
            else:
                std = 0.0

            return {
                "column": col_letter.upper(),
                "count": count,
                "sum": round(total, 6),
                "mean": round(mean, 6),
                "min": min_val,
                "max": max_val,
                "std": round(std, 6),
            }

        except Exception as e:
            logger.error(
                "Column statistics error (%s): %s", col_letter, str(e)
            )
            raise

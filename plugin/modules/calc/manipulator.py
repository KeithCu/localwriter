"""Cell manipulator - Writing data and formatting LibreOffice Calc cells."""

import json
import logging
from plugin.modules.calc.address_utils import parse_address
from plugin.framework.logging import debug_log

logger = logging.getLogger(__name__)


def _parse_formula_or_values_string(s: str):
    """
    Parse formula_or_values when it arrives as a JSON string (e.g. from the AI tool call)
    or as a raw semicolon-separated string.

    Workaround: The AI often sends formula_or_values as a JSON-encoded string (e.g.
    '["Name"; "Category"; "Value"]') or as a raw string 'Name;Category;Value'.
    Without this, write_formula_range would write that whole string as one value per cell.
    We normalize LibreOffice-style semicolon separators and return a flat list.

    Returns:
        A flat list of values, or None if s should be treated as a single literal value.
    """
    if not isinstance(s, str):
        return None

    s_strip = s.strip()
    if not s_strip:
        return None

    import re
    import json

    # Case 1: JSON array e.g. ["a"; "b"] or ["a", "b"]
    if s_strip.startswith("["):
        try:
            # Formula-safe replacement: only replace semicolons NOT inside double quotes.
            # Manual character-by-character scan to correctly handle escaped quotes.
            normalized_list = []
            in_quotes = False
            escaped = False
            for char in s_strip:
                if char == '"' and not escaped:
                    in_quotes = not in_quotes
                
                if char == ';' and not in_quotes:
                    normalized_list.append(',')
                else:
                    normalized_list.append(char)
                
                if char == '\\' and not escaped:
                    escaped = True
                else:
                    escaped = False
            
            normalized = "".join(normalized_list)
            data = json.loads(normalized)
            if isinstance(data, list):
                flat = []
                for item in data:
                    if isinstance(item, list):
                        flat.extend(item)
                    else:
                        flat.append(item)
                return flat
        except (json.JSONDecodeError, TypeError):
            pass

    # Case 2: Raw semicolon-separated string e.g. "Name;Age;Country"
    # But ONLY if it's not a formula (starting with =) and not a single value
    if ";" in s and not s_strip.startswith("="):
        import csv
        import io
        # Use csv.reader with semicolon delimiter to safely handle quoted values
        # containing semicolons or other special characters.
        try:
            # Add skipinitialspace=True so that a space after a semicolon (common in LLM output)
            # doesn't prevent detection of the quote as the start of a field.
            reader = csv.reader(io.StringIO(s), delimiter=";", skipinitialspace=True)
            rows = list(reader)
            if rows:
                # Flatten the first row (ai usually sends 1 row of headers/data)
                return [val.strip() for val in rows[0]]
        except:
            pass

    return None


class CellManipulator:
    """Class that manages data writing and style application to cells."""

    def __init__(self, bridge):
        """
        CellManipulator initializer.

        Args:
            bridge: CalcBridge instance.
        """
        self.bridge = bridge

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

    def write_value(self, address: str, value):
        """
        Writes a value to the cell.

        Args:
            address: Cell address (e.g. "A1").
            value: Value to write (str or numeric).
        """
        try:
            cell = self._get_cell(address)

            if isinstance(value, (int, float)):
                cell.setValue(value)
            else:
                cell.setString(str(value))

            logger.info("Cell %s <- %r written.", address.upper(), value)

        except Exception as e:
            logger.error("Cell writing error (%s): %s", address, str(e))
            raise

    def write_formula(self, address: str, formula: str):
        """
        Writes formula, text, or number to the cell.

        If it starts with '=', it's written as a formula. If it can be converted to 
        a number, it's written as a number. Otherwise, it's written as text.

        Args:
            address: Cell address (e.g. "A1").
            formula: Content to write (e.g. "=SUM(A1:A10)", "Header", "42").

        Returns:
            Description of the written value.
        """
        try:
            cell = self._get_cell(address)

            if formula.startswith("="):
                # Write as formula
                cell.setFormula(formula)
                logger.info("Cell %s <- formula '%s' written.", address.upper(), formula)
                return f"Formula written to cell {address}: {formula}"
            else:
                # Check if it's a number or text
                try:
                    num = float(formula)
                    cell.setValue(num)
                    logger.info("Cell %s <- number %s written.", address.upper(), formula)
                    return f"Number written to cell {address}: {formula}"
                except ValueError:
                    cell.setString(formula)
                    logger.info("Cell %s <- text '%s' written.", address.upper(), formula)
                    return f"Text written to cell {address}: {formula}"

        except Exception as e:
            logger.error(
                "Formula writing error (%s): %s", address, str(e)
            )
            raise

    def set_cell_style(
        self,
        address_or_range: str,
        bold: bool = None,
        italic: bool = None,
        bg_color: int = None,
        font_color: int = None,
        font_size: float = None,
        h_align: str = None,
        v_align: str = None,
        wrap_text: bool = None,
        border_color: int = None,
        number_format: str = None,
    ):
        """
        Applies style to a cell or range. Handles number format for both.

        Args:
            address_or_range: Cell address or range (e.g. "A1" or "A1:D10").
            bold: Bold (True/False/None).
            italic: Italic (True/False/None).
            bg_color: Background color (RGB int).
            font_color: Font color (RGB int).
            font_size: Font size (points).
            h_align: Horizontal alignment ("left", "center", "right", "justify").
            v_align: Vertical alignment ("top", "center", "bottom").
            wrap_text: Wrap text (True/False).
            border_color: Border color (RGB int).
            number_format: Number format string (e.g. "#,##0.00").
        """
        try:
            if ":" in address_or_range:
                # Range handling
                self.set_range_style(
                    address_or_range,
                    bold=bold,
                    italic=italic,
                    bg_color=bg_color,
                    font_color=font_color,
                    font_size=font_size,
                    h_align=h_align,
                    v_align=v_align,
                    wrap_text=wrap_text,
                    border_color=border_color,
                )
                if number_format:
                    self.set_range_number_format(address_or_range, number_format)
                logger.info("Range %s style updated.", address_or_range.upper())
            else:
                # Single cell handling
                cell = self._get_cell(address_or_range)
                self._apply_style_properties(
                    cell, bold, italic, bg_color, font_color, font_size,
                    h_align, v_align, wrap_text, border_color
                )
                if number_format:
                    self.set_number_format(address_or_range, number_format)
                logger.info("Cell %s style updated.", address_or_range.upper())
        except Exception as e:
            logger.error("Style application error (%s): %s", address_or_range, str(e))
            raise

    def set_range_style(
        self,
        range_str: str,
        bold: bool = None,
        italic: bool = None,
        bg_color: int = None,
        font_color: int = None,
        font_size: float = None,
        h_align: str = None,
        v_align: str = None,
        wrap_text: bool = None,
        border_color: int = None,
    ):
        """
        Applies style to a cell range.

        Args:
            range_str: Cell range (e.g. "A1:D10").
            bold: Bold.
            italic: Italic.
            bg_color: Background color.
            font_color: Font color.
            font_size: Font size.
            h_align: Horizontal alignment ("left", "center", "right", "justify").
            v_align: Vertical alignment ("top", "center", "bottom").
            wrap_text: Wrap text (True/False).
            border_color: Border color (RGB int).
        """
        try:
            sheet = self.bridge.get_active_sheet()
            cell_range = self.bridge.get_cell_range(sheet, range_str)
            self._apply_style_properties(
                cell_range, bold, italic, bg_color, font_color, font_size,
                h_align, v_align, wrap_text, border_color
            )
            logger.info("Range %s style updated.", range_str.upper())
        except Exception as e:
            logger.error("Range style application error (%s): %s", range_str, str(e))
            raise

    def set_range_number_format(self, range_str: str, format_str: str):
        """
        Sets number format for a cell range.

        Args:
            range_str: Cell range (e.g. "A1:D10").
            format_str: Number format string (e.g. "#,##0.00", "0%", "dd.MM.yyyy").
        """
        try:
            sheet = self.bridge.get_active_sheet()
            start, end = self.bridge.parse_range_string(range_str)
            doc = self.bridge.get_active_document()
            formats = doc.getNumberFormats()
            locale = doc.getPropertyValue("CharLocale")
            format_id = formats.queryKey(format_str, locale, False)
            if format_id == -1:
                format_id = formats.addNew(format_str, locale)
            # Apply to each cell in range
            for row in range(start[1], end[1] + 1):
                for col in range(start[0], end[0] + 1):
                    cell = sheet.getCellByPosition(col, row)
                    cell.setPropertyValue("NumberFormat", format_id)
            logger.info("Range %s number format set to '%s'.", range_str.upper(), format_str)
        except Exception as e:
            logger.error("Range number format error (%s): %s", range_str, str(e))
            raise


    def set_number_format(self, address: str, format_str: str):
        """
        Sets the number format of the cell.

        Args:
            address: Cell address (e.g. "A1").
            format_str: Number format string (e.g. "#,##0.00", "0%", "dd.MM.yyyy").
        """
        try:
            cell = self._get_cell(address)
            doc = self.bridge.get_active_document()
            formats = doc.getNumberFormats()
            locale = doc.getPropertyValue("CharLocale")

            format_id = formats.queryKey(format_str, locale, False)
            if format_id == -1:
                format_id = formats.addNew(format_str, locale)

            cell.setPropertyValue("NumberFormat", format_id)
            logger.info(
                "Cell %s number format set to '%s'.",
                address.upper(), format_str,
            )

        except Exception as e:
            logger.error(
                "Number format setting error (%s): %s", address, str(e)
            )
            raise

    def clear_cell(self, address: str):
        """
        Clears cell content.

        Args:
            address: Cell address (e.g. "A1").
        """
        try:
            cell = self._get_cell(address)
            cell.setString("")
            logger.info("Cell %s cleared.", address.upper())

        except Exception as e:
            logger.error("Cell clear error (%s): %s", address, str(e))
            raise

    def clear_range(self, range_str: str):
        """
        Clears all content in the cell range.

        Args:
            range_str: Cell range (e.g. "A1:D10").
        """
        try:
            sheet = self.bridge.get_active_sheet()
            cell_range = self.bridge.get_cell_range(sheet, range_str)
            # CellFlags: VALUE=1, DATETIME=2, STRING=4, ANNOTATION=8,
            # FORMULA=16, HARDATTR=32, STYLES=64
            # 1+2+4+16 = 23 -> clears values, dates, text, and formulas
            cell_range.clearContents(23)
            logger.info("Range %s cleared.", range_str.upper())

        except Exception as e:
            logger.error(
                "Range clear error (%s): %s", range_str, str(e)
            )
            raise

    def _apply_style_properties(
        self, obj, bold, italic, bg_color, font_color, font_size,
        h_align, v_align, wrap_text, border_color
    ):
        """Applies common style properties (for cell or range)."""
        if bold is not None:
            from com.sun.star.awt.FontWeight import BOLD, NORMAL
            obj.setPropertyValue("CharWeight", BOLD if bold else NORMAL)

        if italic is not None:
            from com.sun.star.awt.FontSlant import ITALIC, NONE
            obj.setPropertyValue("CharPosture", ITALIC if italic else NONE)

        if bg_color is not None:
            obj.setPropertyValue("CellBackColor", bg_color)

        if font_color is not None:
            obj.setPropertyValue("CharColor", font_color)

        if font_size is not None:
            obj.setPropertyValue("CharHeight", font_size)

        if h_align is not None:
            from com.sun.star.table.CellHoriJustify import (
                LEFT, CENTER, RIGHT, BLOCK, STANDARD
            )
            align_map = {
                "left": LEFT, "center": CENTER, "right": RIGHT,
                "justify": BLOCK, "standard": STANDARD
            }
            if h_align.lower() in align_map:
                obj.setPropertyValue("HoriJustify", align_map[h_align.lower()])

        if v_align is not None:
            from com.sun.star.table.CellVertJustify import (
                TOP, CENTER, BOTTOM, STANDARD
            )
            align_map = {
                "top": TOP, "center": CENTER, "bottom": BOTTOM,
                "standard": STANDARD
            }
            if v_align.lower() in align_map:
                obj.setPropertyValue("VertJustify", align_map[v_align.lower()])

        if wrap_text is not None:
            obj.setPropertyValue("IsTextWrapped", wrap_text)

        if border_color is not None:
             self._apply_borders(obj, border_color)

    def _apply_borders(self, obj, color: int):
        """Applies borders."""
        from com.sun.star.table import BorderLine
        
        line = BorderLine()
        line.Color = color
        line.OuterLineWidth = 50 # 1/100 mm. So 50 is 0.5 mm.

        # Apply to all sides
        obj.setPropertyValue("TopBorder", line)
        obj.setPropertyValue("BottomBorder", line)
        obj.setPropertyValue("LeftBorder", line)
        obj.setPropertyValue("RightBorder", line)

    def merge_cells(self, range_str: str, center: bool = True):
        """
        Merges cell range.

        Args:
            range_str: Cell range to merge (e.g. "A1:D1").
            center: Center content (True/False).
        """
        try:
            sheet = self.bridge.get_active_sheet()
            cell_range = self.bridge.get_cell_range(sheet, range_str)

            # Use XMergeable interface to merge
            cell_range.merge(True)
            logger.info("Range %s merged.", range_str.upper())

            if center:
                from com.sun.star.table.CellHoriJustify import CENTER
                from com.sun.star.table.CellVertJustify import CENTER as V_CENTER

                cell_range.setPropertyValue("HoriJustify", CENTER)
                cell_range.setPropertyValue("VertJustify", V_CENTER)

        except Exception as e:
            logger.error(
                "Cell merge error (%s): %s", range_str, str(e)
            )
            raise

    def set_column_width(self, col_letter: str, width_mm: float):
        """
        Sets column width.

        Args:
            col_letter: Column letter (e.g. "A", "B").
            width_mm: Width (in millimeters).
        """
        try:
            sheet = self.bridge.get_active_sheet()
            columns = sheet.getColumns()
            col_index = self.bridge._column_to_index(col_letter.upper())

            column = columns.getByIndex(col_index)
            # Width is in 1/100 mm
            column.setPropertyValue("Width", int(width_mm * 100))

            logger.info("Column %s width set to %s mm.", col_letter.upper(), width_mm)
            return f"Column {col_letter.upper()} width set to {width_mm} mm."

        except Exception as e:
            logger.error("Column width error (%s): %s", col_letter, str(e))
            raise

    def set_row_height(self, row_num: int, height_mm: float):
        """
        Sets row height.

        Args:
            row_num: Row number (1-based).
            height_mm: Height (in millimeters).
        """
        try:
            sheet = self.bridge.get_active_sheet()
            rows = sheet.getRows()
            row_index = row_num - 1

            row = rows.getByIndex(row_index)
            # Height is in 1/100 mm
            row.setPropertyValue("Height", int(height_mm * 100))

            logger.info("Row %d height set to %s mm.", row_num, height_mm)
            return f"Row {row_num} height set to {height_mm} mm."

        except Exception as e:
            logger.error("Row height error (%d): %s", row_num, str(e))
            raise

    def insert_rows(self, row_num: int, count: int = 1):
        """
        Inserts new rows at the specified position.

        Args:
            row_num: Row number where insertion occurs (1-based).
            count: Number of rows to insert.
        """
        try:
            sheet = self.bridge.get_active_sheet()
            rows = sheet.getRows()
            row_index = row_num - 1

            rows.insertByIndex(row_index, count)

            logger.info("%d row(s) inserted at row %d.", count, row_num)
            return f"{count} row(s) inserted at row {row_num}."

        except Exception as e:
            logger.error("Row insertion error: %s", str(e))
            raise

    def insert_columns(self, col_letter: str, count: int = 1):
        """
        Inserts new columns at the specified position.

        Args:
            col_letter: Column letter where insertion occurs.
            count: Number of columns to insert.
        """
        try:
            sheet = self.bridge.get_active_sheet()
            columns = sheet.getColumns()
            col_index = self.bridge._column_to_index(col_letter.upper())

            columns.insertByIndex(col_index, count)

            logger.info("%d column(s) inserted at column %s.", count, col_letter.upper())
            return f"{count} column(s) inserted at column {col_letter.upper()}."

        except Exception as e:
            logger.error("Column insertion error: %s", str(e))
            raise

    def delete_rows(self, row_num: int, count: int = 1):
        """
        Deletes specified rows.

        Args:
            row_num: First row number to delete (1-based).
            count: Number of rows to delete.
        """
        try:
            sheet = self.bridge.get_active_sheet()
            rows = sheet.getRows()
            row_index = row_num - 1

            rows.removeByIndex(row_index, count)

            logger.info("%d row(s) deleted starting from row %d.", count, row_num)
            return f"{count} row(s) deleted starting from row {row_num}."

        except Exception as e:
            logger.error("Row deletion error: %s", str(e))
            raise

    def delete_columns(self, col_letter: str, count: int = 1):
        """
        Deletes specified columns.

        Args:
            col_letter: First column letter to delete.
            count: Number of columns to delete.
        """
        try:
            sheet = self.bridge.get_active_sheet()
            columns = sheet.getColumns()
            col_index = self.bridge._column_to_index(col_letter.upper())

            columns.removeByIndex(col_index, count)

            logger.info("%d column(s) deleted starting from column %s.", count, col_letter.upper())
            return f"{count} column(s) deleted starting from column {col_letter.upper()}."

        except Exception as e:
            logger.error("Column deletion error: %s", str(e))
            raise

    def delete_structure(self, structure_type: str, start, count: int = 1):
        """
        Deletes rows or columns.

        Args:
            structure_type: "rows" or "columns".
            start: For rows, row number (1-based); for columns, column letter.
            count: Number to delete.
        """
        if structure_type == "rows":
            return self.delete_rows(start, count)
        elif structure_type == "columns":
            return self.delete_columns(start, count)
        else:
            raise ValueError(f"Invalid structure_type: {structure_type}. Must be 'rows' or 'columns'.")

    def auto_fit_column(self, col_letter: str):
        """
        Automatically adjusts column width to fit content.

        Args:
            col_letter: Column letter.
        """
        try:
            sheet = self.bridge.get_active_sheet()
            columns = sheet.getColumns()
            col_index = self.bridge._column_to_index(col_letter.upper())

            column = columns.getByIndex(col_index)
            column.setPropertyValue("OptimalWidth", True)

            logger.info("Column %s width automatically adjusted.", col_letter.upper())
            return f"Column {col_letter.upper()} width adjusted to fit content."

        except Exception as e:
            logger.error("Auto column width error (%s): %s", col_letter, str(e))
            raise

    def list_sheets(self):
        """
        Lists all sheet names in the workbook.

        Returns:
            List of sheet names.
        """
        try:
            doc = self.bridge.get_active_document()
            sheets = doc.getSheets()
            sheet_names = []
            for i in range(sheets.getCount()):
                sheet = sheets.getByIndex(i)
                sheet_names.append(sheet.getName())
            logger.info("Sheets listed: %s", sheet_names)
            return sheet_names
        except Exception as e:
            logger.error("Sheet listing error: %s", str(e))
            raise

    def switch_sheet(self, sheet_name: str):
        """
        Switches to the specified sheet.

        Args:
            sheet_name: Name of the sheet to switch to.
        """
        try:
            doc = self.bridge.get_active_document()
            sheets = doc.getSheets()

            if not sheets.hasByName(sheet_name):
                raise ValueError(f"No sheet found named '{sheet_name}'.")

            sheet = sheets.getByName(sheet_name)
            controller = doc.getCurrentController()
            controller.setActiveSheet(sheet)

            logger.info("Switched to sheet: %s", sheet_name)
            return f"Switched to sheet '{sheet_name}'."

        except Exception as e:
            logger.error("Sheet switch error (%s): %s", sheet_name, str(e))
            raise

    def create_sheet(self, sheet_name: str, position: int = None):
        """
        Creates a new sheet.

        Args:
            sheet_name: New sheet name.
            position: Sheet position (0-based). If not specified, appended to the end.
        """
        try:
            doc = self.bridge.get_active_document()
            sheets = doc.getSheets()

            if position is None:
                position = sheets.getCount()

            sheets.insertNewByName(sheet_name, position)

            logger.info("New sheet created: %s (position: %d)", sheet_name, position)
            return f"New sheet named '{sheet_name}' created."

        except Exception as e:
            logger.error("Sheet creation error (%s): %s", sheet_name, str(e))
            raise

    def rename_sheet(self, old_name: str, new_name: str):
        """
        Renames a sheet.

        Args:
            old_name: Current sheet name.
            new_name: New sheet name.
        """
        try:
            doc = self.bridge.get_active_document()
            sheets = doc.getSheets()

            if not sheets.hasByName(old_name):
                raise ValueError(f"No sheet found named '{old_name}'.")

            sheet = sheets.getByName(old_name)
            sheet.setName(new_name)

            logger.info("Sheet renamed: %s -> %s", old_name, new_name)
            return f"Sheet renamed from '{old_name}' to '{new_name}'."

        except Exception as e:
            logger.error("Sheet rename error: %s", str(e))
            raise

    def copy_range(self, source_range: str, target_cell: str):
        """
        Copies a cell range to another location.

        Args:
            source_range: Source range (e.g. A1:C10).
            target_cell: Target start cell (e.g. E1).
        """
        try:
            sheet = self.bridge.get_active_sheet()
            source = self.bridge.get_cell_range(sheet, source_range)
            target = self._get_cell(target_cell)

            source_address = source.getRangeAddress()
            target_address = target.getCellAddress()

            sheet.copyRange(target_address, source_address)

            logger.info("Range copied: %s -> %s", source_range.upper(), target_cell.upper())
            return f"Range {source_range} copied to position {target_cell}."

        except Exception as e:
            logger.error("Copy error: %s", str(e))
            raise

    def sort_range(self, range_str: str, sort_column: int = 0, ascending: bool = True, has_header: bool = True):
        """
        Sorts the specified range.

        Args:
            range_str: Range to sort (e.g. A1:D10).
            sort_column: Column to sort by (0-based, position within range).
            ascending: Ascending sort (True) or descending (False).
            has_header: Is the first row a header?
        """
        try:
            sheet = self.bridge.get_active_sheet()
            cell_range = self.bridge.get_cell_range(sheet, range_str)

            import uno
            from com.sun.star.table import TableSortField

            # Use createSortDescriptor for robust property defaults
            sort_desc = list(cell_range.createSortDescriptor())

            # Configure the sort field
            sort_field = TableSortField()
            sort_field.Field = sort_column
            sort_field.IsAscending = ascending
            sort_field.IsCaseSensitive = False
            
            # Update specific properties in the descriptor
            for p in sort_desc:
                if p.Name == "SortFields":
                    p.Value = (sort_field,)
                elif p.Name == "ContainsHeader":
                    p.Value = has_header

            # Sort the range
            cell_range.sort(tuple(sort_desc))

            direction = "ascending" if ascending else "descending"
            logger.info("Range %s sorted %s by column %d.", range_str.upper(), direction, sort_column)
            return f"Range {range_str} sorted {direction} by column {sort_column}."

        except Exception as e:
            logger.error("Sort error (%s): %s", range_str, str(e))
            raise

    def set_auto_filter(self, range_str: str, enable: bool = True):
        """
        Applies or removes auto filter to a data range.

        Args:
            range_str: Range to apply filter to (e.g. A1:D10).
            enable: Enable filter (True) or disable (False).
        """
        try:
            sheet = self.bridge.get_active_sheet()
            cell_range = self.bridge.get_cell_range(sheet, range_str)

            db_ranges = self.bridge.get_active_document().getPropertyValue("DatabaseRanges")
            range_name = f"AutoFilter_{range_str.replace(':', '_')}"

            if enable:
                range_address = cell_range.getRangeAddress()
                if not db_ranges.hasByName(range_name):
                    db_ranges.addNewByName(range_name, range_address)

                db_range = db_ranges.getByName(range_name)
                db_range.setAutoFilter(True)
                db_range.refresh()

                logger.info("AutoFilter applied: %s", range_str.upper())
                return f"AutoFilter applied to range {range_str}."
            else:
                if db_ranges.hasByName(range_name):
                    db_ranges.removeByName(range_name)
                logger.info("AutoFilter removed: %s", range_str.upper())
                return f"AutoFilter removed from range {range_str}."

        except Exception as e:
            logger.error("AutoFilter error (%s): %s", range_str, str(e))
            raise

    def write_formula_range(self, range_str: str, formula_or_values):
        """
        Writes formula(s) or value(s) to a cell range efficiently.

        Args:
            range_str: Cell range (e.g. "A1:A10", "B2:D2").
            formula_or_values: Either a single formula/value for all cells, or a list/array of formulas/values for each cell.

        Returns:
            Summary of the operation.
        """
        try:
            sheet = self.bridge.get_active_sheet()
            start, end = self.bridge.parse_range_string(range_str)

            # Calculate range dimensions
            num_rows = end[1] - start[1] + 1
            num_cols = end[0] - start[0] + 1
            total_cells = num_rows * num_cols

            # Workaround: AI often sends formula_or_values as a JSON string (e.g. '["Name"; "Category"; "Value"]')
            # so we get a str instead of a list; that would be written as one blob per cell and formulas lost.
            # Parse string-as-array (semicolon to comma) and flatten 2D to row-major so per-cell values and
            # formula detection work correctly.
            if isinstance(formula_or_values, str):
                parsed = _parse_formula_or_values_string(formula_or_values)
                if parsed is not None:
                    formula_or_values = parsed
                    debug_log(
                        "write_formula_range: parsed formula_or_values from string to %d values" % len(parsed),
                        context="Chat",
                    )

            # Handle single value vs array of values
            if isinstance(formula_or_values, (list, tuple)):
                if len(formula_or_values) != total_cells:
                    raise ValueError(f"Array length {len(formula_or_values)} doesn't match range size {total_cells}")
                values = formula_or_values
            else:
                # Single value repeated for all cells
                values = [formula_or_values] * total_cells

            # Write to each cell in the range
            cell_idx = 0
            for row in range(start[1], end[1] + 1):
                for col in range(start[0], end[0] + 1):
                    cell = sheet.getCellByPosition(col, row)
                    value = values[cell_idx]

                    if isinstance(value, str):
                        if value.startswith("="):
                            # Write as formula
                            cell.setFormula(value)
                        else:
                            # Try to convert to number, otherwise text
                            try:
                                num = float(value)
                                cell.setValue(num)
                            except ValueError:
                                cell.setString(value)
                    elif isinstance(value, (int, float)):
                        # Write as number
                        cell.setValue(value)
                    else:
                        # Write as text
                        cell.setString(str(value))

                    cell_idx += 1

            logger.info("Range %s filled with %d values.", range_str.upper(), len(values))
            return f"Range {range_str} filled with {len(values)} values."
        except Exception as e:
            logger.error("Range formula write error (%s): %s", range_str, str(e))
            raise

    def import_csv_from_string(self, csv_data: str, target_cell: str = "A1"):
        """
        Imports CSV data into the sheet starting at target_cell.
        Automatically detects if the delimiter is ',' or ';'.

        Args:
            csv_data: CSV content as a string.
            target_cell: Starting cell (e.g. "A1").

        Returns:
            Summary string of the import result.
        """
        try:
            # Simple auto-detection: if first line has ';' and no ',', use ';'
            # Otherwise default to ','
            delimiter = ","
            first_line = csv_data.split('\n')[0] if csv_data else ""
            if ";" in first_line and "," not in first_line:
                delimiter = ";"
                debug_log("import_csv_from_string: detected semicolon delimiter", context="Chat")
            elif "," in first_line:
                delimiter = ","
                debug_log("import_csv_from_string: detected comma delimiter", context="Chat")

            col_start, row_start = parse_address(target_cell)
            import csv
            import io
            reader = csv.reader(io.StringIO(csv_data), delimiter=delimiter)
            rows = list(reader)
            if not rows:
                return "No data to import."

            sheet = self.bridge.get_active_sheet()
            total_rows = len(rows)
            total_cols = max(len(r) for r in rows) if rows else 0

            for r_idx, row in enumerate(rows):
                for c_idx, cell_value in enumerate(row):
                    col = col_start + c_idx
                    row = row_start + r_idx
                    cell = sheet.getCellByPosition(col, row)
                    # Try to convert to number, otherwise treat as string
                    try:
                        num = float(cell_value)
                        cell.setValue(num)
                    except ValueError:
                        cell.setString(cell_value)

            range_imported = f"{target_cell}:{self.bridge._index_to_column(col_start + total_cols - 1)}{row_start + total_rows}"
            logger.info("CSV imported to range %s.", range_imported)
            return f"Imported {total_rows} rows, {total_cols} cols to {range_imported}."
        except Exception as e:
            logger.error("CSV import error: %s", str(e))
            raise

    def create_chart(
        self,
        data_range: str,
        chart_type: str,
        title: str = None,
        position: str = None,
        has_header: bool = True,
    ):
        """
        Creates a chart from data.

        Args:
            data_range: Range for chart data (e.g. A1:B10).
            chart_type: Chart type (bar, line, pie, scatter, column).
            title: Chart title.
            position: Cell where chart will be placed (e.g. E1).
            has_header: Is first row/column a label?
        """
        try:
            sheet = self.bridge.get_active_sheet()
            cell_range = self.bridge.get_cell_range(sheet, data_range)
            range_address = cell_range.getRangeAddress()

            if position:
                pos_cell = self._get_cell(position)
                pos_x = pos_cell.Position.X
                pos_y = pos_cell.Position.Y
            else:
                pos_x = 10000 
                pos_y = 1000  

            from com.sun.star.awt import Rectangle

            rect = Rectangle()
            rect.X = pos_x
            rect.Y = pos_y
            rect.Width = 12000
            rect.Height = 8000

            charts = sheet.getCharts()
            chart_name = f"Chart_{len(charts)}"

            type_map = {
                "bar": "com.sun.star.chart.BarDiagram",
                "column": "com.sun.star.chart.BarDiagram",
                "line": "com.sun.star.chart.LineDiagram",
                "pie": "com.sun.star.chart.PieDiagram",
                "scatter": "com.sun.star.chart.XYDiagram",
            }

            chart_service = type_map.get(chart_type, "com.sun.star.chart.BarDiagram")

            charts.addNewByName(
                chart_name,
                rect,
                (range_address,),
                has_header,
                has_header
            )

            chart = charts.getByName(chart_name).getEmbeddedObject()
            diagram = chart.createInstance(chart_service)
            chart.setDiagram(diagram)

            if chart_type == "bar" and hasattr(diagram, "Vertical"):
                diagram.Vertical = True
            elif chart_type == "column" and hasattr(diagram, "Vertical"):
                diagram.Vertical = False

            if title:
                chart.setPropertyValue("HasMainTitle", True)
                chart_title = chart.getTitle()
                chart_title.setPropertyValue("String", title)

            logger.info("Chart created: %s (%s)", chart_name, chart_type)
            return f"{chart_type} type chart created."

        except Exception as e:
            logger.error("Chart creation error: %s", str(e))
            raise

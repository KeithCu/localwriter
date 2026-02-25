"""Writer table tools."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.writer")


class ListTables(ToolBase):
    """List all text tables in the document."""

    name = "list_tables"
    intent = "edit"
    description = (
        "List all text tables in the document with their names "
        "and dimensions (rows x cols)."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        if not hasattr(doc, "getTextTables"):
            return {"status": "error", "message": "Document does not support text tables."}

        tables_sup = doc.getTextTables()
        tables = []
        for name in tables_sup.getElementNames():
            table = tables_sup.getByName(name)
            tables.append({
                "name": name,
                "rows": table.getRows().getCount(),
                "cols": table.getColumns().getCount(),
            })
        return {"status": "ok", "tables": tables, "count": len(tables)}


class ReadTable(ToolBase):
    """Read all cell contents from a named Writer table."""

    name = "read_table"
    intent = "edit"
    description = "Read all cell contents from a named Writer table as a 2D array."
    parameters = {
        "type": "object",
        "properties": {
            "table_name": {
                "type": "string",
                "description": "The table name from list_tables.",
            },
        },
        "required": ["table_name"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        table_name = kwargs.get("table_name", "")
        if not table_name:
            return {"status": "error", "message": "table_name is required."}

        doc = ctx.doc
        tables_sup = doc.getTextTables()
        if not tables_sup.hasByName(table_name):
            available = list(tables_sup.getElementNames())
            return {
                "status": "error",
                "message": "Table '%s' not found." % table_name,
                "available": available,
            }

        table = tables_sup.getByName(table_name)
        rows = table.getRows().getCount()
        cols = table.getColumns().getCount()
        data = []
        for r in range(rows):
            row_data = []
            for c in range(cols):
                col_letter = _col_letter(c)
                cell_ref = "%s%d" % (col_letter, r + 1)
                try:
                    row_data.append(table.getCellByName(cell_ref).getString())
                except Exception:
                    row_data.append("")
            data.append(row_data)

        return {
            "status": "ok",
            "table_name": table_name,
            "rows": rows,
            "cols": cols,
            "data": data,
        }


class WriteTableCell(ToolBase):
    """Write a value to a specific cell in a Writer table."""

    name = "write_table_cell"
    intent = "edit"
    description = (
        "Write a value to a specific cell in a named Writer table. "
        "Use Excel-style cell references (e.g. 'A1', 'B2'). "
        "Numeric strings are stored as numbers automatically."
    )
    parameters = {
        "type": "object",
        "properties": {
            "table_name": {
                "type": "string",
                "description": "The table name from list_tables.",
            },
            "cell": {
                "type": "string",
                "description": "Cell reference, e.g. 'A1', 'B3'.",
            },
            "value": {
                "type": "string",
                "description": "The value to write.",
            },
        },
        "required": ["table_name", "cell", "value"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        table_name = kwargs.get("table_name", "")
        cell_ref = kwargs.get("cell", "")
        value = kwargs.get("value", "")

        if not table_name or not cell_ref:
            return {"status": "error", "message": "table_name and cell are required."}

        doc = ctx.doc
        tables_sup = doc.getTextTables()
        if not tables_sup.hasByName(table_name):
            return {"status": "error", "message": "Table '%s' not found." % table_name}

        table = tables_sup.getByName(table_name)
        cell_obj = table.getCellByName(cell_ref)
        if cell_obj is None:
            return {
                "status": "error",
                "message": "Cell '%s' not found in table '%s'." % (cell_ref, table_name),
            }

        try:
            cell_obj.setValue(float(value))
        except (ValueError, TypeError):
            cell_obj.setString(str(value))

        return {
            "status": "ok",
            "table": table_name,
            "cell": cell_ref,
            "value": value,
        }


class CreateTable(ToolBase):
    """Create a new table at a paragraph position."""

    name = "create_table"
    intent = "edit"
    description = (
        "Create a new table at a paragraph position. "
        "The table is inserted relative to the target paragraph. "
        "Provide either a locator string or a paragraph_index."
    )
    parameters = {
        "type": "object",
        "properties": {
            "rows": {
                "type": "integer",
                "description": "Number of rows.",
            },
            "cols": {
                "type": "integer",
                "description": "Number of columns.",
            },
            "paragraph_index": {
                "type": "integer",
                "description": "Paragraph index for insertion point.",
            },
            "locator": {
                "type": "string",
                "description": (
                    "Unified locator for insertion point "
                    "(e.g. 'bookmark:NAME', 'heading_text:Title')."
                ),
            },
            "position": {
                "type": "string",
                "enum": ["before", "after"],
                "description": (
                    "Insert before or after the target paragraph "
                    "(default: after)."
                ),
            },
        },
        "required": ["rows", "cols"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        rows = kwargs.get("rows")
        cols = kwargs.get("cols")
        if not rows or not cols:
            return {"status": "error", "message": "rows and cols are required."}
        if rows < 1 or cols < 1:
            return {"status": "error", "message": "rows and cols must be >= 1."}

        paragraph_index = kwargs.get("paragraph_index")
        locator = kwargs.get("locator")
        position = kwargs.get("position", "after")

        doc = ctx.doc
        doc_svc = ctx.services.document

        try:
            # Resolve locator to paragraph index
            if locator is not None and paragraph_index is None:
                resolved = doc_svc.resolve_locator(doc, locator)
                paragraph_index = resolved.get("para_index")

            if paragraph_index is None:
                return {
                    "status": "error",
                    "message": "Provide locator or paragraph_index.",
                }

            # Find the target paragraph element
            target, _ = doc_svc.find_paragraph_element(doc, paragraph_index)
            if target is None:
                return {
                    "status": "error",
                    "message": "Paragraph %d not found." % paragraph_index,
                }

            # Create and insert the table
            table = doc.createInstance("com.sun.star.text.TextTable")
            table.initialize(rows, cols)

            doc_text = doc.getText()
            if position == "before":
                cursor = doc_text.createTextCursorByRange(target.getStart())
            else:
                cursor = doc_text.createTextCursorByRange(target.getEnd())

            doc_text.insertTextContent(cursor, table, False)

            table_name = table.getName()

            return {
                "status": "ok",
                "table_name": table_name,
                "rows": rows,
                "cols": cols,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _col_letter(c):
    """Convert 0-based column index to Excel-style letter(s)."""
    if c < 26:
        return chr(ord("A") + c)
    return "A" + chr(ord("A") + c - 26)

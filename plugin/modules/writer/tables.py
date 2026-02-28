import json
from plugin.framework.logging import debug_log

def _err(message):
    return json.dumps({"status": "error", "message": message})

def tool_list_tables(model, ctx, args):
    """List all text tables in the document."""
    try:
        if not hasattr(model, "getTextTables"):
            return _err("Document does not support text tables")
        tables_sup = model.getTextTables()
        tables = []
        for name in tables_sup.getElementNames():
            table = tables_sup.getByName(name)
            tables.append({
                "name": name,
                "rows": table.getRows().getCount(),
                "cols": table.getColumns().getCount(),
            })
        return json.dumps({"status": "ok", "tables": tables,
                           "count": len(tables)})
    except Exception as e:
        debug_log("tool_list_tables error: %s" % e, context="Chat")
        return _err(str(e))

def tool_read_table(model, ctx, args):
    """Read all cell contents from a named Writer table."""
    table_name = args.get("table_name", "")
    if not table_name:
        return _err("table_name is required")
    try:
        tables_sup = model.getTextTables()
        if not tables_sup.hasByName(table_name):
            available = list(tables_sup.getElementNames())
            return json.dumps({"status": "error",
                               "message": "Table '%s' not found" % table_name,
                               "available": available})
        table = tables_sup.getByName(table_name)
        rows = table.getRows().getCount()
        cols = table.getColumns().getCount()
        data = []
        for r in range(rows):
            row_data = []
            for c in range(cols):
                col_letter = (chr(ord("A") + c) if c < 26
                              else "A" + chr(ord("A") + c - 26))
                cell_ref = "%s%d" % (col_letter, r + 1)
                try:
                    row_data.append(table.getCellByName(cell_ref).getString())
                except Exception:
                    row_data.append("")
            data.append(row_data)
        return json.dumps({"status": "ok", "table_name": table_name,
                           "rows": rows, "cols": cols, "data": data})
    except Exception as e:
        debug_log("tool_read_table error: %s" % e, context="Chat")
        return _err(str(e))

def tool_write_table_cell(model, ctx, args):
    """Write a value to a specific cell in a Writer table."""
    table_name = args.get("table_name", "")
    cell_ref = args.get("cell", "")
    value = args.get("value", "")
    if not table_name or not cell_ref:
        return _err("table_name and cell are required")
    try:
        tables_sup = model.getTextTables()
        if not tables_sup.hasByName(table_name):
            return _err("Table '%s' not found" % table_name)
        table = tables_sup.getByName(table_name)
        cell_obj = table.getCellByName(cell_ref)
        if cell_obj is None:
            return _err("Cell '%s' not found in table '%s'" % (cell_ref, table_name))
        try:
            cell_obj.setValue(float(value))
        except (ValueError, TypeError):
            cell_obj.setString(str(value))
        return json.dumps({"status": "ok", "table": table_name,
                           "cell": cell_ref, "value": value})
    except Exception as e:
        debug_log("tool_write_table_cell error: %s" % e, context="Chat")
        return _err(str(e))

TABLES_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List all text tables in the document with their names and dimensions (rows x cols).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_table",
            "description": "Read all cell contents from a named Writer table as a 2D array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The table name from list_tables.",
                    },
                },
                "required": ["table_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_table_cell",
            "description": (
                "Write a value to a specific cell in a named Writer table. "
                "Use Excel-style cell references (e.g. 'A1', 'B2'). "
                "Numeric strings are stored as numbers automatically."
            ),
            "parameters": {
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
                "additionalProperties": False,
            },
        },
    },
]

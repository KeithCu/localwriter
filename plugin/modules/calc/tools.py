"""Calc document manipulation tools for AI chat sidebar."""

import json
import logging
from plugin.framework.logging import agent_log
from plugin.modules.calc.bridge import CalcBridge
from plugin.modules.calc.inspector import CellInspector
from plugin.modules.calc.manipulator import CellManipulator
from plugin.modules.calc.analyzer import SheetAnalyzer
from plugin.modules.calc.error_detector import ErrorDetector

logger = logging.getLogger(__name__)

CALC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_cell_range",
            "description": "Reads values from the specified cell range(s). Supports lists for non-contiguous areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "Cell range(s) (e.g. A1:D10, Sheet1.A1:C5) or list of ranges/cells for non-contiguous areas.",
                    }
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_cell_style",
            "description": "Applies style and formatting to the specified cell(s) or range(s). Supports lists for non-contiguous areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "Target cell(s) or range(s) (e.g. A1:D10) or list of ranges/cells for non-contiguous areas.",
                    },
                    "bold": {"type": "boolean", "description": "Bold font"},
                    "italic": {"type": "boolean", "description": "Italic font"},
                    "font_size": {"type": "number", "description": "Font size (points)"},
                    "bg_color": {"type": "string", "description": "Background color (hex: #FF0000 or name: yellow)"},
                    "font_color": {"type": "string", "description": "Font color (hex: #000000 or name: red)"},
                    "h_align": {
                        "type": "string",
                        "enum": ["left", "center", "right", "justify"],
                        "description": "Horizontal alignment",
                    },
                    "v_align": {
                        "type": "string",
                        "enum": ["top", "center", "bottom"],
                        "description": "Vertical alignment",
                    },
                    "wrap_text": {"type": "boolean", "description": "Wrap text"},
                    "border_color": {"type": "string", "description": "Border color (hex or name). Draws a frame around the cell/range."},
                    "number_format": {"type": "string", "description": "Number format (e.g. #,##0.00, 0%, dd.mm.yyyy)"},
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sheet_summary",
            "description": "Returns a summary of the active or specified sheet (size, used cells, column headers, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "Sheet name (active sheet if empty)"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_and_explain_errors",
            "description": "Detects formula errors in the specified range(s) and provides an explanation and fix suggestion. Supports lists for non-contiguous areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "Cell range(s) to check (e.g. A1:Z100) or list of ranges/cells for non-contiguous areas. Full sheet if empty."
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "merge_cells",
            "description": "Merges the specified cell range(s). Typically used for main headers. Write text with write_formula_range and style with set_cell_style after merging. Supports lists for non-contiguous areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "Range(s) to merge (e.g. A1:D1) or list of ranges for non-contiguous areas."
                    },
                    "center": {"type": "boolean", "description": "Center content (default: true)"}
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_sheets",
            "description": "Lists all sheet names in the workbook.",
            "parameters": {"type": "object", "properties": {}},
            "required": [],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_sheet",
            "description": "Switches to the specified sheet (makes it active).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "Name of the sheet to switch to"}
                },
                "required": ["sheet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_sheet",
            "description": "Creates a new sheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "New sheet name"},
                    "position": {"type": "integer", "description": "Sheet position (0-based). Appended to end if not specified."}
                },
                "required": ["sheet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_chart",
            "description": "Creates a chart from data. Supports bar, column, line, pie, or scatter charts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_range": {"type": "string", "description": "Range for chart data (e.g. A1:B10)"},
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "pie", "scatter", "column"],
                        "description": "Chart type",
                    },
                    "title": {"type": "string", "description": "Chart title"},
                    "position": {"type": "string", "description": "Cell where chart will be placed (e.g. E1)"},
                    "has_header": {"type": "boolean", "description": "Is first row/column a label? Default: true"}
                },
                "required": ["data_range", "chart_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sort_range",
            "description": "Sorts the specified range(s) by a column. Use for ordering rows by values in one column. Supports lists for non-contiguous areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "Range(s) to sort (e.g. A1:D10) or list of ranges for non-contiguous areas."
                    },
                    "sort_column": {"type": "integer", "description": "0-based column index within the range to sort by (default: 0)"},
                    "ascending": {"type": "boolean", "description": "True for ascending, False for descending (default: true)"},
                    "has_header": {"type": "boolean", "description": "Is the first row a header that should not be sorted? (default: true)"}
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_range",
            "description": "Clears all contents (values, formulas) in the specified range(s). Supports lists for non-contiguous areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "Range(s) to clear (e.g. A1:D10) or list of ranges/cells for non-contiguous areas."
                    }
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_formula_range",
            "description": "Writes formulas or values to a cell range(s) efficiently. Use a single value to fill the entire range, or an array of values for each cell. Supports lists for non-contiguous areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "Target range(s) (e.g. A1:A10, B2:D2) or list of ranges/cells for non-contiguous areas."
                    },
                    "formula_or_values": {
                        "type": ["string", "number", "array"],
                        "description": "Single formula/value for all cells, or array of formulas/values for each cell. Formulas start with '='."
                    }
                },
                "required": ["range_name", "formula_or_values"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "import_csv_from_string",
            "description": "Inserts CSV data into the sheet starting at a cell. Handles large datasets efficiently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "csv_data": {
                        "type": "string",
                        "description": "CSV content as string (rows separated by \\n)."
                    },
                    "target_cell": {
                        "type": "string",
                        "description": "Starting cell (default 'A1')."
                    }
                },
                "required": ["csv_data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_structure",
            "description": "Deletes rows or columns. Use for structural changes; prefer ranges for data operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "structure_type": {
                        "type": "string",
                        "enum": ["rows", "columns"],
                        "description": "Type of structure to delete."
                    },
                    "start": {
                        "type": ["integer", "string"],
                        "description": "For rows: row number (1-based); for columns: column letter."
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number to delete (default 1)."
                    }
                },
                "required": ["structure_type", "start"],
            },
        },
    },
]

# Shared instances for the session
_bridge = None
_inspector = None
_manipulator = None
_analyzer = None
_error_detector = None

def _get_tools(doc):
    global _bridge, _inspector, _manipulator, _analyzer, _error_detector
    if _bridge is None or _bridge.doc != doc:
        _bridge = CalcBridge(doc)
        _inspector = CellInspector(_bridge)
        _manipulator = CellManipulator(_bridge)
        _analyzer = SheetAnalyzer(_bridge)
        _error_detector = ErrorDetector(_bridge, _inspector)
    return {
        "inspector": _inspector,
        "manipulator": _manipulator,
        "analyzer": _analyzer,
        "error_detector": _error_detector
    }

def _parse_color(color_str):
    if not color_str:
        return None
    color_str = color_str.strip().lower()
    color_names = {
        "red": 0xFF0000, "green": 0x00FF00, "blue": 0x0000FF,
        "yellow": 0xFFFF00, "white": 0xFFFFFF, "black": 0x000000,
        "orange": 0xFF8C00, "purple": 0x800080, "gray": 0x808080,
    }
    if color_str in color_names:
        return color_names[color_str]
    if color_str.startswith("#"):
        try:
            return int(color_str[1:], 16)
        except ValueError:
            return None
    return None

def execute_calc_tool(tool_name, arguments, doc, ctx=None):
    """Execute a Calc tool by name. Returns JSON result string."""
    tools = _get_tools(doc)
    agent_log("calc_tools.py:execute_calc_tool", "Tool call", data={"tool": tool_name, "arguments": arguments})
    
    try:
        if tool_name == "read_cell_range":
            rn = arguments["range_name"]
            if isinstance(rn, list):
                results = [tools["inspector"].read_range(r) for r in rn]
                return json.dumps({"status": "ok", "result": results})
            else:
                result = tools["inspector"].read_range(rn)
                return json.dumps({"status": "ok", "result": result})
            
        elif tool_name == "set_cell_style":
            rn = arguments["range_name"]
            if isinstance(rn, list):
                for r in rn:
                    tools["manipulator"].set_cell_style(
                        r,
                        bold=arguments.get("bold"),
                        italic=arguments.get("italic"),
                        bg_color=_parse_color(arguments.get("bg_color")),
                        font_color=_parse_color(arguments.get("font_color")),
                        font_size=arguments.get("font_size"),
                        h_align=arguments.get("h_align"),
                        v_align=arguments.get("v_align"),
                        wrap_text=arguments.get("wrap_text"),
                        border_color=_parse_color(arguments.get("border_color")),
                        number_format=arguments.get("number_format")
                    )
                return json.dumps({"status": "ok", "message": f"Style applied to {len(rn)} ranges"})
            else:
                tools["manipulator"].set_cell_style(
                    rn,
                    bold=arguments.get("bold"),
                    italic=arguments.get("italic"),
                    bg_color=_parse_color(arguments.get("bg_color")),
                    font_color=_parse_color(arguments.get("font_color")),
                    font_size=arguments.get("font_size"),
                    h_align=arguments.get("h_align"),
                    v_align=arguments.get("v_align"),
                    wrap_text=arguments.get("wrap_text"),
                    border_color=_parse_color(arguments.get("border_color")),
                    number_format=arguments.get("number_format")
                )
                return json.dumps({"status": "ok", "message": f"Style applied to {rn}"})
            
        elif tool_name == "get_sheet_summary":
            result = tools["analyzer"].get_sheet_summary(sheet_name=arguments.get("sheet_name"))
            return json.dumps({"status": "ok", "result": result})
            
        elif tool_name == "detect_and_explain_errors":
            rn = arguments.get("range_name")
            if rn and isinstance(rn, list):
                results = [tools["error_detector"].detect_and_explain(range_str=r) for r in rn]
                combined = {"errors": [], "summary": ""}
                for res in results:
                    combined["errors"].extend(res.get("errors", []))
                    combined["summary"] += res.get("summary", "") + "; "
                return json.dumps({"status": "ok", "result": combined})
            else:
                result = tools["error_detector"].detect_and_explain(range_str=rn)
                return json.dumps({"status": "ok", "result": result})
            
        elif tool_name == "merge_cells":
            rn = arguments["range_name"]
            if isinstance(rn, list):
                for r in rn:
                    tools["manipulator"].merge_cells(r, center=arguments.get("center", True))
                return json.dumps({"status": "ok", "message": f"Merged cells in {len(rn)} ranges"})
            else:
                tools["manipulator"].merge_cells(rn, center=arguments.get("center", True))
                return json.dumps({"status": "ok", "message": f"Merged cells {rn}"})
            
        elif tool_name == "list_sheets":
            result = tools["manipulator"].list_sheets()
            return json.dumps({"status": "ok", "result": result})
            
        elif tool_name == "switch_sheet":
            result = tools["manipulator"].switch_sheet(arguments["sheet_name"])
            return json.dumps({"status": "ok", "message": result})
            
        elif tool_name == "create_sheet":
            result = tools["manipulator"].create_sheet(arguments["sheet_name"], position=arguments.get("position"))
            return json.dumps({"status": "ok", "message": result})
            
        elif tool_name == "create_chart":
            result = tools["manipulator"].create_chart(
                arguments["data_range"],
                arguments["chart_type"],
                title=arguments.get("title"),
                position=arguments.get("position"),
                has_header=arguments.get("has_header", True)
            )
            return json.dumps({"status": "ok", "message": result})
            
        elif tool_name == "sort_range":
            rn = arguments["range_name"]
            if isinstance(rn, list):
                for r in rn:
                    tools["manipulator"].sort_range(
                        r,
                        sort_column=arguments.get("sort_column", 0),
                        ascending=arguments.get("ascending", True),
                        has_header=arguments.get("has_header", True)
                    )
                return json.dumps({"status": "ok", "message": f"Sorted {len(rn)} ranges"})
            else:
                result = tools["manipulator"].sort_range(
                    rn,
                    sort_column=arguments.get("sort_column", 0),
                    ascending=arguments.get("ascending", True),
                    has_header=arguments.get("has_header", True)
                )
                return json.dumps({"status": "ok", "message": result})

        elif tool_name == "clear_range":
            rn = arguments["range_name"]
            if isinstance(rn, list):
                for r in rn:
                    tools["manipulator"].clear_range(r)
                return json.dumps({"status": "ok", "message": f"Cleared {len(rn)} ranges"})
            else:
                tools["manipulator"].clear_range(rn)
                return json.dumps({"status": "ok", "message": f"Cleared range {rn}"})

        elif tool_name == "write_formula_range":
            rn = arguments["range_name"]
            if isinstance(rn, list):
                for r in rn:
                    tools["manipulator"].write_formula_range(
                        r,
                        arguments["formula_or_values"]
                    )
                return json.dumps({"status": "ok", "message": f"Wrote to {len(rn)} ranges"})
            else:
                result = tools["manipulator"].write_formula_range(
                    rn,
                    arguments["formula_or_values"]
                )
                return json.dumps({"status": "ok", "message": result})

        elif tool_name == "import_csv_from_string":
            result = tools["manipulator"].import_csv_from_string(
                arguments["csv_data"],
                target_cell=arguments.get("target_cell", "A1")
            )
            return json.dumps({"status": "ok", "message": result})

        elif tool_name == "delete_structure":
            result = tools["manipulator"].delete_structure(
                arguments["structure_type"],
                arguments["start"],
                count=arguments.get("count", 1)
            )
            return json.dumps({"status": "ok", "message": result})

        else:
            return json.dumps({"status": "error", "message": f"Unknown tool: {tool_name}"})
            
    except Exception as e:
        logger.exception("Error executing Calc tool %s", tool_name)
        return json.dumps({"status": "error", "message": str(e)})

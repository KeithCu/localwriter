"""Calc document manipulation tools for AI chat sidebar.
Compatibility shim migrating old macro-like tools to the new Framework."""

import json
import logging
from plugin.framework.tool_registry import ToolRegistry
from plugin.framework.tool_context import ToolContext

import plugin.modules.calc.cells as cells
from plugin.modules.calc.cells import _parse_color
import plugin.modules.calc.formulas as formulas
import plugin.modules.calc.sheets as sheets

logger = logging.getLogger(__name__)

# Initialize a standalone registry just for Calc tools
_registry = ToolRegistry(services={})

# Instantiate and register manually
_tool_classes = [
    cells.ReadCellRange,
    cells.WriteCellRange,
    cells.SetCellStyle,
    cells.MergeCells,
    cells.ClearRange,
    cells.SortRange,
    cells.ImportCsv,
    cells.DeleteStructure,
    formulas.DetectErrors,
    sheets.GetSheetSummary,
    sheets.ListSheets,
    sheets.SwitchSheet,
    sheets.CreateSheet,
    sheets.CreateChart
]

for cls in _tool_classes:
    _registry.register(cls())

# Export the tools schema list
CALC_TOOLS = _registry.get_openai_schemas(doc_type="calc", tier="core") + _registry.get_openai_schemas(doc_type="calc", tier="extended")

def execute_calc_tool(tool_name, arguments, doc, ctx=None):
    """Execute a Calc tool by name. Returns JSON result string."""
    # ToolContext expects (doc, ctx, doc_type, services, caller)
    tctx = ToolContext(doc, ctx, "calc", {}, "chatbot")
    
    try:
        res = _registry.execute(tool_name, tctx, **arguments)
        return json.dumps(res)
    except Exception as e:
        logger.exception("execute_calc_tool failed")
        return json.dumps({"status": "error", "message": str(e)})

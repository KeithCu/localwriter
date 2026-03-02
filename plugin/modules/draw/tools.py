"""Draw document manipulation tools for AI chat sidebar."""

import json
import logging
from plugin.framework.logging import agent_log, debug_log
from plugin.modules.draw.bridge import DrawBridge

logger = logging.getLogger(__name__)

from plugin.framework.tool_registry import ToolRegistry
from plugin.framework.tool_context import ToolContext
from plugin.modules.draw.shapes import CreateShape, EditShape, DeleteShape
from plugin.modules.draw.pages import ListPages, GetDrawSummary, AddSlide, DeleteSlide
from plugin.modules.ai.tools import WebResearchTool, GenerateImageTool, EditImageTool

# Initialize Draw registry
_registry = ToolRegistry(services={})

_tool_classes = [
    ListPages,
    GetDrawSummary,
    CreateShape,
    EditShape,
    DeleteShape,
    AddSlide,
    DeleteSlide,
    WebResearchTool,
    GenerateImageTool,
    EditImageTool
]

for cls in _tool_classes:
    _registry.register(cls())

# Export the tools schema list
DRAW_TOOLS = _registry.get_openai_schemas(doc_type="draw", tier="core") + \
             _registry.get_openai_schemas(doc_type="draw", tier="extended") + \
             _registry.get_openai_schemas(doc_type="draw", tier="agent")





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

def execute_draw_tool(tool_name, arguments, model, ctx, status_callback=None, append_thinking_callback=None):
    """Execute a Draw tool by name. Returns JSON result string."""
    tctx = ToolContext(
        model, ctx, "draw", {}, "chatbot",
        status_callback=status_callback,
        append_thinking_callback=append_thinking_callback
    )
    
    try:
        res = _registry.execute(tool_name, tctx, **(arguments or {}))
        return json.dumps(res) if isinstance(res, dict) else res
    except Exception as e:
        logger.exception("execute_draw_tool failed")
        return json.dumps({"status": "error", "message": str(e)})

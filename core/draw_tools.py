"""Draw document manipulation tools for AI chat sidebar."""

import json
import logging
from core.logging import agent_log
from core.draw_bridge import DrawBridge

logger = logging.getLogger(__name__)

DRAW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_pages",
            "description": "Lists all pages (slides) in the document.",
            "parameters": {"type": "object", "properties": {}},
            "required": [],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_draw_summary",
            "description": "Returns a summary of shapes on the active or specified page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_index": {"type": "integer", "description": "0-based page index (active page if omitted)"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_shape",
            "description": "Creates a new shape on the active page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "shape_type": {
                        "type": "string",
                        "enum": ["rectangle", "ellipse", "text", "line"],
                        "description": "Type of shape to create",
                    },
                    "x": {"type": "integer", "description": "X position (100ths of mm)"},
                    "y": {"type": "integer", "description": "Y position (100ths of mm)"},
                    "width": {"type": "integer", "description": "Width (100ths of mm)"},
                    "height": {"type": "integer", "description": "Height (100ths of mm)"},
                    "text": {"type": "string", "description": "Initial text for the shape (if applicable)"},
                    "bg_color": {"type": "string", "description": "Hex (e.g. #FF0000) or name (e.g. red)"},
                },
                "required": ["shape_type", "x", "y", "width", "height"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_shape",
            "description": "Modifies properties of an existing shape. Use get_draw_summary to find shape indexes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_index": {"type": "integer", "description": "Page index of the shape"},
                    "shape_index": {"type": "integer", "description": "Index of the shape on the page"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "text": {"type": "string"},
                    "bg_color": {"type": "string", "description": "Hex (e.g. #FF0000) or name (e.g. red)"},
                },
                "required": ["shape_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_shape",
            "description": "Deletes a shape by index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_index": {"type": "integer"},
                    "shape_index": {"type": "integer"},
                },
                "required": ["shape_index"],
            },
        },
    },
]

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

def execute_draw_tool(tool_name, arguments, model, ctx):
    bridge = DrawBridge(model)
    agent_log("draw_tools.py:execute_draw_tool", "Tool call", data={"tool": tool_name, "arguments": arguments})
    
    try:
        if tool_name == "list_pages":
            pages = bridge.get_pages()
            result = [f"Page {i}" for i in range(pages.getCount())]
            return json.dumps({"status": "ok", "result": result})

        elif tool_name == "get_draw_summary":
            idx = arguments.get("page_index")
            if idx is not None:
                page = bridge.get_pages().getByIndex(idx)
            else:
                page = bridge.get_active_page()
            
            shapes = []
            for i in range(page.getCount()):
                s = page.getByIndex(i)
                info = {
                    "index": i,
                    "type": s.getShapeType(),
                    "x": s.getPosition().X,
                    "y": s.getPosition().Y,
                    "width": s.getSize().Width,
                    "height": s.getSize().Height
                }
                if hasattr(s, "getString"):
                    info["text"] = s.getString()
                shapes.append(info)
            return json.dumps({"status": "ok", "result": {"page_index": idx, "shapes": shapes}})

        elif tool_name == "create_shape":
            type_map = {
                "rectangle": "com.sun.star.drawing.RectangleShape",
                "ellipse": "com.sun.star.drawing.EllipseShape",
                "text": "com.sun.star.drawing.TextShape",
                "line": "com.sun.star.drawing.LineShape"
            }
            uno_type = type_map.get(arguments["shape_type"])
            if not uno_type:
                return json.dumps({"status": "error", "message": f"Unsupported shape type: {arguments['shape_type']}"})
            
            shape = bridge.create_shape(
                uno_type, 
                arguments["x"], arguments["y"], 
                arguments["width"], arguments["height"]
            )
            if arguments.get("text") and hasattr(shape, "setString"):
                shape.setString(arguments["text"])
            
            if "bg_color" in arguments:
                color = _parse_color(arguments["bg_color"])
                if color is not None:
                    # LineShape uses LineColor, most others use FillColor
                    prop_name = "LineColor" if "LineShape" in shape.getShapeType() else "FillColor"
                    try:
                        shape.setPropertyValue(prop_name, color)
                    except Exception:
                        from core.logging import debug_log
                        debug_log("Could not set %s on %s" % (prop_name, shape.getShapeType()), context="Draw")
            return json.dumps({"status": "ok", "message": f"Created {arguments['shape_type']}"})

        elif tool_name == "edit_shape":
            idx = arguments.get("page_index")
            if idx is not None:
                page = bridge.get_pages().getByIndex(idx)
            else:
                page = bridge.get_active_page()
            
            shape = page.getByIndex(arguments["shape_index"])
            if "x" in arguments or "y" in arguments:
                from com.sun.star.awt import Point
                pos = shape.getPosition()
                new_x = arguments.get("x", pos.X)
                new_y = arguments.get("y", pos.Y)
                shape.setPosition(Point(new_x, new_y))
            
            if "width" in arguments or "height" in arguments:
                from com.sun.star.awt import Size
                size = shape.getSize()
                new_w = arguments.get("width", size.Width)
                new_h = arguments.get("height", size.Height)
                shape.setSize(Size(new_w, new_h))
                
            if "text" in arguments and hasattr(shape, "setString"):
                shape.setString(arguments["text"])
            
            if "bg_color" in arguments:
                color = _parse_color(arguments["bg_color"])
                if color is not None:
                    prop_name = "LineColor" if "LineShape" in shape.getShapeType() else "FillColor"
                    try:
                        shape.setPropertyValue(prop_name, color)
                    except Exception:
                        debug_log("Could not set %s on %s" % (prop_name, shape.getShapeType()), context="Draw")
            
            return json.dumps({"status": "ok", "message": "Shape updated"})

        elif tool_name == "delete_shape":
            idx = arguments.get("page_index")
            if idx is not None:
                page = bridge.get_pages().getByIndex(idx)
            else:
                page = bridge.get_active_page()
            shape = page.getByIndex(arguments["shape_index"])
            page.remove(shape)
            return json.dumps({"status": "ok", "message": "Shape deleted"})

        else:
            return json.dumps({"status": "error", "message": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.exception("Error executing Draw tool %s", tool_name)
        return json.dumps({"status": "error", "message": str(e)})

"""Navigation tools: navigate_heading, get_surroundings."""

from plugin.framework.tool_base import ToolBase


class NavigateHeading(ToolBase):
    name = "navigate_heading"
    intent = "navigate"
    description = (
        "Navigate from a locator to a related heading. "
        "Directions: next, previous, parent, first_child, "
        "next_sibling, previous_sibling. "
        "Returns the target heading with bookmark for stable addressing."
    )
    parameters = {
        "type": "object",
        "properties": {
            "locator": {
                "type": "string",
                "description": (
                    "Starting position (e.g. 'bookmark:_mcp_xxx', "
                    "'paragraph:42', 'heading_text:Introduction')"
                ),
            },
            "direction": {
                "type": "string",
                "enum": ["next", "previous", "parent", "first_child",
                         "next_sibling", "previous_sibling"],
                "description": "Navigation direction",
            },
        },
        "required": ["locator", "direction"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        prox_svc = ctx.services.writer_proximity
        try:
            result = prox_svc.navigate_heading(
                ctx.doc, kwargs["locator"], kwargs["direction"])
            if "error" in result:
                return {"status": "error", **result}
            return {"status": "ok", **result}
        except ValueError as e:
            return {"status": "error", "error": str(e)}


class GetSurroundings(ToolBase):
    name = "get_surroundings"
    intent = "navigate"
    description = (
        "Discover objects within a radius of paragraphs around a locator. "
        "Returns nearby paragraphs, heading chain, images, tables, "
        "frames, and comments."
    )
    parameters = {
        "type": "object",
        "properties": {
            "locator": {
                "type": "string",
                "description": "Center position (e.g. 'bookmark:_mcp_xxx', 'paragraph:42')",
            },
            "radius": {
                "type": "integer",
                "description": "Number of paragraphs in each direction (default: 10, max: 50)",
            },
            "include": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Object types to include: paragraphs, images, tables, "
                    "frames, comments, headings (default: all)"
                ),
            },
        },
        "required": ["locator"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        prox_svc = ctx.services.writer_proximity
        try:
            result = prox_svc.get_surroundings(
                ctx.doc, kwargs["locator"],
                radius=kwargs.get("radius", 10),
                include=kwargs.get("include"))
            return {"status": "ok", **result}
        except ValueError as e:
            return {"status": "error", "error": str(e)}

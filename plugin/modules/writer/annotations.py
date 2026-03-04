"""AI annotation tools: add_ai_summary, get_ai_summaries, remove_ai_summary."""

from plugin.framework.tool_base import ToolBase


class AddAiSummary(ToolBase):
    name = "add_ai_summary"
    intent = "review"
    description = (
        "Add an AI-generated summary as a comment (MCP-AI author) "
        "at a heading or paragraph. Replaces any existing MCP-AI "
        "annotation at the same location."
    )
    parameters = {
        "type": "object",
        "properties": {
            "locator": {
                "type": "string",
                "description": "Target location (e.g. 'bookmark:_mcp_xxx', 'paragraph:5')",
            },
            "para_index": {
                "type": "integer",
                "description": "Paragraph index (alternative to locator)",
            },
            "summary": {
                "type": "string",
                "description": "Summary text to add as annotation",
            },
        },
        "required": ["summary"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        tree_svc = ctx.services.writer_tree
        para_index = kwargs.get("para_index")
        locator = kwargs.get("locator")
        if locator is not None and para_index is None:
            try:
                resolved = ctx.services.document.resolve_locator(ctx.doc, locator)
                para_index = resolved.get("para_index")
            except ValueError as e:
                return {"status": "error", "error": str(e)}
        if para_index is None:
            return {"status": "error", "error": "Provide locator or para_index"}
        try:
            result = tree_svc.add_ai_summary(ctx.doc, para_index, kwargs["summary"])
            return {"status": "ok", **result}
        except ValueError as e:
            return {"status": "error", "error": str(e)}


class GetAiSummaries(ToolBase):
    name = "get_ai_summaries"
    intent = "review"
    description = "List all MCP-AI summary annotations in the document."
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        tree_svc = ctx.services.writer_tree
        summaries = tree_svc.get_ai_summaries(ctx.doc)
        return {"status": "ok", "summaries": summaries, "count": len(summaries)}


class RemoveAiSummary(ToolBase):
    name = "remove_ai_summary"
    intent = "review"
    description = "Remove an MCP-AI summary annotation at a paragraph."
    parameters = {
        "type": "object",
        "properties": {
            "locator": {
                "type": "string",
                "description": "Target location (e.g. 'bookmark:_mcp_xxx')",
            },
            "para_index": {
                "type": "integer",
                "description": "Paragraph index (alternative to locator)",
            },
        },
        "required": [],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        tree_svc = ctx.services.writer_tree
        para_index = kwargs.get("para_index")
        locator = kwargs.get("locator")
        if locator is not None and para_index is None:
            try:
                resolved = ctx.services.document.resolve_locator(ctx.doc, locator)
                para_index = resolved.get("para_index")
            except ValueError as e:
                return {"status": "error", "error": str(e)}
        if para_index is None:
            return {"status": "error", "error": "Provide locator or para_index"}
        removed = tree_svc.remove_ai_summary(ctx.doc, para_index)
        return {"status": "ok", "removed": removed, "para_index": para_index}

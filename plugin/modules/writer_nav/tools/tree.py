"""Heading tree tools: get_document_tree, get_heading_children."""

from plugin.framework.tool_base import ToolBase


class GetDocumentTree(ToolBase):
    name = "get_document_tree"
    intent = "navigate"
    description = (
        "Get the document heading tree with bookmarks and content previews. "
        "Creates _mcp_ bookmarks on headings for stable addressing. "
        "Content strategies: heading_only, first_lines (default), "
        "ai_summary_first, full. "
        "depth=0 for unlimited, depth=1 (default) for top-level only."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content_strategy": {
                "type": "string",
                "enum": ["heading_only", "first_lines", "ai_summary_first", "full"],
                "description": "Content to include with headings (default: first_lines)",
            },
            "depth": {
                "type": "integer",
                "description": "Max tree depth (0=unlimited, default: 1)",
            },
        },
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        tree_svc = ctx.services.writer_tree
        result = tree_svc.get_document_tree(
            ctx.doc,
            content_strategy=kwargs.get("content_strategy", "first_lines"),
            depth=kwargs.get("depth", 1),
        )
        return {"status": "ok", **result}


class GetHeadingChildren(ToolBase):
    name = "get_heading_children"
    intent = "navigate"
    description = (
        "Drill into a heading's children — body paragraphs and sub-headings. "
        "Identify the heading by locator (e.g. 'bookmark:_mcp_xxx', "
        "'heading_text:Title'), heading_para_index, or heading_bookmark."
    )
    parameters = {
        "type": "object",
        "properties": {
            "locator": {
                "type": "string",
                "description": "Locator string (e.g. 'bookmark:_mcp_xxx', 'heading:1.2')",
            },
            "heading_para_index": {
                "type": "integer",
                "description": "Paragraph index of the heading",
            },
            "heading_bookmark": {
                "type": "string",
                "description": "Bookmark name of the heading",
            },
            "content_strategy": {
                "type": "string",
                "enum": ["heading_only", "first_lines", "ai_summary_first", "full"],
                "description": "Content strategy (default: first_lines)",
            },
            "depth": {
                "type": "integer",
                "description": "Max sub-heading depth (default: 1)",
            },
        },
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        tree_svc = ctx.services.writer_tree
        try:
            result = tree_svc.get_heading_children(
                ctx.doc,
                heading_para_index=kwargs.get("heading_para_index"),
                heading_bookmark=kwargs.get("heading_bookmark"),
                locator=kwargs.get("locator"),
                content_strategy=kwargs.get("content_strategy", "first_lines"),
                depth=kwargs.get("depth", 1),
            )
            return {"status": "ok", **result}
        except ValueError as e:
            return {"status": "error", "error": str(e)}

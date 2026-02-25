"""Bookmark tools: list_bookmarks, cleanup_bookmarks."""

from plugin.framework.tool_base import ToolBase


class ListBookmarks(ToolBase):
    name = "list_bookmarks"
    intent = "navigate"
    description = (
        "List all bookmarks in the document with their anchor text preview. "
        "Includes both user bookmarks and _mcp_ heading bookmarks."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        if not hasattr(doc, "getBookmarks"):
            return {"status": "ok", "bookmarks": [], "count": 0}
        try:
            bookmarks = doc.getBookmarks()
            names = bookmarks.getElementNames()
            result = []
            for name in names:
                bm = bookmarks.getByName(name)
                anchor_text = bm.getAnchor().getString()
                result.append({
                    "name": name,
                    "preview": anchor_text[:100] if anchor_text else "",
                })
            return {"status": "ok", "bookmarks": result, "count": len(result)}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class CleanupBookmarks(ToolBase):
    name = "cleanup_bookmarks"
    intent = "navigate"
    description = (
        "Remove all _mcp_* bookmarks from the document. "
        "Use when bookmarks become stale after major edits."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        bm_svc = ctx.services.writer_bookmarks
        removed = bm_svc.cleanup_mcp_bookmarks(ctx.doc)
        return {"status": "ok", "removed": removed}

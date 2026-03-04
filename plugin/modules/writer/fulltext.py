"""Full-text search tools: search_fulltext, get_index_stats."""

from plugin.framework.tool_base import ToolBase


class SearchFulltext(ToolBase):
    name = "search_fulltext"
    intent = "navigate"
    description = (
        "Full-text search with Snowball stemming. Supports boolean queries: "
        "AND (default), OR, NOT, NEAR/N. "
        "Language auto-detected from document locale. "
        "Returns matching paragraphs with context and nearest heading bookmark. "
        "Use around_page to restrict results near a specific page."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search query. Examples: 'climate change', "
                    "'energy AND renewable', 'solar OR wind', "
                    "'climate NOT politics', 'ocean NEAR/3 warming'"
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default: 20)",
            },
            "context_paragraphs": {
                "type": "integer",
                "description": "Paragraphs of context around each match (default: 1)",
            },
            "around_page": {
                "type": "integer",
                "description": (
                    "Restrict results to paragraphs near this page "
                    "(optional). Enables page numbers in results."
                ),
            },
            "page_radius": {
                "type": "integer",
                "description": (
                    "Page radius for around_page filter "
                    "(default: 1, meaning +/-1 page)"
                ),
            },
            "include_pages": {
                "type": "boolean",
                "description": (
                    "Add page numbers to results. "
                    "Costs ~30s on first call (cached after). "
                    "Automatic when around_page is set. "
                    "(default: false)"
                ),
            },
        },
        "required": ["query"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        idx_svc = ctx.services.writer_index
        around_page = kwargs.get("around_page")
        page_radius = kwargs.get("page_radius", 1)
        include_pages = kwargs.get("include_pages", False)

        if around_page is not None:
            include_pages = True

        try:
            result = idx_svc.search_boolean(
                ctx.doc,
                kwargs["query"],
                max_results=kwargs.get("max_results", 20),
                context_paragraphs=kwargs.get("context_paragraphs", 1),
            )
        except ValueError as e:
            return {"status": "error", "error": str(e)}

        # Post-process: add page numbers and filter by page proximity
        if include_pages and result.get("matches"):
            page_map = _build_page_map(ctx.doc)
            for m in result["matches"]:
                pi = m.get("paragraph_index")
                if pi is not None and pi in page_map:
                    m["page"] = page_map[pi]

            if around_page is not None:
                lo = around_page - page_radius
                hi = around_page + page_radius
                before_count = len(result["matches"])
                result["matches"] = [
                    m for m in result["matches"]
                    if lo <= m.get("page", 0) <= hi
                ]
                result["returned"] = len(result["matches"])
                result["filtered_by_page"] = {
                    "around_page": around_page,
                    "page_radius": page_radius,
                    "before_filter": before_count,
                }

        return {"status": "ok", **result}


# Page map cache (cleared on doc change)
_page_map_cache = {}


def _build_page_map(doc):
    """Map paragraph indices to page numbers using view cursor."""
    doc_url = doc.getURL() or id(doc)
    if doc_url in _page_map_cache:
        return _page_map_cache[doc_url]

    page_map = {}
    try:
        controller = doc.getCurrentController()
        vc = controller.getViewCursor()
        saved = doc.getText().createTextCursorByRange(vc.getStart())
        doc.lockControllers()
        try:
            text = doc.getText()
            enum = text.createEnumeration()
            idx = 0
            while enum.hasMoreElements():
                para = enum.nextElement()
                try:
                    vc.gotoRange(para.getStart(), False)
                    page_map[idx] = vc.getPage()
                except Exception:
                    pass
                idx += 1
        finally:
            vc.gotoRange(saved, False)
            doc.unlockControllers()
    except Exception:
        pass

    _page_map_cache[doc_url] = page_map
    return page_map


class GetIndexStats(ToolBase):
    name = "get_index_stats"
    intent = "navigate"
    description = (
        "Get search index statistics: paragraph count, unique stems, "
        "language, build time, and top 20 most frequent stems."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        idx_svc = ctx.services.writer_index
        result = idx_svc.get_index_stats(ctx.doc)
        return {"status": "ok", **result}

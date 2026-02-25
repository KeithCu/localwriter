"""Writer document statistics tool."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.writer")


class GetDocumentStats(ToolBase):
    """Return basic statistics about the current Writer document."""

    name = "get_document_stats"
    description = (
        "Returns document statistics: character count, word count, "
        "paragraph count, page count, and heading count."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = ["writer"]
    tier = "core"

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        doc_svc = ctx.services.document

        # Character and word count via full text.
        try:
            text_obj = doc.getText()
            cursor = text_obj.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            full_text = cursor.getString()
            char_count = len(full_text)
            word_count = len(full_text.split())
        except Exception:
            char_count = doc_svc.get_document_length(doc)
            word_count = 0

        # Paragraph count.
        try:
            para_ranges = doc_svc.get_paragraph_ranges(doc)
            para_count = len(para_ranges)
        except Exception:
            para_count = 0

        # Heading count from tree.
        try:
            tree = doc_svc.build_heading_tree(doc)
            heading_count = _count_headings(tree)
        except Exception:
            heading_count = 0

        # Page count (approximate via view cursor).
        page_count = 0
        try:
            vc = doc.getCurrentController().getViewCursor()
            vc.jumpToLastPage()
            page_count = vc.getPage()
        except Exception:
            pass

        return {
            "status": "ok",
            "character_count": char_count,
            "word_count": word_count,
            "paragraph_count": para_count,
            "page_count": page_count,
            "heading_count": heading_count,
        }


def _count_headings(nodes):
    """Recursively count heading nodes in a nested list."""
    count = 0
    for node in nodes:
        count += 1
        count += _count_headings(node.get("children", []))
    return count

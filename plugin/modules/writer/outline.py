"""Writer outline / heading navigation tools."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.writer")


class GetDocumentOutline(ToolBase):
    """Return the heading tree (outline) of a Writer document."""

    name = "get_document_outline"
    description = "Returns the document outline (headings hierarchy)."
    parameters = {
        "type": "object",
        "properties": {
            "max_depth": {
                "type": "integer",
                "description": "Maximum heading depth to return (default: all).",
            },
        },
        "required": [],
    }
    doc_types = ["writer"]
    tier = "core"

    def execute(self, ctx, **kwargs):
        doc_svc = ctx.services.document
        tree = doc_svc.build_heading_tree(ctx.doc)
        max_depth = kwargs.get("max_depth")
        if max_depth is not None:
            tree = [_prune_tree(node, max_depth) for node in tree]
        return {"status": "ok", "outline": tree}


class GetHeadingContent(ToolBase):
    """Return content under a heading identified by its path."""

    name = "get_heading_content"
    intent = "navigate"
    description = (
        "Returns content under a heading identified by its path "
        "(e.g. '1.2' for the second child of the first heading)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "heading_path": {
                "type": "string",
                "description": "Dot-separated heading path, e.g. '1', '2.3'.",
            },
            "max_paragraphs": {
                "type": "integer",
                "description": "Maximum paragraphs to return (default: 50).",
            },
        },
        "required": ["heading_path"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        heading_path = kwargs["heading_path"]
        max_paragraphs = kwargs.get("max_paragraphs", 50)
        doc_svc = ctx.services.document

        # Navigate the heading tree by path indices.
        tree = doc_svc.build_heading_tree(ctx.doc)
        parts = _parse_path(heading_path)
        if parts is None:
            return {
                "status": "error",
                "message": "Invalid heading path: %s" % heading_path,
            }

        node = _walk_tree(tree, parts)
        if node is None:
            return {
                "status": "error",
                "message": "Heading '%s' not found." % heading_path,
            }

        # Read paragraphs under that heading.
        para_ranges = doc_svc.get_paragraph_ranges(ctx.doc)
        heading_level = node.get("level", 1)
        heading_title = node.get("title", "")

        # Find the paragraph index of this heading by scanning for a
        # matching title and level.
        start_idx = _find_heading_para_index(
            para_ranges, heading_title, heading_level
        )
        if start_idx is None:
            return {
                "status": "error",
                "message": "Could not locate heading in paragraphs.",
            }

        # Collect body paragraphs until the next heading of equal or
        # higher level (or end of document).
        paragraphs = []
        for i in range(start_idx + 1, len(para_ranges)):
            if len(paragraphs) >= max_paragraphs:
                break
            p = para_ranges[i]
            if not hasattr(p, "getString"):
                continue
            try:
                level = p.getPropertyValue("OutlineLevel")
            except Exception:
                level = 0
            if level > 0 and level <= heading_level:
                break
            paragraphs.append(p.getString())

        return {
            "status": "ok",
            "heading_path": heading_path,
            "heading_title": heading_title,
            "paragraphs": paragraphs,
            "sub_headings": node.get("children", []),
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _prune_tree(node, max_depth, current_depth=1):
    """Remove children deeper than *max_depth*."""
    pruned = dict(node)
    if current_depth >= max_depth:
        pruned["children"] = []
    else:
        pruned["children"] = [
            _prune_tree(c, max_depth, current_depth + 1)
            for c in node.get("children", [])
        ]
    return pruned


def _parse_path(path_str):
    """Parse ``'1.2.3'`` into ``[1, 2, 3]`` (1-based). Returns None on error."""
    try:
        parts = [int(p) for p in path_str.strip().split(".")]
        if all(p >= 1 for p in parts):
            return parts
    except (ValueError, AttributeError):
        pass
    return None


def _walk_tree(tree, parts):
    """Walk a nested heading tree by 1-based indices.

    *tree* is a list of top-level heading dicts, each with a
    ``'children'`` list.
    """
    nodes = tree
    node = None
    for idx in parts:
        if idx < 1 or idx > len(nodes):
            return None
        node = nodes[idx - 1]
        nodes = node.get("children", [])
    return node


def _find_heading_para_index(para_ranges, title, level):
    """Scan paragraph ranges for a heading matching *title* and *level*."""
    for i, p in enumerate(para_ranges):
        if not hasattr(p, "getString"):
            continue
        try:
            p_level = p.getPropertyValue("OutlineLevel")
        except Exception:
            continue
        if p_level == level and p.getString().strip() == title:
            return i
    return None

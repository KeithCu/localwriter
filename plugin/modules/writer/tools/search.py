"""Writer search tools: search_in_document, replace_in_document."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.writer")


class SearchInDocument(ToolBase):
    """Search for text in a document with paragraph context."""

    name = "search_in_document"
    description = (
        "Search for text in the document using LibreOffice native search. "
        "Returns matches with surrounding paragraph text for context."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Search string or regex pattern.",
            },
            "regex": {
                "type": "boolean",
                "description": "Use regular expression (default: false).",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive search (default: false).",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default: 20).",
            },
            "context_paragraphs": {
                "type": "integer",
                "description": (
                    "Number of paragraphs of context around each match "
                    "(default: 1)."
                ),
            },
        },
        "required": ["pattern"],
    }
    doc_types = ["writer"]
    tier = "core"

    def execute(self, ctx, **kwargs):
        import re as re_mod

        pattern = kwargs.get("pattern", "")
        if not pattern:
            return {"status": "error", "message": "pattern is required."}

        use_regex = kwargs.get("regex", False)
        case_sensitive = kwargs.get("case_sensitive", False)
        max_results = kwargs.get("max_results", 20)
        context_paragraphs = kwargs.get("context_paragraphs", 1)

        doc = ctx.doc
        doc_svc = ctx.services.document
        para_ranges = doc_svc.get_paragraph_ranges(doc)
        para_count = len(para_ranges)

        try:
            # Read paragraph texts once
            para_texts = []
            for para in para_ranges:
                try:
                    if para.supportsService(
                        "com.sun.star.text.Paragraph"
                    ):
                        para_texts.append(para.getString())
                    else:
                        para_texts.append("")
                except Exception:
                    para_texts.append("")

            # Compile regex if needed
            if use_regex:
                flags = 0 if case_sensitive else re_mod.IGNORECASE
                try:
                    compiled = re_mod.compile(pattern, flags)
                except re_mod.error as e:
                    return {
                        "status": "error",
                        "error": "Invalid regex: %s" % e,
                    }

            # Search within paragraphs
            matches = []
            total_count = 0

            for i, ptext in enumerate(para_texts):
                if not ptext:
                    continue

                if use_regex:
                    for m in compiled.finditer(ptext):
                        total_count += 1
                        if len(matches) < max_results:
                            matches.append(
                                _build_match(
                                    m.group(), i,
                                    context_paragraphs, para_count,
                                    para_texts,
                                )
                            )
                else:
                    haystack = ptext if case_sensitive else ptext.lower()
                    needle = (
                        pattern if case_sensitive else pattern.lower()
                    )
                    step = max(1, len(needle))
                    pos = 0
                    while True:
                        pos = haystack.find(needle, pos)
                        if pos == -1:
                            break
                        total_count += 1
                        if len(matches) < max_results:
                            matches.append(
                                _build_match(
                                    ptext[pos:pos + len(pattern)], i,
                                    context_paragraphs, para_count,
                                    para_texts,
                                )
                            )
                        pos += step

            return {
                "status": "ok",
                "matches": matches,
                "count": total_count,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


def _build_match(text, para_idx, ctx_paras, para_count, para_texts):
    """Build a single match result with context paragraphs."""
    ctx_lo = max(0, para_idx - ctx_paras)
    ctx_hi = min(para_count, para_idx + ctx_paras + 1)
    context = [
        {"index": j, "text": para_texts[j]}
        for j in range(ctx_lo, ctx_hi)
    ]
    return {
        "text": text,
        "paragraph_index": para_idx,
        "context": context,
    }


class ReplaceInDocument(ToolBase):
    """Find and replace text preserving formatting."""

    name = "replace_in_document"
    description = (
        "Find and replace text in the document with regex support. "
        "Preserves existing formatting. Returns count of replacements."
    )
    parameters = {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Text or regex pattern to find.",
            },
            "replace": {
                "type": "string",
                "description": "Replacement text.",
            },
            "regex": {
                "type": "boolean",
                "description": "Use regular expression (default: false).",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive matching (default: false).",
            },
            "replace_all": {
                "type": "boolean",
                "description": (
                    "Replace all occurrences (default: true). "
                    "Set to false to replace only the first match."
                ),
            },
        },
        "required": ["search", "replace"],
    }
    doc_types = ["writer"]
    tier = "core"
    is_mutation = True

    def execute(self, ctx, **kwargs):
        search = kwargs.get("search", "")
        replace = kwargs.get("replace", "")
        if not search:
            return {"status": "error", "message": "search is required."}

        regex = kwargs.get("regex", False)
        case_sensitive = kwargs.get("case_sensitive", False)
        replace_all = kwargs.get("replace_all", True)

        doc = ctx.doc

        try:
            replace_desc = doc.createReplaceDescriptor()
            replace_desc.SearchString = search
            replace_desc.ReplaceString = replace
            replace_desc.SearchRegularExpression = bool(regex)
            replace_desc.SearchCaseSensitive = bool(case_sensitive)

            if replace_all:
                count = doc.replaceAll(replace_desc)
            else:
                # Replace only the first match
                found = doc.findFirst(replace_desc)
                if found is not None:
                    found.setString(replace)
                    count = 1
                else:
                    count = 0

            # Invalidate document cache after edits
            if count > 0:
                doc_svc = ctx.services.document
                doc_svc.invalidate_cache(doc)

            return {
                "status": "ok",
                "replacements": count,
                "search": search,
                "replace": replace,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

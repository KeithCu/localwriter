"""Document context strategies for the chatbot.

Builds context strings injected into the LLM conversation via
``ChatSession.update_document_context()``. Each strategy produces
a different level of detail depending on document size.

Strategies
----------
full
    Entire document text (truncated at *max_context*).
    Best for small documents (< 4000 chars).
page
    Pages around the current selection / cursor.
    Good for medium documents.
tree
    Heading outline + targeted excerpt with selection markers.
    Good for large structured documents.
stats
    Word/heading counts + outline + selection only.
    Fallback for very large documents.
auto
    Chooses automatically based on document length.
"""

import logging

log = logging.getLogger("localwriter.chatbot.context")

# Size thresholds for auto strategy (chars)
_FULL_THRESHOLD = 4000
_PAGE_THRESHOLD = 20000


def build_context(doc, services, strategy="auto", max_context=8000):
    """Build a document context string for the LLM.

    Args:
        doc: UNO document model.
        services: ServiceRegistry.
        strategy: ``"auto"``, ``"full"``, ``"page"``, ``"tree"``, ``"stats"``.
        max_context: Max characters for the context string.

    Returns:
        Context string ready for ``ChatSession.update_document_context()``,
        or empty string if no context could be built.
    """
    if not doc:
        return ""

    doc_svc = services.get("document")
    if not doc_svc:
        return ""

    doc_type = doc_svc.detect_doc_type(doc)
    if doc_type != "writer":
        # For Calc/Draw, use existing context builder
        return doc_svc.get_document_context_for_chat(doc, max_context)

    if strategy == "auto":
        strategy = _auto_strategy(doc, doc_svc)

    builders = {
        "full": _writer_context_full,
        "page": _writer_context_page,
        "tree": _writer_context_tree,
        "stats": _writer_context_stats,
    }
    builder = builders.get(strategy, _writer_context_full)
    try:
        return builder(doc, doc_svc, services, max_context)
    except Exception:
        log.exception("Context strategy '%s' failed, falling back to full",
                      strategy)
        try:
            return _writer_context_full(doc, doc_svc, services, max_context)
        except Exception:
            return ""


def _auto_strategy(doc, doc_svc):
    """Choose strategy based on document length."""
    doc_len = doc_svc.get_document_length(doc)
    if doc_len <= _FULL_THRESHOLD:
        return "full"
    headings = doc_svc.build_heading_tree(doc)
    if doc_len <= _PAGE_THRESHOLD:
        return "page"
    if headings:
        return "tree"
    return "page"


# ── Full strategy ────────────────────────────────────────────────────


def _writer_context_full(doc, doc_svc, services, max_context):
    """Full document text with selection markers."""
    return doc_svc.get_document_context_for_chat(doc, max_context)


# ── Page strategy ────────────────────────────────────────────────────


def _get_cursor_page(doc):
    """Return (page_number, total_pages) for the current cursor."""
    try:
        controller = doc.getCurrentController()
        vc = controller.getViewCursor()
        return vc.getPage(), 0  # total filled later
    except Exception:
        return 1, 0


def _get_selection_text(doc):
    """Return the currently selected text, or empty string."""
    try:
        controller = doc.getCurrentController()
        selection = controller.getSelection()
        if selection and hasattr(selection, "getCount"):
            text_range = selection.getByIndex(0)
            return text_range.getString()
        if selection and hasattr(selection, "getString"):
            return selection.getString()
    except Exception:
        pass
    return ""


def _writer_context_page(doc, doc_svc, services, max_context):
    """Pages around the cursor/selection.

    Extracts paragraphs visible on the current page and its neighbours.
    """
    cursor_page, _ = _get_cursor_page(doc)
    page_count = doc_svc.get_page_count(doc)
    doc_len = doc_svc.get_document_length(doc)
    selection = _get_selection_text(doc)

    # Determine page range (current +/- 1)
    page_start = max(1, cursor_page - 1)
    page_end = min(page_count, cursor_page + 1)

    # Collect paragraphs for those pages
    para_ranges = doc_svc.get_paragraph_ranges(doc)
    if not para_ranges:
        return _writer_context_full(doc, doc_svc, services, max_context)

    # Find paragraphs on target pages
    page_paras = []
    chars = 0
    for i, para in enumerate(para_ranges):
        para_page = doc_svc.get_page_for_paragraph(doc, i)
        if page_start <= para_page <= page_end:
            text = para.getString()
            page_paras.append((i, para_page, text))
            chars += len(text)
            if chars > max_context:
                break

    if not page_paras:
        return _writer_context_full(doc, doc_svc, services, max_context)

    # Build context
    parts = []
    parts.append("Document: %d chars, %d pages." % (doc_len, page_count))
    parts.append("Showing pages %d-%d (cursor on page %d)."
                 % (page_start, page_end, cursor_page))

    if selection:
        sel_preview = selection[:200]
        if len(selection) > 200:
            sel_preview += "..."
        parts.append("\n[SELECTION]\n%s\n[/SELECTION]" % sel_preview)

    parts.append("\n[PAGE CONTENT]")
    current_page = None
    for _, ppage, text in page_paras:
        if ppage != current_page:
            parts.append("\n--- Page %d ---" % ppage)
            current_page = ppage
        parts.append(text)
    parts.append("[/PAGE CONTENT]")

    # Add outline if available
    headings = doc_svc.build_heading_tree(doc)
    if headings:
        outline = _format_outline(headings, max_depth=2)
        if outline:
            parts.append("\n[DOCUMENT OUTLINE]\n%s\n[/OUTLINE]" % outline)

    return "\n".join(parts)


# ── Tree strategy ────────────────────────────────────────────────────


def _format_outline(headings, indent=0, max_depth=None):
    """Format heading tree as indented text."""
    lines = []
    for h in headings:
        level = h.get("level", 1)
        title = h.get("title", "")
        prefix = "  " * indent
        lines.append("%s%s %s" % (prefix, "#" * level, title))
        children = h.get("children", [])
        if children and (max_depth is None or indent < max_depth):
            lines.append(
                _format_outline(children, indent + 1, max_depth))
    return "\n".join(lines)


def _writer_context_tree(doc, doc_svc, services, max_context):
    """Heading outline + excerpt around selection."""
    doc_len = doc_svc.get_document_length(doc)
    headings = doc_svc.build_heading_tree(doc)
    selection = _get_selection_text(doc)
    page_count = doc_svc.get_page_count(doc)

    parts = []
    parts.append("Document: %d chars, %d pages, %d headings."
                 % (doc_len, page_count, _count_headings(headings)))

    # Full outline
    if headings:
        outline = _format_outline(headings)
        parts.append("\n[DOCUMENT OUTLINE]\n%s\n[/OUTLINE]" % outline)
    else:
        parts.append("\n(No heading structure)")

    # Selection context
    if selection:
        sel_budget = min(len(selection), max_context // 2)
        sel_text = selection[:sel_budget]
        if len(selection) > sel_budget:
            sel_text += "\n[... selection truncated, %d chars total ...]" % len(selection)
        parts.append("\n[SELECTION]\n%s\n[/SELECTION]" % sel_text)

    # Excerpt around cursor (paragraphs near cursor, up to budget)
    remaining = max_context - sum(len(p) for p in parts)
    if remaining > 500:
        excerpt = _get_cursor_excerpt(doc, doc_svc, remaining)
        if excerpt:
            parts.append("\n[EXCERPT AROUND CURSOR]\n%s\n[/EXCERPT]"
                         % excerpt)

    return "\n".join(parts)


def _count_headings(headings):
    """Count total headings in a nested tree."""
    count = 0
    for h in headings:
        count += 1
        count += _count_headings(h.get("children", []))
    return count


def _get_cursor_excerpt(doc, doc_svc, max_chars):
    """Get paragraphs around the cursor position."""
    try:
        controller = doc.getCurrentController()
        vc = controller.getViewCursor()
        text = doc.getText()
        para_ranges = doc_svc.get_paragraph_ranges(doc)
        cursor_idx = doc_svc.find_paragraph_for_range(
            vc.getStart(), para_ranges, text)
        if cursor_idx < 0:
            cursor_idx = 0

        # Collect paragraphs around cursor
        radius = 10
        start = max(0, cursor_idx - radius)
        end = min(len(para_ranges), cursor_idx + radius + 1)

        lines = []
        chars = 0
        for i in range(start, end):
            ptext = para_ranges[i].getString()
            if i == cursor_idx:
                ptext = "[>>> CURSOR <<<] " + ptext
            lines.append(ptext)
            chars += len(ptext)
            if chars > max_chars:
                break

        return "\n".join(lines)
    except Exception:
        return ""


# ── Stats strategy ───────────────────────────────────────────────────


def _writer_context_stats(doc, doc_svc, services, max_context):
    """Minimal context: stats + outline + selection only."""
    doc_len = doc_svc.get_document_length(doc)
    headings = doc_svc.build_heading_tree(doc)
    selection = _get_selection_text(doc)
    page_count = doc_svc.get_page_count(doc)

    # Word count estimate
    full_text = doc_svc.get_full_text(doc, max_chars=doc_len)
    word_count = len(full_text.split()) if full_text else 0

    parts = []
    parts.append("Document stats: %d chars, ~%d words, %d pages, %d headings."
                 % (doc_len, word_count, page_count,
                    _count_headings(headings)))

    if headings:
        outline = _format_outline(headings, max_depth=3)
        parts.append("\n[DOCUMENT OUTLINE]\n%s\n[/OUTLINE]" % outline)

    if selection:
        sel_budget = min(len(selection), max_context // 2)
        sel_text = selection[:sel_budget]
        if len(selection) > sel_budget:
            sel_text += "\n[... selection truncated ...]"
        parts.append("\n[SELECTION]\n%s\n[/SELECTION]" % sel_text)

    return "\n".join(parts)

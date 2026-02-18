"""Document helpers for LocalWriter."""
from core.calc_bridge import CalcBridge
from core.calc_sheet_analyzer import SheetAnalyzer


def get_full_document_text(model, max_chars=8000):
    """Get full document text for Writer or summary for Calc, truncated to max_chars."""
    try:
        if hasattr(model, "getSheets"):
            # Calc document
            import uno
            bridge = CalcBridge(uno.getComponentContext())
            analyzer = SheetAnalyzer(bridge)
            summary = analyzer.get_sheet_summary()
            text = f"Sheet: {summary['sheet_name']}\nUsed Range: {summary['used_range']}\n"
            text += f"Columns: {', '.join(filter(None, summary['headers']))}\n"
            # Maybe add some preview rows?
            return text
        
        text = model.getText()
        # ... rest of Writer logic
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        full = cursor.getString()
        if len(full) > max_chars:
            full = full[:max_chars] + "\n\n[... document truncated ...]"
        return full
    except Exception:
        return ""


def get_document_end(model, max_chars=4000):
    """Get the last max_chars of the document."""
    try:
        text = model.getText()
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        cursor.gotoStart(True)  # expand backward to select from start to end
        full = cursor.getString()
        if len(full) <= max_chars:
            return full
        return full[-max_chars:]
    except Exception:
        return ""


# goRight(nCount, bExpand) takes short; max 32767 per call
_GO_RIGHT_CHUNK = 8192


def get_document_length(model):
    """Return total character length of the document. Returns 0 on error."""
    try:
        text = model.getText()
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        return len(cursor.getString())
    except Exception:
        return 0


def get_text_cursor_at_range(model, start_offset, end_offset):
    """Return a text cursor that selects the character range [start_offset, end_offset).
    The cursor is positioned at start and expanded to end so caller can setString('') and insert.
    goRight is used in chunks because UNO's goRight takes short (max 32767).
    Returns None on error or invalid range."""
    try:
        doc_len = get_document_length(model)
        start_offset = max(0, min(start_offset, doc_len))
        end_offset = max(0, min(end_offset, doc_len))
        if start_offset > end_offset:
            start_offset, end_offset = end_offset, start_offset
        text = model.getText()
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        # Move to start_offset in chunks
        remaining = start_offset
        while remaining > 0:
            n = min(remaining, _GO_RIGHT_CHUNK)
            cursor.goRight(n, False)
            remaining -= n
        # Expand selection by (end_offset - start_offset)
        remaining = end_offset - start_offset
        while remaining > 0:
            n = min(remaining, _GO_RIGHT_CHUNK)
            cursor.goRight(n, True)
            remaining -= n
        return cursor
    except Exception:
        return None


def get_selection_range(model):
    """Return (start_offset, end_offset) character positions into the document.
    Cursor (no selection) = same start and end. Returns (0, 0) on error or no text range."""
    try:
        sel = model.getCurrentController().getSelection()
        if not sel or sel.getCount() == 0:
            # No selection: use view cursor for insertion point
            vc = model.getCurrentController().getViewCursor()
            rng = vc
        else:
            rng = sel.getByIndex(0)
        if not rng or not hasattr(rng, "getStart") or not hasattr(rng, "getEnd"):
            return (0, 0)
        text = model.getText()
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoRange(rng.getStart(), True)
        start_offset = len(cursor.getString())
        cursor.gotoStart(False)
        cursor.gotoRange(rng.getEnd(), True)
        end_offset = len(cursor.getString())
        return (start_offset, end_offset)
    except Exception:
        return (0, 0)


def get_document_context_for_chat(model, max_context=8000, include_end=True, include_selection=True, ctx=None):
    """Build a single context string for chat. Handles Writer and Calc.
    ctx: component context (required for Calc and Draw documents)."""
    if hasattr(model, "getSheets"):
        return get_calc_context_for_chat(model, max_context, ctx)
    
    if hasattr(model, "getDrawPages"):
        return get_draw_context_for_chat(model, max_context, ctx)
    
    # Original Writer logic
    try:
        text = model.getText()
        # ... (rest of the function)
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        full = cursor.getString()
        doc_len = len(full)
    except Exception:
        return "Document length: 0.\n\n[DOCUMENT START]\n(empty)\n[END DOCUMENT]"

    # Selection/cursor range; cap selection span for very long selections (e.g. 100k chars)
    start_offset, end_offset = (0, 0)
    if include_selection:
        start_offset, end_offset = get_selection_range(model)
        # Clamp to document bounds
        start_offset = max(0, min(start_offset, doc_len))
        end_offset = max(0, min(end_offset, doc_len))
        if start_offset > end_offset:
            start_offset, end_offset = end_offset, start_offset
        # Optional: cap selection span so we don't force huge context (e.g. 2000 chars max span for "selection" in excerpts)
        max_selection_span = 2000
        if end_offset - start_offset > max_selection_span:
            end_offset = start_offset + max_selection_span

    # Budget split: half for start, half for end when include_end
    if include_end and doc_len > (max_context // 2):
        start_chars = max_context // 2
        end_chars = max_context - start_chars
        start_excerpt = full[:start_chars]
        end_excerpt = full[-end_chars:]
        # Inject markers into start excerpt
        start_excerpt = _inject_markers_into_excerpt(
            start_excerpt, 0, start_chars, start_offset, end_offset, "[DOCUMENT START]\n", "\n[DOCUMENT END]"
        )
        # Inject markers into end excerpt (offsets relative to document; excerpt starts at doc_len - end_chars)
        end_excerpt = _inject_markers_into_excerpt(
            end_excerpt, doc_len - end_chars, doc_len, start_offset, end_offset, "[DOCUMENT END]\n", "\n[END DOCUMENT]"
        )
        middle_note = "\n\n[... middle of document omitted ...]\n\n" if doc_len > max_context else ""
        return (
            "Document length: %d characters.\n\n%s%s%s"
            % (doc_len, start_excerpt, middle_note, end_excerpt)
        )
    else:
        # Short doc or start-only: one block
        take = min(doc_len, max_context)
        excerpt = full[:take]
        if doc_len > max_context:
            excerpt += "\n\n[... document truncated ...]"
        content_len = take  # character range we're showing (before truncation message)
        excerpt = _inject_markers_into_excerpt(
            excerpt, 0, content_len, start_offset, end_offset, "[DOCUMENT START]\n", "\n[END DOCUMENT]"
        )
        return "Document length: %d characters.\n\n%s" % (doc_len, excerpt)


def get_calc_context_for_chat(model, max_context=8000):
    """Get context summary for a Calc spreadsheet."""
    try:
        bridge = CalcBridge(model)
        analyzer = SheetAnalyzer(bridge)
        summary = analyzer.get_sheet_summary()

        ctx_str = f"Spreadsheet Document: {model.getURL() or 'Untitled'}\n"
        ctx_str += f"Active Sheet: {summary['sheet_name']}\n"
        ctx_str += f"Used Range: {summary['used_range']} ({summary['row_count']} rows x {summary['col_count']} columns)\n"
        ctx_str += f"Columns: {', '.join([str(h) for h in summary['headers'] if h])}\n"

        # Add selection context if available
        controller = model.getCurrentController()
        selection = controller.getSelection()
        if selection:
            if hasattr(selection, "getRangeAddress"):
                addr = selection.getRangeAddress()
                from core.calc_address_utils import index_to_column
                sel_range = f"{index_to_column(addr.StartColumn)}{addr.StartRow + 1}:{index_to_column(addr.EndColumn)}{addr.EndRow + 1}"
                ctx_str += f"Current Selection: {sel_range}\n"

                # Check for selected values if small
                if (addr.EndRow - addr.StartRow + 1) * (addr.EndColumn - addr.StartColumn + 1) < 100:
                    from core.calc_inspector import CellInspector
                    inspector = CellInspector(bridge)
                    cells = inspector.read_range(sel_range)
                    ctx_str += "Selection Content (CSV-like):\n"
                    for row in cells:
                        ctx_str += ", ".join([str(c['value']) if c['value'] is not None else "" for c in row]) + "\n"

        return ctx_str
    except Exception as e:
        return f"Error getting Calc context: {e}"


def get_draw_context_for_chat(model, max_context=8000, ctx=None):
    """Get context summary for a Draw/Impress document. ctx: component context."""
    if ctx is None:
        raise ValueError("ctx is required for get_draw_context_for_chat")
    try:
        from core.draw_bridge import DrawBridge
        bridge = DrawBridge(ctx)
        doc = model
        pages = bridge.get_pages(doc)
        active_page = bridge.get_active_page(doc)
        
        ctx_str = f"Draw/Impress Document: {doc.getURL() or 'Untitled'}\n"
        ctx_str += f"Total Pages: {pages.getCount()}\n"
        
        # Get index of active page
        active_page_idx = -1
        for i in range(pages.getCount()):
            # Using queryInterface style check if possible or just comparison
            if pages.getByIndex(i) == active_page:
                active_page_idx = i
                break
        
        ctx_str += f"Active Page Index: {active_page_idx}\n"
        
        # Summarize shapes on active page
        if active_page:
            shapes = bridge.get_shapes(active_page)
            ctx_str += f"\nShapes on Page {active_page_idx}:\n"
            for i, s in enumerate(shapes):
                type_name = s.getShapeType().split('.')[-1]
                pos = s.getPosition()
                size = s.getSize()
                ctx_str += f"- [{i}] {type_name}: pos({pos.X}, {pos.Y}) size({size.Width}x{size.Height})"
                if hasattr(s, "getString"):
                    text = s.getString()
                    if text:
                        # Limit text length to avoid context overflow
                        ctx_str += f" text: \"{text[:200]}\""
                ctx_str += "\n"
        
        return ctx_str
    except Exception as e:
        return f"Error getting Draw context: {e}"


def _inject_markers_into_excerpt(excerpt_text, excerpt_start, excerpt_end, sel_start, sel_end, prefix, suffix):
    # ...
    """Inject [SELECTION_START] and [SELECTION_END] at character positions relative to excerpt.
    excerpt_start/excerpt_end are the document character range this excerpt covers.
    sel_start/sel_end are the selection/cursor range in document coordinates."""
    if sel_start >= excerpt_end or sel_end <= excerpt_start:
        # Selection does not overlap this excerpt (or both markers in same position outside)
        return prefix + excerpt_text + suffix
    # Map to excerpt-relative indices
    local_start = max(0, sel_start - excerpt_start)
    local_end = min(len(excerpt_text), sel_end - excerpt_start)
    # Build result with markers inserted (order: text before start, START, text between, END, text after)
    before = excerpt_text[:local_start]
    between = excerpt_text[local_start:local_end]
    after = excerpt_text[local_end:]
    out = prefix + before + "[SELECTION_START]" + between + "[SELECTION_END]" + after + suffix
    return out

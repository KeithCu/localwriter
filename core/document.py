"""Document helpers for LocalWriter."""


def get_full_document_text(model, max_chars=8000):
    """Get full document text for Writer, truncated to max_chars."""
    try:
        text = model.getText()
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        full = cursor.getString()
        if len(full) > max_chars:
            full = full[:max_chars] + "\n\n[... document truncated ...]"
        return full
    except Exception:
        return ""

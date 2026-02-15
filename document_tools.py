# document_tools.py — Writer document manipulation tools for AI chat sidebar.
# Provides JSON tool schemas (WRITER_TOOLS) and executor functions for the
# OpenAI-compatible tool-calling protocol.
# Exposed tool list is markdown-centric: get_markdown, apply_markdown only.

import json

from core.logging import agent_log

from markdown_support import MARKDOWN_TOOLS, tool_get_markdown, tool_apply_markdown, tool_find_text


# ---------------------------------------------------------------------------
# Tool list exposed to the AI (markdown-centric)
# ---------------------------------------------------------------------------

WRITER_TOOLS = list(MARKDOWN_TOOLS)


# ---------------------------------------------------------------------------
# NOT CURRENTLY USED — Legacy tool schemas and executors. Not in WRITER_TOOLS;
# TOOL_DISPATCH entries for these are commented out below. Kept for possible future use.
# ---------------------------------------------------------------------------

def _tool_error(message):
    """Helper to create error response."""
    return json.dumps({"status": "error", "message": message})


def tool_replace_text(model, ctx, args):
    """Replace one or all occurrences. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    all_matches = args.get("all_matches", False)
    case_sensitive = args.get("case_sensitive", True)
    if all_matches:
        rd = model.createReplaceDescriptor()
        rd.SearchString = args["search"]
        rd.ReplaceString = args["replacement"]
        rd.SearchCaseSensitive = case_sensitive
        rd.SearchRegularExpression = False
        count = model.replaceAll(rd)
        return json.dumps({"status": "ok", "message": "Replaced %d occurrence(s)." % count})
    else:
        sd = model.createSearchDescriptor()
        sd.SearchString = args["search"]
        sd.SearchRegularExpression = False
        sd.SearchCaseSensitive = case_sensitive
        found = model.findFirst(sd)
        if found:
            found.setString(args["replacement"])
            return json.dumps({"status": "ok", "message": "Replaced 1 occurrence."})
        return json.dumps({"status": "not_found", "message": "Text not found in document."})


def tool_insert_text(model, ctx, args):
    """Insert text at beginning or end. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    text_obj = model.getText()
    position = args["position"]
    insert_str = args["text"]
    cursor = text_obj.createTextCursor()
    if position == "beginning":
        cursor.gotoStart(False)
    elif position == "end":
        cursor.gotoEnd(False)
    else:
        return _tool_error("Unknown position: %s" % position)
    text_obj.insertString(cursor, insert_str, False)
    return json.dumps({"status": "ok", "message": "Inserted text at %s." % position})


def tool_get_selection(model, ctx, args):
    """Return currently selected text. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    try:
        sel = model.getCurrentController().getSelection()
        if sel and sel.getCount() > 0:
            selected = sel.getByIndex(0).getString()
            return json.dumps({"status": "ok", "text": selected})
    except Exception:
        pass
    return json.dumps({"status": "ok", "text": ""})


def tool_replace_selection(model, ctx, args):
    """Replace selected text. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    try:
        sel = model.getCurrentController().getSelection()
        if sel and sel.getCount() > 0:
            rng = sel.getByIndex(0)
            old_len = len(rng.getString())
            rng.setString(args["new_text"])
            return json.dumps({"status": "ok", "message": "Replaced selection (%d chars)." % old_len})
    except Exception:
        pass
    return json.dumps({"status": "no_selection", "message": "No text is selected."})


def tool_format_text(model, ctx, args):
    """Find text and apply character formatting. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    sd = model.createSearchDescriptor()
    sd.SearchString = args["search"]
    sd.SearchRegularExpression = False
    sd.SearchCaseSensitive = True
    found = model.findFirst(sd)
    if not found:
        return json.dumps({"status": "not_found", "message": "Text not found in document."})
    applied = []
    if "bold" in args:
        found.setPropertyValue("CharWeight", 150.0 if args["bold"] else 100.0)
        applied.append("bold" if args["bold"] else "unbold")
    if "italic" in args:
        from com.sun.star.awt.FontSlant import ITALIC, NONE as SLANT_NONE
        found.setPropertyValue("CharPosture", ITALIC if args["italic"] else SLANT_NONE)
        applied.append("italic" if args["italic"] else "unitalic")
    if "underline" in args:
        found.setPropertyValue("CharUnderline", 1 if args["underline"] else 0)
        applied.append("underline" if args["underline"] else "no underline")
    if "strikethrough" in args:
        found.setPropertyValue("CharStrikeout", 1 if args["strikethrough"] else 0)
        applied.append("strikethrough" if args["strikethrough"] else "no strikethrough")
    if "font_size" in args:
        found.setPropertyValue("CharHeight", float(args["font_size"]))
        applied.append("size %spt" % args["font_size"])
    if "font_color" in args:
        hex_color = str(args["font_color"]).lstrip("#")
        color_int = int(hex_color, 16)
        found.setPropertyValue("CharColor", color_int)
        applied.append("color #%s" % hex_color)
    if not applied:
        return json.dumps({"status": "ok", "message": "Text found but no formatting properties specified."})
    return json.dumps({"status": "ok", "message": "Applied %s to '%s'." % (", ".join(applied), args["search"])})


def tool_set_paragraph_style(model, ctx, args):
    """Set paragraph style. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    style_name = args["style_name"]
    all_matches = args.get("all_matches", False)
    search_text = args["search"]
    text_obj = model.getText()
    enum = text_obj.createEnumeration()
    count = 0
    while enum.hasMoreElements():
        para = enum.nextElement()
        if not hasattr(para, "getString"):
            continue
        if search_text in para.getString():
            try:
                para.setPropertyValue("ParaStyleName", style_name)
                count += 1
            except Exception as e:
                return _tool_error("Style '%s' not found or error: %s" % (style_name, e))
            if not all_matches:
                break
    if count == 0:
        return json.dumps({"status": "not_found", "message": "No paragraph containing '%s' found." % search_text})
    return json.dumps({"status": "ok", "message": "Applied '%s' to %d paragraph(s)." % (style_name, count)})


def tool_get_document_text(model, ctx, args):
    """Get full document text. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    text_obj = model.getText()
    cursor = text_obj.createTextCursor()
    cursor.gotoStart(False)
    cursor.gotoEnd(True)
    full_text = cursor.getString()
    max_chars = args.get("max_chars")
    if max_chars and len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "\n\n[... truncated ...]"
    return json.dumps({"status": "ok", "text": full_text, "length": len(full_text)})


# ---------------------------------------------------------------------------
# Tool dispatch table (only tools currently exposed to the AI)
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    "get_markdown": tool_get_markdown,
    "apply_markdown": tool_apply_markdown,
    "find_text": tool_find_text,
    # Unused (not in WRITER_TOOLS); uncomment to re-enable:
    # "get_selection": tool_get_selection,
    # "replace_text": tool_replace_text,
    # "insert_text": tool_insert_text,
    # "replace_selection": tool_replace_selection,
    # "format_text": tool_format_text,
    # "set_paragraph_style": tool_set_paragraph_style,
    # "get_document_text": tool_get_document_text,
}


def execute_tool(tool_name, arguments, model, ctx):
    """Execute a tool by name. Returns JSON result string."""
    func = TOOL_DISPATCH.get(tool_name)
    if not func:
        return json.dumps({"status": "error", "message": "Unknown tool: %s" % tool_name})
    try:
        result = func(model, ctx, arguments)
        agent_log("document_tools.py:execute_tool", "Tool result", data={"tool": tool_name, "result_snippet": (result or "")[:120]}, hypothesis_id="C,E")
        return result
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

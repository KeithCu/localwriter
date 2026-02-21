# core/writer_ops.py — Style, comment, track-changes, and table tool implementations.
# Ported from libreoffice-mcp-extension/pythonpath/uno_bridge.py and adapted to
# LocalWriter's function signatures: (model, ctx, args) -> JSON string.
# model = already-resolved document; ctx = component context.

import json

from core.logging import debug_log


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _err(message):
    return json.dumps({"status": "error", "message": message})


def _get_paragraph_ranges(doc):
    """Return list of top-level paragraph elements for anchor position lookup."""
    text = doc.getText()
    enum = text.createEnumeration()
    ranges = []
    while enum.hasMoreElements():
        ranges.append(enum.nextElement())
    return ranges


def _find_paragraph_for_range(match_range, para_ranges, text_obj=None):
    """Return the paragraph index that contains match_range, or 0 on failure."""
    try:
        if text_obj is None:
            text_obj = match_range.getText()
        match_start = match_range.getStart()
        for i, para in enumerate(para_ranges):
            try:
                cmp_start = text_obj.compareRegionStarts(match_start, para.getStart())
                cmp_end = text_obj.compareRegionStarts(match_start, para.getEnd())
                if cmp_start <= 0 and cmp_end >= 0:
                    return i
            except Exception:
                continue
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Style tools
# ---------------------------------------------------------------------------

def tool_list_styles(model, ctx, args):
    """List available styles in the document."""
    family = args.get("family", "ParagraphStyles")
    try:
        families = model.getStyleFamilies()
        if not families.hasByName(family):
            available = list(families.getElementNames())
            return json.dumps({"status": "error",
                               "message": "Unknown style family: %s" % family,
                               "available_families": available})
        style_family = families.getByName(family)
        styles = []
        for name in style_family.getElementNames():
            style = style_family.getByName(name)
            entry = {
                "name": name,
                "is_user_defined": style.isUserDefined(),
                "is_in_use": style.isInUse(),
            }
            try:
                entry["parent_style"] = style.getPropertyValue("ParentStyle")
            except Exception:
                pass
            styles.append(entry)
        return json.dumps({"status": "ok", "family": family,
                           "styles": styles, "count": len(styles)})
    except Exception as e:
        debug_log("tool_list_styles error: %s" % e, context="Chat")
        return _err(str(e))


def tool_get_style_info(model, ctx, args):
    """Get detailed properties of a named style."""
    style_name = args.get("style_name", "")
    family = args.get("family", "ParagraphStyles")
    if not style_name:
        return _err("style_name is required")
    try:
        families = model.getStyleFamilies()
        if not families.hasByName(family):
            return _err("Unknown style family: %s" % family)
        style_family = families.getByName(family)
        if not style_family.hasByName(style_name):
            return json.dumps({"status": "error",
                               "message": "Style '%s' not found in %s" % (style_name, family)})
        style = style_family.getByName(style_name)
        info = {
            "name": style_name,
            "family": family,
            "is_user_defined": style.isUserDefined(),
            "is_in_use": style.isInUse(),
        }
        props_to_read = {
            "ParagraphStyles": [
                "ParentStyle", "FollowStyle",
                "CharFontName", "CharHeight", "CharWeight",
                "ParaAdjust", "ParaTopMargin", "ParaBottomMargin",
            ],
            "CharacterStyles": [
                "ParentStyle", "CharFontName", "CharHeight",
                "CharWeight", "CharPosture", "CharColor",
            ],
        }
        for prop_name in props_to_read.get(family, []):
            try:
                info[prop_name] = style.getPropertyValue(prop_name)
            except Exception:
                pass
        return json.dumps({"status": "ok", **info})
    except Exception as e:
        debug_log("tool_get_style_info error: %s" % e, context="Chat")
        return _err(str(e))


# ---------------------------------------------------------------------------
# Comment tools
# ---------------------------------------------------------------------------

def tool_list_comments(model, ctx, args):
    """List all comments/annotations in the document."""
    try:
        fields = model.getTextFields()
        enum = fields.createEnumeration()
        para_ranges = _get_paragraph_ranges(model)
        text_obj = model.getText()
        comments = []
        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService("com.sun.star.text.textfield.Annotation"):
                continue
            try:
                author = field.getPropertyValue("Author")
            except Exception:
                author = ""
            content = ""
            try:
                content = field.getPropertyValue("Content")
            except Exception:
                pass
            name = ""
            parent_name = ""
            resolved = False
            try:
                name = field.getPropertyValue("Name")
            except Exception:
                pass
            try:
                parent_name = field.getPropertyValue("ParentName")
            except Exception:
                pass
            try:
                resolved = field.getPropertyValue("Resolved")
            except Exception:
                pass
            date_str = ""
            try:
                dt = field.getPropertyValue("DateTimeValue")
                date_str = "%04d-%02d-%02d %02d:%02d" % (
                    dt.Year, dt.Month, dt.Day, dt.Hours, dt.Minutes)
            except Exception:
                pass
            anchor = field.getAnchor()
            para_idx = _find_paragraph_for_range(anchor, para_ranges, text_obj)
            anchor_preview = anchor.getString()[:80]
            entry = {
                "author": author,
                "content": content,
                "date": date_str,
                "resolved": resolved,
                "paragraph_index": para_idx,
                "anchor_preview": anchor_preview,
                "is_reply": bool(parent_name),
            }
            if name:
                entry["name"] = name
            if parent_name:
                entry["parent_name"] = parent_name
            comments.append(entry)
        return json.dumps({"status": "ok", "comments": comments,
                           "count": len(comments)})
    except Exception as e:
        debug_log("tool_list_comments error: %s" % e, context="Chat")
        return _err(str(e))


def tool_add_comment(model, ctx, args):
    """Add a comment to the paragraph containing the given search text."""
    content = args.get("content", "")
    author = args.get("author", "AI")
    search_text = args.get("search_text", "")
    if not content:
        return _err("content is required")
    if not search_text:
        return _err("search_text is required")
    try:
        doc_text = model.getText()
        sd = model.createSearchDescriptor()
        sd.SearchString = search_text
        sd.SearchRegularExpression = False
        found = model.findFirst(sd)
        if found is None:
            return json.dumps({"status": "not_found",
                               "message": "Text '%s' not found" % search_text})
        annotation = model.createInstance("com.sun.star.text.textfield.Annotation")
        annotation.setPropertyValue("Author", author)
        annotation.setPropertyValue("Content", content)
        cursor = doc_text.createTextCursorByRange(found.getStart())
        doc_text.insertTextContent(cursor, annotation, False)
        return json.dumps({"status": "ok", "message": "Comment added",
                           "author": author})
    except Exception as e:
        debug_log("tool_add_comment error: %s" % e, context="Chat")
        return _err(str(e))


def tool_delete_comment(model, ctx, args):
    """Delete a comment and all its replies by comment name."""
    comment_name = args.get("comment_name", "")
    if not comment_name:
        return _err("comment_name is required")
    try:
        fields = model.getTextFields()
        enum = fields.createEnumeration()
        text_obj = model.getText()
        to_delete = []
        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService("com.sun.star.text.textfield.Annotation"):
                continue
            try:
                name = field.getPropertyValue("Name")
                parent = field.getPropertyValue("ParentName")
            except Exception:
                continue
            if name == comment_name or parent == comment_name:
                to_delete.append(field)
        for field in to_delete:
            text_obj.removeTextContent(field)
        return json.dumps({"status": "ok", "deleted": len(to_delete),
                           "comment_name": comment_name})
    except Exception as e:
        debug_log("tool_delete_comment error: %s" % e, context="Chat")
        return _err(str(e))


# ---------------------------------------------------------------------------
# Track-changes tools
# ---------------------------------------------------------------------------

def tool_set_track_changes(model, ctx, args):
    """Enable or disable change tracking in the document."""
    enabled = args.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.lower() not in ("false", "0", "no")
    try:
        model.setPropertyValue("RecordChanges", bool(enabled))
        return json.dumps({"status": "ok", "record_changes": bool(enabled)})
    except Exception as e:
        debug_log("tool_set_track_changes error: %s" % e, context="Chat")
        return _err(str(e))


def tool_get_tracked_changes(model, ctx, args):
    """List all tracked changes (redlines) in the document."""
    try:
        recording = False
        try:
            recording = model.getPropertyValue("RecordChanges")
        except Exception:
            pass
        if not hasattr(model, "getRedlines"):
            return json.dumps({"status": "ok", "recording": recording,
                               "changes": [], "count": 0,
                               "message": "Document does not expose redlines API"})
        redlines = model.getRedlines()
        enum = redlines.createEnumeration()
        changes = []
        while enum.hasMoreElements():
            redline = enum.nextElement()
            entry = {}
            for prop in ("RedlineType", "RedlineAuthor",
                         "RedlineComment", "RedlineIdentifier"):
                try:
                    entry[prop] = redline.getPropertyValue(prop)
                except Exception:
                    pass
            try:
                dt = redline.getPropertyValue("RedlineDateTime")
                entry["date"] = "%04d-%02d-%02d %02d:%02d" % (
                    dt.Year, dt.Month, dt.Day, dt.Hours, dt.Minutes)
            except Exception:
                pass
            changes.append(entry)
        return json.dumps({"status": "ok", "recording": recording,
                           "changes": changes, "count": len(changes)})
    except Exception as e:
        debug_log("tool_get_tracked_changes error: %s" % e, context="Chat")
        return _err(str(e))


def tool_accept_all_changes(model, ctx, args):
    """Accept all tracked changes in the document."""
    try:
        smgr = ctx.ServiceManager
        dispatcher = smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx)
        frame = model.getCurrentController().getFrame()
        dispatcher.executeDispatch(
            frame, ".uno:AcceptAllTrackedChanges", "", 0, ())
        return json.dumps({"status": "ok",
                           "message": "All tracked changes accepted."})
    except Exception as e:
        debug_log("tool_accept_all_changes error: %s" % e, context="Chat")
        return _err(str(e))


def tool_reject_all_changes(model, ctx, args):
    """Reject all tracked changes in the document."""
    try:
        smgr = ctx.ServiceManager
        dispatcher = smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx)
        frame = model.getCurrentController().getFrame()
        dispatcher.executeDispatch(
            frame, ".uno:RejectAllTrackedChanges", "", 0, ())
        return json.dumps({"status": "ok",
                           "message": "All tracked changes rejected."})
    except Exception as e:
        debug_log("tool_reject_all_changes error: %s" % e, context="Chat")
        return _err(str(e))


# ---------------------------------------------------------------------------
# Table tools
# ---------------------------------------------------------------------------

def tool_list_tables(model, ctx, args):
    """List all text tables in the document."""
    try:
        if not hasattr(model, "getTextTables"):
            return _err("Document does not support text tables")
        tables_sup = model.getTextTables()
        tables = []
        for name in tables_sup.getElementNames():
            table = tables_sup.getByName(name)
            tables.append({
                "name": name,
                "rows": table.getRows().getCount(),
                "cols": table.getColumns().getCount(),
            })
        return json.dumps({"status": "ok", "tables": tables,
                           "count": len(tables)})
    except Exception as e:
        debug_log("tool_list_tables error: %s" % e, context="Chat")
        return _err(str(e))


def tool_read_table(model, ctx, args):
    """Read all cell contents from a named Writer table."""
    table_name = args.get("table_name", "")
    if not table_name:
        return _err("table_name is required")
    try:
        tables_sup = model.getTextTables()
        if not tables_sup.hasByName(table_name):
            available = list(tables_sup.getElementNames())
            return json.dumps({"status": "error",
                               "message": "Table '%s' not found" % table_name,
                               "available": available})
        table = tables_sup.getByName(table_name)
        rows = table.getRows().getCount()
        cols = table.getColumns().getCount()
        data = []
        for r in range(rows):
            row_data = []
            for c in range(cols):
                col_letter = (chr(ord("A") + c) if c < 26
                              else "A" + chr(ord("A") + c - 26))
                cell_ref = "%s%d" % (col_letter, r + 1)
                try:
                    row_data.append(table.getCellByName(cell_ref).getString())
                except Exception:
                    row_data.append("")
            data.append(row_data)
        return json.dumps({"status": "ok", "table_name": table_name,
                           "rows": rows, "cols": cols, "data": data})
    except Exception as e:
        debug_log("tool_read_table error: %s" % e, context="Chat")
        return _err(str(e))


def tool_write_table_cell(model, ctx, args):
    """Write a value to a specific cell in a Writer table."""
    table_name = args.get("table_name", "")
    cell_ref = args.get("cell", "")
    value = args.get("value", "")
    if not table_name or not cell_ref:
        return _err("table_name and cell are required")
    try:
        tables_sup = model.getTextTables()
        if not tables_sup.hasByName(table_name):
            return _err("Table '%s' not found" % table_name)
        table = tables_sup.getByName(table_name)
        cell_obj = table.getCellByName(cell_ref)
        if cell_obj is None:
            return _err("Cell '%s' not found in table '%s'" % (cell_ref, table_name))
        try:
            cell_obj.setValue(float(value))
        except (ValueError, TypeError):
            cell_obj.setString(str(value))
        return json.dumps({"status": "ok", "table": table_name,
                           "cell": cell_ref, "value": value})
    except Exception as e:
        debug_log("tool_write_table_cell error: %s" % e, context="Chat")
        return _err(str(e))


# ---------------------------------------------------------------------------
# Tool schemas exposed to the AI
# ---------------------------------------------------------------------------

WRITER_OPS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_styles",
            "description": (
                "List available styles in the document. Call this before applying styles "
                "with apply_document_content to discover exact style names (they may be "
                "localized). family defaults to ParagraphStyles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "family": {
                        "type": "string",
                        "description": "Style family to list.",
                        "enum": ["ParagraphStyles", "CharacterStyles",
                                 "PageStyles", "FrameStyles", "NumberingStyles"],
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_style_info",
            "description": "Get detailed properties of a specific style (font, size, margins, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "style_name": {
                        "type": "string",
                        "description": "Name of the style to inspect.",
                    },
                    "family": {
                        "type": "string",
                        "description": "Style family. Default: ParagraphStyles.",
                        "enum": ["ParagraphStyles", "CharacterStyles",
                                 "PageStyles", "FrameStyles", "NumberingStyles"],
                    },
                },
                "required": ["style_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_comments",
            "description": (
                "List all comments/annotations in the document, including author, content, "
                "date, resolved status, and the text they are anchored to."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_comment",
            "description": (
                "Add a comment/annotation anchored to the paragraph containing search_text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The comment text.",
                    },
                    "search_text": {
                        "type": "string",
                        "description": "Anchor the comment to the paragraph containing this text.",
                    },
                    "author": {
                        "type": "string",
                        "description": "Author name shown on the comment. Default: AI.",
                    },
                },
                "required": ["content", "search_text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_comment",
            "description": "Delete a comment and all its replies by the comment's name (from list_comments).",
            "parameters": {
                "type": "object",
                "properties": {
                    "comment_name": {
                        "type": "string",
                        "description": "The 'name' field of the comment returned by list_comments.",
                    },
                },
                "required": ["comment_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_track_changes",
            "description": "Enable or disable track changes (change recording) in the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "description": "True to enable track changes, False to disable.",
                    },
                },
                "required": ["enabled"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tracked_changes",
            "description": (
                "List all tracked changes (redlines) in the document, including type, "
                "author, date, and comment."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "accept_all_changes",
            "description": "Accept all tracked changes in the document.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_all_changes",
            "description": "Reject all tracked changes in the document.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List all text tables in the document with their names and dimensions (rows x cols).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_table",
            "description": "Read all cell contents from a named Writer table as a 2D array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The table name from list_tables.",
                    },
                },
                "required": ["table_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_table_cell",
            "description": (
                "Write a value to a specific cell in a named Writer table. "
                "Use Excel-style cell references (e.g. 'A1', 'B2'). "
                "Numeric strings are stored as numbers automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The table name from list_tables.",
                    },
                    "cell": {
                        "type": "string",
                        "description": "Cell reference, e.g. 'A1', 'B3'.",
                    },
                    "value": {
                        "type": "string",
                        "description": "The value to write.",
                    },
                },
                "required": ["table_name", "cell", "value"],
                "additionalProperties": False,
            },
        },
    },
]

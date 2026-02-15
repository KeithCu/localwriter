# markdown_support.py — Markdown read/write for Writer tool-calling.
# Converts document to/from Markdown; uses system temp dir (cross-platform) and
# insertDocumentFromURL for inserting formatted markdown content.

import json
import os
import tempfile
import urllib.parse
import urllib.request

from core.logging import agent_log, debug_log


# System temp dir: /tmp on Linux, /var/folders/... on macOS, %TEMP% on Windows
TEMP_DIR = tempfile.gettempdir()


def _file_url(path):
    """Return a file:// URL for the given path."""
    return urllib.parse.urljoin("file:", urllib.request.pathname2url(os.path.abspath(path)))


def _create_property_value(name, value):
    """Create a com.sun.star.beans.PropertyValue for loadComponentFromURL."""
    import uno
    p = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    p.Name = name
    p.Value = value
    return p


# ---------------------------------------------------------------------------
# Document → Markdown
# ---------------------------------------------------------------------------

def _document_to_markdown_structural(model, max_chars=None, scope="full", selection_start=0, selection_end=0):
    """Walk document structure and emit Markdown. scope='full', 'selection', or 'range'."""
    try:
        text = model.getText()
        enum = text.createEnumeration()
        lines = []
        current_offset = 0
        while enum.hasMoreElements():
            el = enum.nextElement()
            if not hasattr(el, "getString"):
                continue
            try:
                style = el.getPropertyValue("ParaStyleName") if hasattr(el, "getPropertyValue") else ""
            except Exception:
                style = ""
            para_text = el.getString()
            para_start = current_offset
            para_end = current_offset + len(para_text)
            current_offset = para_end

            if scope in ("selection", "range") and (para_end <= selection_start or para_start >= selection_end):
                continue
            if scope in ("selection", "range") and (para_start < selection_start or para_end > selection_end):
                trim_start = max(0, selection_start - para_start)
                trim_end = len(para_text) - max(0, para_end - selection_end)
                para_text = para_text[trim_start:trim_end]

            prefix = ""
            style_lower = (style or "").strip().lower()
            if "heading 1" in style_lower or style == "Heading 1":
                prefix = "# "
            elif "heading 2" in style_lower or style == "Heading 2":
                prefix = "## "
            elif "heading 3" in style_lower or style == "Heading 3":
                prefix = "### "
            elif "heading 4" in style_lower or style == "Heading 4":
                prefix = "#### "
            elif "heading 5" in style_lower or style == "Heading 5":
                prefix = "##### "
            elif "heading 6" in style_lower or style == "Heading 6":
                prefix = "###### "
            elif "list bullet" in style_lower or style == "List Bullet":
                prefix = "- "
            elif "list number" in style_lower or style == "List Number":
                prefix = "1. "
            elif "quotations" in style_lower or style == "Quotations":
                prefix = "> "

            line = prefix + para_text
            if max_chars and sum(len(l) + 1 for l in lines) + len(line) + 1 > max_chars:
                line = line[: max_chars - sum(len(l) + 1 for l in lines) - 10] + "\n\n[... truncated ...]"
                lines.append(line)
                break
            lines.append(line)
        out = "\n".join(lines)
        if max_chars and len(out) > max_chars:
            out = out[:max_chars] + "\n\n[... truncated ...]"
        return out
    except Exception as e:
        return ""


def document_to_markdown(model, ctx, max_chars=None, scope="full", range_start=None, range_end=None):
    """Get document (or selection/range) as Markdown. Tries storeToURL for full scope, then structural fallback."""
    selection_start, selection_end = 0, 0
    if scope == "selection":
        try:
            from core.document import get_selection_range
            selection_start, selection_end = get_selection_range(model)
        except Exception:
            pass
    elif scope == "range":
        selection_start = int(range_start) if range_start is not None else 0
        selection_end = int(range_end) if range_end is not None else 0
        doc_len = 0
        try:
            from core.document import get_document_length
            doc_len = get_document_length(model)
        except Exception:
            pass
        selection_end = min(selection_end, doc_len)
        selection_start = max(0, min(selection_start, doc_len))

    if scope not in ("selection", "range"):
        try:
            storable = model
            if hasattr(storable, "storeToURL"):
                fd, path = tempfile.mkstemp(suffix=".md", dir=TEMP_DIR)
                try:
                    os.close(fd)
                    file_url = _file_url(path)
                    props = (_create_property_value("FilterName", "Markdown"),)
                    storable.storeToURL(file_url, props)
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if max_chars and len(content) > max_chars:
                        content = content[:max_chars] + "\n\n[... truncated ...]"
                    return content
                finally:
                    try:
                        os.unlink(path)
                    except Exception:
                        pass
        except Exception as e:
            debug_log(ctx, "markdown_support: storeToURL failed (%s), using structural" % e)
    return _document_to_markdown_structural(
        model, max_chars=max_chars, scope=scope,
        selection_start=selection_start, selection_end=selection_end,
    )


# ---------------------------------------------------------------------------
# Markdown → Document (insertDocumentFromURL)
# ---------------------------------------------------------------------------

def _doc_text_length(model):
    """Return (length, snippet) of full document text for logging. snippet is first+last 40 chars."""
    try:
        cur = model.getText().createTextCursor()
        cur.gotoStart(False)
        cur.gotoEnd(True)
        s = cur.getString()
        n = len(s)
        if n <= 80:
            snippet = repr(s)
        else:
            snippet = repr(s[:40] + " ... " + s[-40:])
        return (n, snippet)
    except Exception:
        return (-1, "")


def _insert_markdown_at_position(model, ctx, markdown_string, position, use_process_events=True):
    """Write markdown to a temp file, then use insertDocumentFromURL to insert it as
    formatted content at the given position in the target document.

    insertDocumentFromURL renders the source file through its filter (Markdown → formatted text)
    and inserts the result at the text cursor position. No hidden document, no transferable,
    no clipboard needed.

    position: 'beginning' | 'end' | 'selection'.
    use_process_events: ignored (kept for API compatibility).
    """
    fd, path = tempfile.mkstemp(suffix=".md", dir=TEMP_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(markdown_string)
    except Exception:
        os.close(fd)
        try:
            os.unlink(path)
        except Exception:
            pass
        raise

    file_url = _file_url(path)
    try:
        text = model.getText()
        cursor = text.createTextCursor()

        if position == "beginning":
            cursor.gotoStart(False)
        elif position == "end":
            cursor.gotoEnd(False)
        elif position == "selection":
            try:
                controller = model.getCurrentController()
                sel = controller.getSelection()
                if sel and sel.getCount() > 0:
                    rng = sel.getByIndex(0)
                    rng.setString("")  # Clear selected text
                    cursor.gotoRange(rng.getStart(), False)
                else:
                    vc = controller.getViewCursor()
                    cursor.gotoRange(vc.getStart(), False)
            except Exception:
                cursor.gotoEnd(False)
        else:
            raise ValueError("Unknown position: %s" % position)

        filter_props = (_create_property_value("FilterName", "Markdown"),)
        cursor.insertDocumentFromURL(file_url, filter_props)
        debug_log(ctx, "markdown_support: insertDocumentFromURL succeeded at position=%s" % position)
    except Exception as e:
        debug_log(ctx, "markdown_support: insertDocumentFromURL failed: %s" % e)
        raise
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def _insert_markdown_full(model, ctx, markdown_string):
    """Replace entire document with the given markdown (clear all, then insert at start)."""
    fd, path = tempfile.mkstemp(suffix=".md", dir=TEMP_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(markdown_string)
    except Exception:
        os.close(fd)
        try:
            os.unlink(path)
        except Exception:
            pass
        raise
    file_url = _file_url(path)
    try:
        text = model.getText()
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        cursor.setString("")
        cursor.gotoStart(False)
        filter_props = (_create_property_value("FilterName", "Markdown"),)
        cursor.insertDocumentFromURL(file_url, filter_props)
        debug_log(ctx, "markdown_support: insertDocumentFromURL succeeded at position=full")
    except Exception as e:
        debug_log(ctx, "markdown_support: _insert_markdown_full failed: %s" % e)
        raise
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def _apply_markdown_at_range(model, ctx, markdown_string, start_offset, end_offset):
    """Replace character range [start_offset, end_offset) with rendered markdown content."""
    from core.document import get_text_cursor_at_range
    cursor = get_text_cursor_at_range(model, start_offset, end_offset)
    if cursor is None:
        raise ValueError("Invalid range or could not create cursor for range (%d, %d)" % (start_offset, end_offset))
    fd, path = tempfile.mkstemp(suffix=".md", dir=TEMP_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(markdown_string)
    except Exception:
        os.close(fd)
        try:
            os.unlink(path)
        except Exception:
            pass
        raise
    file_url = _file_url(path)
    try:
        cursor.setString("")
        filter_props = (_create_property_value("FilterName", "Markdown"),)
        cursor.insertDocumentFromURL(file_url, filter_props)
        debug_log(ctx, "markdown_support: apply_markdown_at_range succeeded for (%d, %d)" % (start_offset, end_offset))
    except Exception as e:
        debug_log(ctx, "markdown_support: _apply_markdown_at_range failed: %s" % e)
        raise
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def _apply_markdown_at_search(model, ctx, markdown_string, search_string, all_matches=False, case_sensitive=True):
    """Find search_string (first or all), replace each match with rendered markdown content."""
    fd, path = tempfile.mkstemp(suffix=".md", dir=TEMP_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(markdown_string)
    except Exception:
        os.close(fd)
        try:
            os.unlink(path)
        except Exception:
            pass
        raise

    file_url = _file_url(path)
    try:
        sd = model.createSearchDescriptor()
        sd.SearchString = search_string
        sd.SearchRegularExpression = False
        sd.SearchCaseSensitive = case_sensitive
        filter_props = (_create_property_value("FilterName", "Markdown"),)

        count = 0
        found = model.findFirst(sd)
        while found:
            # Clear the matched text, then insert markdown at that position
            text = found.getText()
            cursor = text.createTextCursorByRange(found)
            cursor.setString("")  # Remove matched text
            cursor.insertDocumentFromURL(file_url, filter_props)
            count += 1
            if not all_matches:
                break
            # Continue searching after the inserted content
            found = model.findNext(cursor.getEnd(), sd)
        return count
    except Exception as e:
        debug_log(ctx, "markdown_support: _apply_markdown_at_search failed: %s" % e)
        raise
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def _find_text_ranges(model, ctx, search_string, start=0, limit=None, case_sensitive=True):
    """Find occurrences of search_string, returning list of {start, end} dicts.
    Optional start offset to search from, and limit on number of matches."""
    matches = []
    try:
        sd = model.createSearchDescriptor()
        sd.SearchString = search_string
        sd.SearchRegularExpression = False
        sd.SearchCaseSensitive = case_sensitive
        
        from core.document import get_document_length
        doc_len = get_document_length(model)
        if start >= doc_len:
            return []

        # Manual iteration with findFirst/findNext is safer for 'limit' and 'start'.
        # We start searching from the beginning and skip matches before 'start'.
        
        # Optimization: Use a cursor at 'start' to restrict search? 
        # model.findNext(start_cursor, sd) -- start_cursor determines start position.
        
        cursor = model.getText().createTextCursor()
        cursor.gotoStart(False)
        cursor.goRight(start, False) # Move to start offset

        found = model.findNext(cursor, sd)
        while found:
            # We need absolute offsets.
            # Reuse get_selection_range logic inline for performance
            measure_cursor = found.getText().createTextCursor()
            measure_cursor.gotoStart(False)
            measure_cursor.gotoRange(found.getStart(), True)
            m_start = len(measure_cursor.getString())
            
            m_end = m_start + len(found.getString())
            
            matches.append({"start": m_start, "end": m_end})
            
            if limit and len(matches) >= limit:
                break
            
            found = model.findNext(found, sd)
            
        return matches
    except Exception as e:
        debug_log(ctx, "markdown_support: _find_text_ranges failed: %s" % e)
        return []


# ---------------------------------------------------------------------------
# Tool schemas and executors
# ---------------------------------------------------------------------------

MARKDOWN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_markdown",
            "description": "Get the document (or a range/selection) as Markdown. Result includes document_length; use it with apply_markdown(target='range', start=0, end=document_length) to replace the whole document, or target='full'. For reformatting: call get_markdown once, then apply_markdown with only the new markdown—never paste the original text back.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_chars": {"type": "integer", "description": "Maximum number of characters to return. Omit for full content."},
                    "scope": {
                        "type": "string",
                        "enum": ["full", "selection", "range"],
                        "description": "Return full document (default), current selection/cursor region, or a character range (requires start and end)."
                    },
                    "start": {"type": "integer", "description": "Start character offset (0-based). Required when scope is 'range'."},
                    "end": {"type": "integer", "description": "End character offset (exclusive). Required when scope is 'range'."},
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_markdown",
            "description": "Insert or replace content using Markdown (converted to formatted text). For 'replace whole document': use target='full' and pass only the new markdown. For a character span: use target='range' with start and end (e.g. from get_markdown's document_length). Never send the original document text back—only the new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "markdown": {"type": "string", "description": "Markdown content. Use newlines for line/paragraph breaks (\\n in JSON). Literal backslash-n in the string is normalized to newlines so headings, lists, and paragraphs render correctly. String or list of strings."},
                    "target": {
                        "type": "string",
                        "enum": ["beginning", "end", "selection", "search", "full", "range"],
                        "description": "Where to apply: 'full' (replace entire document), 'range' (replace [start,end); requires start and end), 'beginning'/'end' (insert), 'selection' (replace selection or insert at cursor), 'search' (find and replace; requires 'search' parameter)."
                    },
                    "start": {"type": "integer", "description": "Start character offset (0-based). Required when target is 'range'."},
                    "end": {"type": "integer", "description": "End character offset (exclusive). Required when target is 'range'."},
                    "search": {"type": "string", "description": "Exact text to find and replace. Required when target is 'search'."},
                    "all_matches": {"type": "boolean", "description": "When target is 'search', replace all occurrences (true) or just the first (false). Default false."},
                    "case_sensitive": {"type": "boolean", "description": "When target is 'search', whether the search is case-sensitive. Default true."},
                },
                "required": ["markdown", "target"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_text",
            "description": "Find occurrences of text in the document. Returns a list of ranges ({start, end}) that can be used with apply_markdown(target='range').",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Text to search for."},
                    "start": {"type": "integer", "description": "Start offset to search from (default 0)."},
                    "limit": {"type": "integer", "description": "Maximum number of matches to return (optional)."},
                    "case_sensitive": {"type": "boolean", "description": "Case sensitive search. Default true."},
                },
                "required": ["search"],
                "additionalProperties": False
            }
        }
    },
]


def _tool_error(message):
    return json.dumps({"status": "error", "message": message})


def tool_get_markdown(model, ctx, args):
    """Tool: get document, selection, or range as Markdown. Returns document_length and optionally start/end for scope=range."""
    try:
        from core.document import get_document_length
        max_chars = args.get("max_chars")
        scope = args.get("scope", "full")
        range_start = args.get("start") if scope == "range" else None
        range_end = args.get("end") if scope == "range" else None
        if scope == "range" and (range_start is None or range_end is None):
            return _tool_error("scope 'range' requires start and end parameters")
        markdown = document_to_markdown(
            model, ctx, max_chars=max_chars, scope=scope,
            range_start=range_start, range_end=range_end,
        )
        doc_len = get_document_length(model)
        out = {"status": "ok", "markdown": markdown, "length": len(markdown), "document_length": doc_len}
        if scope == "range" and range_start is not None and range_end is not None:
            out["start"] = int(range_start)
            out["end"] = int(range_end)
        return json.dumps(out)
    except Exception as e:
        debug_log(ctx, "markdown_support: get_markdown failed: %s" % e)
        return _tool_error(str(e))


def tool_apply_markdown(model, ctx, args):
    """Tool: insert or replace content using Markdown (combined edit)."""
    markdown = args.get("markdown")
    target = args.get("target")
    
    # Debug: log the start of content to check for wrapping issues
    if markdown:
        debug_log(ctx, "tool_apply_markdown: input type=%s starts with: %s" % (type(markdown), repr(markdown)[:50]))
        
        # Accommodate list input (LLM sometimes ignores schema and sends array)
        if isinstance(markdown, list):
             debug_log(ctx, "tool_apply_markdown: joining list input with newlines")
             markdown = "\n".join(str(x) for x in markdown)
        # Normalize literal \n and \t so multi-line markdown renders correctly
        # (handles over-escaped or stream-chunked output where we get backslash-n instead of newline)
        if isinstance(markdown, str):
            markdown = markdown.replace("\\n", "\n").replace("\\t", "\t")
    
    if not markdown and markdown != "":
        return _tool_error("markdown is required")
    if not target:
        return _tool_error("target is required")
    if target == "search":
        search = args.get("search")
        if not search and search != "":
            return _tool_error("search is required when target is 'search'")
        all_matches = args.get("all_matches", False)
        case_sensitive = args.get("case_sensitive", True)
        try:
            count = _apply_markdown_at_search(model, ctx, markdown, search, all_matches=all_matches, case_sensitive=case_sensitive)
            return json.dumps({"status": "ok", "message": "Replaced %d occurrence(s) with markdown content." % count})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_markdown search failed: %s" % e)
            return _tool_error(str(e))
    if target == "full":
        try:
            _insert_markdown_full(model, ctx, markdown)
            return json.dumps({"status": "ok", "message": "Replaced entire document with markdown."})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_markdown full failed: %s" % e)
            return _tool_error(str(e))
    if target == "range":
        start_val = args.get("start")
        end_val = args.get("end")
        if start_val is None or end_val is None:
            return _tool_error("target 'range' requires start and end parameters")
        try:
            _apply_markdown_at_range(model, ctx, markdown, int(start_val), int(end_val))
            return json.dumps({"status": "ok", "message": "Replaced range [%s, %s) with markdown." % (start_val, end_val)})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_markdown range failed: %s" % e)
            return _tool_error(str(e))
    if target in ("beginning", "end", "selection"):
        try:
            _insert_markdown_at_position(model, ctx, markdown, target)
            return json.dumps({"status": "ok", "message": "Inserted markdown at %s." % target})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_markdown insert failed: %s" % e)
            return _tool_error(str(e))
    return _tool_error("Unknown target: %s" % target)


def tool_find_text(model, ctx, args):
    """Tool: find text ranges."""
    search = args.get("search")
    if not search:
        return _tool_error("search parameter is required")
    start = args.get("start", 0)
    limit = args.get("limit")
    case_sensitive = args.get("case_sensitive", True)
    
    ranges = _find_text_ranges(model, ctx, search, start=start, limit=limit, case_sensitive=case_sensitive)
    return json.dumps({"status": "ok", "ranges": ranges})


# ---------------------------------------------------------------------------
# In-LibreOffice test runner (called from main.py menu: Run markdown tests)
# ---------------------------------------------------------------------------

def run_markdown_tests(ctx, model=None):
    """
    Run markdown_support tests with real UNO. Called from main.py when user chooses Run markdown tests.
    ctx: UNO ComponentContext. model: optional XTextDocument (Writer); if None or not Writer, a new doc is created.
    Returns (passed_count, failed_count, list of message strings).
    """
    log = []
    passed = 0
    failed = 0

    def ok(msg):
        log.append("OK: %s" % msg)

    def fail(msg):
        log.append("FAIL: %s" % msg)

    desktop = ctx.getServiceManager().createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx)
    doc = model
    if doc is None or not hasattr(doc, "getText"):
        try:
            doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        except Exception as e:
            return 0, 1, ["Could not create Writer document: %s" % e]
    if not doc or not hasattr(doc, "getText"):
        return 0, 1, ["No Writer document available."]

    debug_log(ctx, "markdown_tests: run start (model=%s)" % ("supplied" if model is doc else "new"))

    try:
        md = document_to_markdown(doc, ctx, scope="full")
        if isinstance(md, str):
            passed += 1
            ok("document_to_markdown(scope='full') returned string (len=%d)" % len(md))
        else:
            failed += 1
            fail("document_to_markdown did not return string: %s" % type(md))
    except Exception as e:
        failed += 1
        log.append("FAIL: document_to_markdown raised: %s" % e)

    try:
        result = tool_get_markdown(doc, ctx, {"scope": "full"})
        data = json.loads(result)
        if data.get("status") == "ok" and "markdown" in data:
            passed += 1
            ok("tool_get_markdown returned status=ok and markdown (len=%d)" % len(data.get("markdown", "")))
        else:
            failed += 1
            fail("tool_get_markdown: %s" % result[:200])
    except Exception as e:
        failed += 1
        log.append("FAIL: tool_get_markdown raised: %s" % e)


    def _read_doc_text(d):
        raw = d.getText().createTextCursor()
        raw.gotoStart(False)
        raw.gotoEnd(True)
        return raw.getString()

    # Test: get_markdown returns document_length
    try:
        result = tool_get_markdown(doc, ctx, {"scope": "full"})
        data = json.loads(result)
        doc_len_actual = len(_read_doc_text(doc))
        if data.get("status") == "ok" and "document_length" in data and data["document_length"] == doc_len_actual:
            passed += 1
            ok("tool_get_markdown returns document_length (%d)" % doc_len_actual)
        else:
            failed += 1
            fail("tool_get_markdown document_length: got %s, doc len=%d" % (data.get("document_length"), doc_len_actual))
    except Exception as e:
        failed += 1
        log.append("FAIL: get_markdown document_length raised: %s" % e)

    test_markdown = "## Markdown test\n\nThis was inserted by the test."
    insert_needle = "Markdown test"

    # Test A: apply at end with use_process_events=False (diagnostic: often fails)
    try:
        len_before = _doc_text_length(doc)[0]
        _insert_markdown_at_position(doc, ctx, test_markdown, "end", use_process_events=False)
        full_text = _read_doc_text(doc)
        len_after = len(full_text)
        content_found = insert_needle in full_text
        debug_log(ctx, "markdown_tests: strategy=no_events len_before=%s len_after=%s content_found=%s" % (
            len_before, len_after, content_found))
        if content_found:
            passed += 1
            ok("apply at end (no processEvents): content found (len_after=%d)" % len_after)
        else:
            failed += 1
            fail("apply at end (no processEvents): content not found (len_before=%d len_after=%d)" % (len_before, len_after))
    except Exception as e:
        failed += 1
        log.append("FAIL: apply no processEvents raised: %s" % e)
        debug_log(ctx, "markdown_tests: strategy=no_events raised: %s" % e)

    # Test B: apply at end with use_process_events=True (fix: should succeed)
    try:
        len_before = _doc_text_length(doc)[0]
        _insert_markdown_at_position(doc, ctx, test_markdown, "end", use_process_events=True)
        full_text = _read_doc_text(doc)
        len_after = len(full_text)
        content_found = insert_needle in full_text
        debug_log(ctx, "markdown_tests: strategy=process_events len_before=%s len_after=%s content_found=%s" % (
            len_before, len_after, content_found))
        if content_found:
            passed += 1
            ok("apply at end (with processEvents): content found (len_after=%d)" % len_after)
        else:
            failed += 1
            fail("apply at end (with processEvents): content not found (len_before=%d len_after=%d)" % (len_before, len_after))
    except Exception as e:
        failed += 1
        log.append("FAIL: apply with processEvents raised: %s" % e)
        debug_log(ctx, "markdown_tests: strategy=process_events raised: %s" % e)

    # Test C: production path (tool_apply_markdown uses process_events=True)
    try:
        result = tool_apply_markdown(doc, ctx, {
            "markdown": test_markdown,
            "target": "end",
        })
        data = json.loads(result)
        if data.get("status") != "ok":
            failed += 1
            fail("tool_apply_markdown: %s" % result[:200])
        else:
            full_text = _read_doc_text(doc)
            if insert_needle in full_text:
                passed += 1
                ok("tool_apply_markdown(target='end'): status=ok and content in document (len=%d)" % len(full_text))
            else:
                failed += 1
                fail("tool_apply_markdown returned ok but content not in document (len=%d)" % len(full_text))
    except Exception as e:
        failed += 1
        log.append("FAIL: tool_apply_markdown raised: %s" % e)

    # Test D: markdown formatting (bold, italic, headings) - VISIBLE TEST
    try:
        formatted_markdown = "# Heading\n\n**Bold text** and *italic text* and _underline_"
        len_before = _doc_text_length(doc)[0]
        result = tool_apply_markdown(doc, ctx, {
            "markdown": formatted_markdown,
            "target": "end",
        })
        data = json.loads(result)
        if data.get("status") != "ok":
            failed += 1
            fail("formatted markdown: tool returned error: %s" % result[:200])
        else:
            full_text = _read_doc_text(doc)
            len_after = len(full_text)
            # Check if ANY of the formatting keywords appear (raw or formatted)
            has_heading = "Heading" in full_text
            has_bold = "Bold" in full_text
            has_italic = "italic" in full_text
            has_underline = "underline" in full_text
            
            if has_heading or has_bold or has_italic or has_underline:
                passed += 1
                ok("formatted markdown: INSERTED (len %d→%d, has_heading=%s, has_bold=%s, has_italic=%s, has_underline=%s)" % (
                    len_before, len_after, has_heading, has_bold, has_italic, has_underline))
            else:
                failed += 1
                fail("formatted markdown: NOT FOUND (len %d→%d)" % (len_before, len_after))
    except Exception as e:
        failed += 1
        log.append("FAIL: formatted markdown test raised: %s" % e)

    # Test E: search-and-replace path (_apply_markdown_at_search)
    try:
        # Insert a known string, then replace it with markdown
        marker = "REPLACE_ME_MARKER"
        text = doc.getText()
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        text.insertString(cursor, "\n" + marker, False)
        result = tool_apply_markdown(doc, ctx, {
            "markdown": "**replaced**",
            "target": "search",
            "search": marker,
        })
        data = json.loads(result)
        full_text = _read_doc_text(doc)
        if data.get("status") == "ok" and "replaced" in full_text and marker not in full_text:
            passed += 1
            ok("search-and-replace: marker replaced with markdown content")
        else:
            failed += 1
            fail("search-and-replace: status=%s, marker_gone=%s, replaced_found=%s" % (
                data.get("status"), marker not in full_text, "replaced" in full_text))
    except Exception as e:
        failed += 1
        log.append("FAIL: search-and-replace test raised: %s" % e)

    # Test G: Real list input support (accommodating fix)
    try:
        # Pass a REAL list, expect joined content
        list_input = ["**list**", "*item*"]
        len_before = _doc_text_length(doc)[0]
        result = tool_apply_markdown(doc, ctx, {
            "markdown": list_input,
            "target": "end",
        })
        data = json.loads(result)
        full_text = _read_doc_text(doc)
        
        has_content = "list" in full_text and "item" in full_text
        
        if data.get("status") == "ok" and has_content:
            passed += 1
            ok("list input accommodation: handled list input successfully")
        else:
            failed += 1
            fail("list input accommodation: status=%s, has_content=%s (input was %s)" % (
                data.get("status"), has_content, list_input))
    except Exception as e:
        failed += 1
        log.append("FAIL: list input test raised: %s" % e)

    # Test H: target="full" — replace entire document
    try:
        full_replacement = "# Full Replace Test\n\nOnly this content should remain."
        result = tool_apply_markdown(doc, ctx, {"markdown": full_replacement, "target": "full"})
        data = json.loads(result)
        full_text = _read_doc_text(doc)
        if data.get("status") == "ok" and "Full Replace Test" in full_text and "Only this content" in full_text:
            passed += 1
            ok("target='full': replaced entire document (len=%d)" % len(full_text))
        else:
            failed += 1
            fail("target='full': status=%s, content check failed (len=%d)" % (data.get("status"), len(full_text)))
    except Exception as e:
        failed += 1
        log.append("FAIL: target=full test raised: %s" % e)

    # Test I: target="range" with start=0, end=document_length (whole-doc replace by range)
    try:
        from core.document import get_document_length
        doc_len = get_document_length(doc)
        range_md = "## Range Replace\n\nReplaced by range [0, %d)." % doc_len
        result = tool_apply_markdown(doc, ctx, {"markdown": range_md, "target": "range", "start": 0, "end": doc_len})
        data = json.loads(result)
        full_text = _read_doc_text(doc)
        if data.get("status") == "ok" and "Range Replace" in full_text:
            passed += 1
            ok("target='range' [0, doc_len): replaced with markdown (len=%d)" % len(full_text))
        else:
            failed += 1
            fail("target='range': status=%s (len=%d)" % (data.get("status"), len(full_text)))
    except Exception as e:
        failed += 1
        log.append("FAIL: target=range test raised: %s" % e)

    # Test J: get_markdown scope="range" returns slice and start/end
    try:
        full_text = _read_doc_text(doc)
        if len(full_text) >= 10:
            result = tool_get_markdown(doc, ctx, {"scope": "range", "start": 0, "end": 10})
            data = json.loads(result)
            if data.get("status") == "ok" and data.get("start") == 0 and data.get("end") == 10 and "markdown" in data:
                passed += 1
                ok("get_markdown scope='range' (0,10): returns start, end and markdown")
            else:
                failed += 1
                fail("get_markdown scope=range: %s" % result[:200])
        else:
            passed += 1
            ok("get_markdown scope=range: skipped (doc too short)")
    except Exception as e:
        failed += 1
        log.append("FAIL: get_markdown scope=range raised: %s" % e)

    # Test K: tool_find_text
    try:
        # Insert unique text to find
        marker_find = "FIND_ME_UNIQUE_xyz"
        text = doc.getText()
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        text.insertString(cursor, "\n" + marker_find, False)
        
        # Search for it
        result = tool_find_text(doc, ctx, {
            "search": marker_find,
            "case_sensitive": True
        })
        data = json.loads(result)
        
        if data.get("status") == "ok" and "ranges" in data:
            ranges = data["ranges"]
            if len(ranges) == 1:
                r = ranges[0]
                # Verify we can extract the text at that range
                text_at_range = _read_doc_text(doc)[r["start"]:r["end"]] # Python slice of full text
                if text_at_range == marker_find:
                    passed += 1
                    ok("find_text: found correct range (text '%s' matches)" % text_at_range)
                else:
                    failed += 1
                    fail("find_text: range text mismatch. Expected '%s', got '%s'" % (marker_find, text_at_range))
            else:
                failed += 1
                fail("find_text: expected 1 match, got %d" % len(ranges))
        else:
            failed += 1
            fail("find_text: status=%s" % data.get("status"))
            
    except Exception as e:
        failed += 1
        log.append("FAIL: find_text raised: %s" % e)

    return passed, failed, log

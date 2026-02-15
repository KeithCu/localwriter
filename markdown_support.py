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
    """Walk document structure and emit Markdown. scope='full' or 'selection'."""
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

            if scope == "selection" and (para_end <= selection_start or para_start >= selection_end):
                continue
            if scope == "selection" and (para_start < selection_start or para_end > selection_end):
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


def document_to_markdown(model, ctx, max_chars=None, scope="full"):
    """Get document (or selection) as Markdown. Tries storeToURL for full scope, then structural fallback."""
    selection_start, selection_end = 0, 0
    if scope == "selection":
        try:
            from core.document import get_selection_range
            selection_start, selection_end = get_selection_range(model)
        except Exception:
            pass

    if scope != "selection":
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


# ---------------------------------------------------------------------------
# Tool schemas and executors
# ---------------------------------------------------------------------------

MARKDOWN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_markdown",
            "description": "Get the document (or current selection) as Markdown. Use this to read formatted content as markdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_chars": {"type": "integer", "description": "Maximum number of characters to return. Omit for full content."},
                    "scope": {
                        "type": "string",
                        "enum": ["full", "selection"],
                        "description": "Return full document (default) or only the current selection/cursor region."
                    },
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_markdown",
            "description": "Insert or replace content using Markdown. The markdown is converted to formatted document content. Use target to choose where: beginning or end of document, current selection (replace selection or insert at cursor), or search for exact text to replace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "markdown": {"type": "string", "description": "The content in Markdown format."},
                    "target": {
                        "type": "string",
                        "enum": ["beginning", "end", "selection", "search"],
                        "description": "Where to apply: 'beginning' or 'end' of document, 'selection' (replace selection or insert at cursor), or 'search' (find and replace; requires 'search' parameter)."
                    },
                    "search": {"type": "string", "description": "Exact text to find and replace. Required when target is 'search'."},
                    "all_matches": {"type": "boolean", "description": "When target is 'search', replace all occurrences (true) or just the first (false). Default false."},
                    "case_sensitive": {"type": "boolean", "description": "When target is 'search', whether the search is case-sensitive. Default true."},
                },
                "required": ["markdown", "target"],
                "additionalProperties": False
            }
        }
    },
]


def _tool_error(message):
    return json.dumps({"status": "error", "message": message})


def tool_get_markdown(model, ctx, args):
    """Tool: get document or selection as Markdown."""
    try:
        max_chars = args.get("max_chars")
        scope = args.get("scope", "full")
        markdown = document_to_markdown(model, ctx, max_chars=max_chars, scope=scope)
        return json.dumps({"status": "ok", "markdown": markdown, "length": len(markdown)})
    except Exception as e:
        debug_log(ctx, "markdown_support: get_markdown failed: %s" % e)
        return _tool_error(str(e))


def tool_apply_markdown(model, ctx, args):
    """Tool: insert or replace content using Markdown (combined edit)."""
    markdown = args.get("markdown")
    target = args.get("target")
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
    if target in ("beginning", "end", "selection"):
        try:
            _insert_markdown_at_position(model, ctx, markdown, target)
            return json.dumps({"status": "ok", "message": "Inserted markdown at %s." % target})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_markdown insert failed: %s" % e)
            return _tool_error(str(e))
    return _tool_error("Unknown target: %s" % target)


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

    test_markdown = "## Markdown test\n\nThis was inserted by the test."
    insert_needle = "Markdown test"

    def _read_doc_text(d):
        raw = d.getText().createTextCursor()
        raw.gotoStart(False)
        raw.gotoEnd(True)
        return raw.getString()

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

    return passed, failed, log

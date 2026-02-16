# markdown_support.py — Markdown read/write for Writer tool-calling.
# Converts document to/from Markdown; uses system temp dir (cross-platform) and
# insertDocumentFromURL for inserting formatted markdown content.

import contextlib
import json
import os
import tempfile
import time
import urllib.parse
import urllib.request

from core.logging import debug_log


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


@contextlib.contextmanager
def _with_temp_markdown(content=None):
    """Create a temp .md file. If content is not None, write it; else create empty file. Yields (path, file_url). Unlinks in finally."""
    fd, path = tempfile.mkstemp(suffix=".md", dir=TEMP_DIR)
    try:
        if content is not None:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            os.close(fd)
        file_url = _file_url(path)
        yield (path, file_url)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Document → Markdown
# ---------------------------------------------------------------------------

# com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK
_PARAGRAPH_BREAK = 0


def _range_to_markdown_via_temp_doc(model, ctx, selection_start, selection_end, max_chars=None):
    """Copy the character range [selection_start, selection_end) into a temporary Writer document
    (preserving paragraph styles), then export it to Markdown via storeToURL. Returns markdown string or \"\" on failure."""
    temp_doc = None
    try:
        smgr = ctx.getServiceManager()
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        load_props = (_create_property_value("Hidden", True),)
        temp_doc = desktop.loadComponentFromURL("private:factory/swriter", "_default", 0, load_props)
        if not temp_doc or not hasattr(temp_doc, "getText"):
            if temp_doc:
                temp_doc.close(True)
            debug_log(ctx, "markdown_support: _range_to_markdown_via_temp_doc could not create temp document")
            return ""
        temp_text = temp_doc.getText()
        temp_cursor = temp_text.createTextCursor()
        text = model.getText()
        enum = text.createEnumeration()
        current_offset = 0
        first_para = True
        added_any = False
        while enum.hasMoreElements():
            el = enum.nextElement()
            if not hasattr(el, "getString"):
                continue
            try:
                style = el.getPropertyValue("ParaStyleName") if hasattr(el, "getPropertyValue") else ""
            except Exception:
                style = ""
            style = style or ""
            para_text = el.getString()
            para_start = current_offset
            para_end = current_offset + len(para_text)
            current_offset = para_end

            if para_end <= selection_start or para_start >= selection_end:
                continue
            if para_start < selection_start or para_end > selection_end:
                trim_start = max(0, selection_start - para_start)
                trim_end = len(para_text) - max(0, para_end - selection_end)
                para_text = para_text[trim_start:trim_end]

            if first_para:
                temp_cursor.gotoStart(False)
                temp_cursor.setString(para_text)
                try:
                    temp_cursor.setPropertyValue("ParaStyleName", style)
                except Exception:
                    pass
                first_para = False
            else:
                temp_cursor.gotoEnd(False)
                temp_text.insertControlCharacter(temp_cursor, _PARAGRAPH_BREAK, False)
                try:
                    temp_cursor.setPropertyValue("ParaStyleName", style)
                except Exception:
                    pass
                temp_cursor.setString(para_text)
            added_any = True

        if not added_any:
            return ""

        with _with_temp_markdown(None) as (path, file_url):
            props = (_create_property_value("FilterName", "Markdown"),)
            temp_doc.storeToURL(file_url, props)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        if max_chars and len(content) > max_chars:
            content = content[:max_chars] + "\n\n[... truncated ...]"
        return content
    except Exception as e:
        debug_log(ctx, "markdown_support: _range_to_markdown_via_temp_doc failed: %s" % e)
        return ""
    finally:
        if temp_doc is not None:
            try:
                temp_doc.close(True)
            except Exception:
                pass


def document_to_markdown(model, ctx, max_chars=None, scope="full", range_start=None, range_end=None):
    """Get document (or selection/range) as Markdown. Uses storeToURL for full scope; for selection/range uses temp document + storeToURL."""
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
                with _with_temp_markdown(None) as (path, file_url):
                    props = (_create_property_value("FilterName", "Markdown"),)
                    storable.storeToURL(file_url, props)
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if max_chars and len(content) > max_chars:
                        content = content[:max_chars] + "\n\n[... truncated ...]"
                    return content
        except Exception as e:
            debug_log(ctx, "markdown_support: storeToURL failed (%s)" % e)
            return ""
    return _range_to_markdown_via_temp_doc(model, ctx, selection_start, selection_end, max_chars)


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


def _insert_markdown_at_position(model, ctx, markdown_string, position):
    """Write markdown to a temp file, then use insertDocumentFromURL to insert it as
    formatted content at the given position in the target document.

    insertDocumentFromURL renders the source file through its filter (Markdown → formatted text)
    and inserts the result at the text cursor position. No hidden document, no transferable,
    no clipboard needed.

    position: 'beginning' | 'end' | 'selection'.
    """
    with _with_temp_markdown(markdown_string) as (path, file_url):
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


def _insert_markdown_full(model, ctx, markdown_string):
    """Replace entire document with the given markdown (clear all, then insert at start)."""
    with _with_temp_markdown(markdown_string) as (path, file_url):
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


def _apply_markdown_at_range(model, ctx, markdown_string, start_offset, end_offset):
    """Replace character range [start_offset, end_offset) with rendered markdown content."""
    from core.document import get_text_cursor_at_range
    cursor = get_text_cursor_at_range(model, start_offset, end_offset)
    if cursor is None:
        raise ValueError("Invalid range or could not create cursor for range (%d, %d)" % (start_offset, end_offset))
    with _with_temp_markdown(markdown_string) as (path, file_url):
        try:
            cursor.setString("")
            filter_props = (_create_property_value("FilterName", "Markdown"),)
            cursor.insertDocumentFromURL(file_url, filter_props)
            debug_log(ctx, "markdown_support: apply_markdown_at_range succeeded for (%d, %d)" % (start_offset, end_offset))
        except Exception as e:
            debug_log(ctx, "markdown_support: _apply_markdown_at_range failed: %s" % e)
            raise


def _markdown_to_plain_via_document(ctx, markdown_string):
    """Load markdown into a temporary Writer document via LO's Markdown filter, return plain text.
    Returns None on any failure so callers can fall back to the original string."""
    t0 = time.time()
    if markdown_string is None:
        return None
    try:
        with _with_temp_markdown(markdown_string) as (path, file_url):
            smgr = ctx.getServiceManager()
            desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            load_props = (
                _create_property_value("FilterName", "Markdown"),
                _create_property_value("Hidden", True),
            )
            debug_log(ctx, "markdown_support: _markdown_to_plain_via_document loading url=%s with FilterName=Markdown Hidden=True" % file_url)
            doc = desktop.loadComponentFromURL(file_url, "_default", 0, load_props)
            if not doc:
                debug_log(ctx, "markdown_support: _markdown_to_plain_via_document load returned None (took %.3fs)" % (time.time() - t0))
                return None
            if not hasattr(doc, "getText"):
                debug_log(ctx, "markdown_support: _markdown_to_plain_via_document loaded component has no getText (took %.3fs)" % (time.time() - t0))
                doc.close(True)
                return None
            cursor = doc.getText().createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            plain = cursor.getString()
            doc.close(True)
            # Strip trailing newlines so we match document paragraphs (last para in doc often has no trailing \n)
            if plain is not None and isinstance(plain, str):
                plain = plain.rstrip("\n\r")
            # Log what we got so we can see if filter was applied (e.g. 'Summary') or raw markdown ('## Summary')
            snippet = repr(plain[:200]) if plain is not None and len(plain) > 200 else repr(plain)
            debug_log(ctx, "markdown_support: _markdown_to_plain_via_document plain len=%s snippet=%s (took %.3fs)" % (len(plain) if plain else 0, snippet, time.time() - t0))
            return plain
    except Exception as e:
        import traceback
        debug_log(ctx, "markdown_support: _markdown_to_plain_via_document failed: %s (took %.3fs)" % (e, time.time() - t0))
        debug_log(ctx, "markdown_support: _markdown_to_plain_via_document traceback: %s" % traceback.format_exc())
        return None


def _literal_search_candidates(source_string):
    """Build a deduplicated list of literal search strings to try for a given source.
    Includes raw, normalized (all line breaks collapsed to \\n), and variants with
    \\n\\n, \\r\\n, \\r\\n\\r\\n, \\r, \\n\\r, plus optional trailing \\n and \\n\\n.
    Used so multi-paragraph search can match regardless of how Writer stores breaks."""
    if source_string is None or not isinstance(source_string, str):
        return [source_string] if source_string is not None else []
    seen = set()
    out = []
    def add(s):
        if s is not None and s not in seen:
            seen.add(s)
            out.append(s)
    add(source_string)
    # Normalize: collapse all line break forms to single \n (order matters)
    normalized = source_string.replace("\r\n\r\n", "\n").replace("\r\n", "\n").replace("\n\n", "\n").replace("\r", "\n")
    add(normalized)
    add(normalized.replace("\n", "\n\n"))
    add(normalized.replace("\n", "\r\n"))
    add(normalized.replace("\n", "\r\n\r\n"))
    add(normalized.replace("\n", "\r"))
    add(normalized.replace("\n", "\n\r"))
    add(normalized + "\n")
    add(normalized + "\n\n")
    return out


def _search_candidates_with_plain(ctx, search_string):
    """Return deduplicated list of search candidates: raw + normalized + LO plain variants."""
    candidates = list(_literal_search_candidates(search_string))
    plain = _markdown_to_plain_via_document(ctx, search_string)
    if plain:
        seen = set(candidates)
        for c in _literal_search_candidates(plain):
            if c not in seen:
                seen.add(c)
                candidates.append(c)
    return candidates


def _apply_markdown_at_search(model, ctx, markdown_string, search_string, all_matches=False, case_sensitive=True):
    """Find search_string (first or all), replace each match with rendered markdown content.
    Builds literal search candidates from the raw string and always from LO plain (when available)
    via _literal_search_candidates, so we handle markdown stripping and multiple line-ending variants."""
    search_candidates = _search_candidates_with_plain(ctx, search_string)
    t0 = time.time()
    debug_log(ctx, "markdown_support: _apply_markdown_at_search LO plain took %.3fs, %d candidates" % (time.time() - t0, len(search_candidates)))
    with _with_temp_markdown(markdown_string) as (path, file_url):
        filter_props = (_create_property_value("FilterName", "Markdown"),)
        try:
            for idx, search_candidate in enumerate(search_candidates):
                # Log exact candidate so we can see line endings and characters (repr truncate to 400)
                r = repr(search_candidate)
                if len(r) > 400:
                    r = r[:400] + "..."
                debug_log(ctx, "markdown_support: _apply_markdown_at_search candidate #%d len=%d: %s" % (idx, len(search_candidate), r))
                sd = model.createSearchDescriptor()
                sd.SearchString = search_candidate
                sd.SearchRegularExpression = False
                sd.SearchCaseSensitive = case_sensitive
                count = 0
                found = model.findFirst(sd)
                while found:
                    text = found.getText()
                    cursor = text.createTextCursorByRange(found)
                    cursor.setString("")
                    cursor.insertDocumentFromURL(file_url, filter_props)
                    count += 1
                    if not all_matches:
                        break
                    found = model.findNext(cursor.getEnd(), sd)
                debug_log(ctx, "markdown_support: _apply_markdown_at_search candidate #%d -> replaced %d" % (idx, count))
                if count > 0:
                    return count
            debug_log(ctx, "markdown_support: _apply_markdown_at_search all %d candidates gave 0 replacements" % len(search_candidates))
            return 0
        except Exception as e:
            debug_log(ctx, "markdown_support: _apply_markdown_at_search failed: %s" % e)
            raise


def _find_text_ranges(model, ctx, search_string, start=0, limit=None, case_sensitive=True):
    """Find occurrences of search_string, returning list of {start, end, text} dicts.
    Optional start offset to search from, and limit on number of matches.
    Each range includes "text": the exact document string at that span.
    Tries exact search_string first; if no match, converts markdown to plain via LO and retries."""
    from core.document import get_document_length
    doc_len = get_document_length(model)
    if start >= doc_len:
        return []

    def _search(s):
        matches = []
        try:
            sd = model.createSearchDescriptor()
            sd.SearchString = s
            sd.SearchRegularExpression = False
            sd.SearchCaseSensitive = case_sensitive
            cursor = model.getText().createTextCursor()
            cursor.gotoStart(False)
            cursor.goRight(start, False)
            found = model.findNext(cursor, sd)
            while found:
                measure_cursor = found.getText().createTextCursor()
                measure_cursor.gotoStart(False)
                measure_cursor.gotoRange(found.getStart(), True)
                m_start = len(measure_cursor.getString())
                matched_text = found.getString()
                m_end = m_start + len(matched_text)
                matches.append({"start": m_start, "end": m_end, "text": matched_text})
                if limit and len(matches) >= limit:
                    break
                found = model.findNext(found, sd)
        except Exception as e:
            debug_log(ctx, "markdown_support: _find_text_ranges failed: %s" % e)
        return matches

    r0 = repr(search_string)
    if len(r0) > 400:
        r0 = r0[:400] + "..."
    debug_log(ctx, "markdown_support: _find_text_ranges initial search len=%d: %s" % (len(search_string), r0))
    matches = _search(search_string)
    debug_log(ctx, "markdown_support: _find_text_ranges initial -> %d matches" % len(matches))
    if matches:
        # Log first match's actual document text so we see what the doc contains
        first_text = matches[0].get("text", "")
        debug_log(ctx, "markdown_support: _find_text_ranges first match text len=%d repr=%s" % (len(first_text), repr(first_text)[:300]))
    if not matches:
        t0_fallback = time.time()
        candidates = _search_candidates_with_plain(ctx, search_string)
        for idx, needle in enumerate(candidates):
            r = repr(needle)
            if len(r) > 400:
                r = r[:400] + "..."
            debug_log(ctx, "markdown_support: _find_text_ranges candidate #%d len=%d: %s" % (idx, len(needle), r))
            matches = _search(needle)
            debug_log(ctx, "markdown_support: _find_text_ranges candidate #%d -> %d matches" % (idx, len(matches)))
            if matches:
                first_text = matches[0].get("text", "")
                debug_log(ctx, "markdown_support: _find_text_ranges first match text len=%d repr=%s" % (len(first_text), repr(first_text)[:300]))
                break
        debug_log(ctx, "markdown_support: _find_text_ranges fallback took %.3fs, %d candidates" % (time.time() - t0_fallback, len(candidates)))
        if not matches:
            # Log document prefix so we can see actual line endings / content
            try:
                cursor = model.getText().createTextCursor()
                cursor.gotoStart(False)
                n = min(500, doc_len)
                if n > 0:
                    cursor.goRight(n, True)
                    prefix = cursor.getString()
                    debug_log(ctx, "markdown_support: _find_text_ranges document prefix (first %d chars) repr=%s" % (len(prefix), repr(prefix)))
            except Exception as e:
                debug_log(ctx, "markdown_support: _find_text_ranges could not get document prefix: %s" % e)
    return matches


# ---------------------------------------------------------------------------
# Tool schemas and executors
# ---------------------------------------------------------------------------

MARKDOWN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_markdown",
            "description": "Get document (or selection/range) as Markdown. Result includes document_length. scope: full, selection, or range (requires start, end).",
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
            "description": "Insert or replace with Markdown. Preferred for partial edits: target='search' with search= and markdown=. For whole doc: target='full'. Use target='range' with start/end (e.g. from find_text or get_markdown document_length).",
            "parameters": {
                "type": "object",
                "properties": {
                    "markdown": {"type": "string", "description": "Markdown string (use \\n for line breaks). Can be list of strings (joined with newlines)."},
                    "target": {
                        "type": "string",
                        "enum": ["beginning", "end", "selection", "search", "full", "range"],
                        "description": "Where to apply: full, range (start+end), search (needs search), beginning, end, selection."
                    },
                    "start": {"type": "integer", "description": "Start character offset (0-based). Required when target is 'range'."},
                    "end": {"type": "integer", "description": "End character offset (exclusive). Required when target is 'range'."},
                    "search": {"type": "string", "description": "Text to find (markdown ok; LO strips to plain to match). For section replacement send the full section text. Required for target 'search'."},
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
            "description": "Finds text. Accepts markdown; LO strips to plain to match. Returns {start, end, text} per match. Use with apply_markdown (search= or target=range).",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Text to search (markdown ok; LO strips to plain to match)."},
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
            msg = "Replaced %d occurrence(s) with markdown content." % count
            if count == 0:
                msg += " Tried multiple literal candidates (including different line-ending variants). For section replacement send the full section text as search, or use find_text then apply_markdown with target='range'."
            return json.dumps({"status": "ok", "message": msg})
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



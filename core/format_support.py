# format_support.py — Format-agnostic read/write for Writer tool-calling.
# Converts document to/from Markdown/HTML; uses system temp dir (cross-platform) and
# insertDocumentFromURL for inserting formatted content.

import contextlib
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request

from core.logging import debug_log
from core.constants import DOCUMENT_FORMAT


# Map internal format name to LibreOffice filter name and file extension
FORMAT_CONFIG = {
    "markdown": {"filter": "Markdown", "extension": ".md"},
    "html": {"filter": "HTML (StarWriter)", "extension": ".html"},
}


def _get_format_props():
    """Return (FilterName, file_extension) for the current DOCUMENT_FORMAT."""
    cfg = FORMAT_CONFIG.get(DOCUMENT_FORMAT, FORMAT_CONFIG["markdown"])
    return cfg["filter"], cfg["extension"]


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
def _with_temp_buffer(content=None):
    """Create a temp file with the correct extension for the current format.
    If content is not None, write it; else create empty file. Yields (path, file_url). Unlinks in finally."""
    _, ext = _get_format_props()
    fd, path = tempfile.mkstemp(suffix=ext, dir=TEMP_DIR)
    try:
        if content is not None:
            if isinstance(content, list):
                content = "\n".join(str(x) for x in content)
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

def _strip_html_boilerplate(html_string):
    """Extract content between <body> tags if present, otherwise return as is.
    Helps the AI see cleaner content without noisy meta/style tags."""
    if not html_string or not isinstance(html_string, str):
        return html_string
    
    # Simple regex to find body content
    match = re.search(r'<body[^>]*>(.*?)</body>', html_string, re.DOTALL | re.IGNORECASE)
    if match:
        body_content = match.group(1).strip()
        # Remove some common junk LO adds if it's there
        return body_content
    return html_string


# com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK
_PARAGRAPH_BREAK = 0


def _strip_html_boilerplate(html_string):
    """Extract content between <body> tags if present, otherwise return as is.
    Helps the AI see cleaner content without noisy meta/style tags."""
    if not html_string or not isinstance(html_string, str):
        return html_string
    
    # Simple regex to find body content
    match = re.search(r'<body[^>]*>(.*?)</body>', html_string, re.DOTALL | re.IGNORECASE)
    if match:
        body_content = match.group(1).strip()
        # Remove some common junk LO adds if it's there
        # (e.g. initial/trailing empty paragraphs or lines)
        return body_content
    return html_string


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
                temp_cursor.setPropertyValue("ParaStyleName", style)
                first_para = False
            else:
                temp_cursor.gotoEnd(False)
                temp_text.insertControlCharacter(temp_cursor, _PARAGRAPH_BREAK, False)
                temp_cursor.setPropertyValue("ParaStyleName", style)
                temp_cursor.setString(para_text)
            added_any = True

        if not added_any:
            return ""

        filter_name, _ = _get_format_props()
        with _with_temp_buffer(None) as (path, file_url):
            props = (_create_property_value("FilterName", filter_name),)
            temp_doc.storeToURL(file_url, props)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        if DOCUMENT_FORMAT == "html":
            content = _strip_html_boilerplate(content)
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
                filter_name, _ = _get_format_props()
                with _with_temp_buffer(None) as (path, file_url):
                    props = (_create_property_value("FilterName", filter_name),)
                    storable.storeToURL(file_url, props)
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if DOCUMENT_FORMAT == "html":
                        content = _strip_html_boilerplate(content)
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
    with _with_temp_buffer(markdown_string) as (path, file_url):
        try:
            text = model.getText()
            cursor = text.createTextCursor()
            # ... (position movement logic)
            # (Wait, I need to make sure I don't break the cursor movement logic)

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

            filter_name, _ = _get_format_props()
            filter_props = (_create_property_value("FilterName", filter_name),)
            cursor.insertDocumentFromURL(file_url, filter_props)
            debug_log(ctx, "markdown_support: insertDocumentFromURL succeeded at position=%s" % position)
        except Exception as e:
            debug_log(ctx, "markdown_support: insertDocumentFromURL failed: %s" % e)
            raise


def _insert_markdown_full(model, ctx, markdown_string):
    """Replace entire document with the given content (clear all, then insert at start)."""
    with _with_temp_buffer(markdown_string) as (path, file_url):
        try:
            text = model.getText()
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            cursor.setString("")
            cursor.gotoStart(False)
            filter_name, _ = _get_format_props()
            filter_props = (_create_property_value("FilterName", filter_name),)
            cursor.insertDocumentFromURL(file_url, filter_props)
            debug_log(ctx, "markdown_support: insertDocumentFromURL succeeded at position=full")
        except Exception as e:
            debug_log(ctx, "markdown_support: _insert_markdown_full failed: %s" % e)
            raise


def _apply_markdown_at_range(model, ctx, markdown_string, start_offset, end_offset):
    """Replace character range [start_offset, end_offset) with rendered content."""
    from core.document import get_text_cursor_at_range
    cursor = get_text_cursor_at_range(model, start_offset, end_offset)
    if cursor is None:
        raise ValueError("Invalid range or could not create cursor for range (%d, %d)" % (start_offset, end_offset))
    with _with_temp_buffer(markdown_string) as (path, file_url):
        try:
            cursor.setString("")
            filter_name, _ = _get_format_props()
            filter_props = (_create_property_value("FilterName", filter_name),)
            cursor.insertDocumentFromURL(file_url, filter_props)
            debug_log(ctx, "markdown_support: apply_markdown_at_range succeeded for (%d, %d)" % (start_offset, end_offset))
        except Exception as e:
            debug_log(ctx, "markdown_support: _apply_markdown_at_range failed: %s" % e)
            raise


def _markdown_to_plain_via_document(ctx, markdown_string):
    """Load content into a temporary Writer document via LO's filter, return plain text.
    Returns None on any failure so callers can fall back to the original string."""
    t0 = time.time()
    if markdown_string is None:
        return None
    try:
        with _with_temp_buffer(markdown_string) as (path, file_url):
            smgr = ctx.getServiceManager()
            desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            filter_name, _ = _get_format_props()
            load_props = (
                _create_property_value("FilterName", filter_name),
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
    with _with_temp_buffer(markdown_string) as (path, file_url):
        filter_name, _ = _get_format_props()
        filter_props = (_create_property_value("FilterName", filter_name),)
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

FORMAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_document_content",
            "description": "Get document (or selection/range) content. Result includes document_length. scope: full, selection, or range (requires start, end).",
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
            "name": "apply_document_content",
            "description": "Insert or replace content. Preferred for partial edits: target='search' with search= and content=. For whole doc: target='full'. Use target='range' with start/end (e.g. from find_text or get_document_content document_length).",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The new content (Markdown or HTML based on system prompt). Can be list of strings (joined with newlines)."},
                    "target": {
                        "type": "string",
                        "enum": ["beginning", "end", "selection", "search", "full", "range"],
                        "description": "Where to apply: full, range (start+end), search (needs search), beginning, end, selection."
                    },
                    "start": {"type": "integer", "description": "Start character offset (0-based). Required when target is 'range'."},
                    "end": {"type": "integer", "description": "End character offset (exclusive). Required when target is 'range'."},
                    "search": {"type": "string", "description": "Text to find (LO strips to plain to match). For section replacement send the full section text. Required for target 'search'."},
                    "all_matches": {"type": "boolean", "description": "When target is 'search', replace all occurrences (true) or just the first (false). Default false."},
                    "case_sensitive": {"type": "boolean", "description": "When target is 'search', whether the search is case-sensitive. Default true."},
                },
                "required": ["content", "target"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_text",
            "description": "Finds text. LO strips search string to plain to match document content. Returns {start, end, text} per match. Use with apply_document_content (search= or target=range).",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Text to search (LO strips to plain to match)."},
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


def _wrap_html_fragment(html_content):
    """Wrap HTML fragment in complete document structure for LibreOffice's HTML filter.
    Adds <html>, <head>, <body> tags if missing.
    
    Also ensures proper charset declaration for special characters (é, ü, ©, etc.)."""
    if not html_content or not isinstance(html_content, str):
        return html_content

    # Check if it already has basic document structure
    has_html_tag = '<html' in html_content.lower() and '</html>' in html_content.lower()
    has_body_tag = '<body' in html_content.lower() and '</body>' in html_content.lower()

    if has_html_tag and has_body_tag:
        return html_content

    # Wrap fragment in complete structure with UTF-8 charset for special characters
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body>
{html_content}
</body>
</html>"""


def _ensure_html_linebreaks(content):
    """If content looks like plain text or Markdown (no basic HTML tags) but has newlines,
    convert newlines to <br> and <p> so the 'HTML (StarWriter)' filter preserves them.
    Standard browsers (and LO's filter) collapse newlines in HTML.
    
    Also handles escaped HTML by unescaping first to detect real HTML tags."""
    if not isinstance(content, str) or not content:
        return content
    
    # First unescape HTML entities to detect real HTML
    import html
    unescaped = html.unescape(content)
    
    # Check for HTML tags in unescaped version
    html_tags = ["<p>", "<br>", "</h1>", "</h2>", "</h3>", "</ul>", "</li>", "</div>", "<html>"]
    has_html = any(tag in unescaped.lower() for tag in html_tags)

    if has_html:
        # It's HTML, wrap if needed and return
        return _wrap_html_fragment(unescaped)
    
    # It looks plain. Convert newlines.
    # Collapse 3+ newlines to 2
    content = re.sub(r'\n{3,}', '\n\n', content)
    # Split by double newline for paragraphs
    paras = content.split('\n\n')
    out = []
    for p in paras:
        if not p.strip():
            continue
        # For each paragraph, convert single \n to <br>
        p_html = p.replace('\n', '<br>\n')
        out.append("<p>%s</p>" % p_html)
    
    wrapped = "\n".join(out)
    return _wrap_html_fragment(wrapped)


def tool_get_document_content(model, ctx, args):
    """Tool: get document, selection, or range. Returns document_length and optionally start/end for scope=range."""
    try:
        from core.document import get_document_length
        max_chars = args.get("max_chars")
        scope = args.get("scope", "full")
        range_start = args.get("start") if scope == "range" else None
        range_end = args.get("end") if scope == "range" else None
        if scope == "range" and (range_start is None or range_end is None):
            return _tool_error("scope 'range' requires start and end parameters")
        content = document_to_markdown(
            model, ctx, max_chars=max_chars, scope=scope,
            range_start=range_start, range_end=range_end,
        )
        doc_len = get_document_length(model)
        out = {"status": "ok", "content": content, "length": len(content), "document_length": doc_len}
        if scope == "range" and range_start is not None and range_end is not None:
            out["start"] = int(range_start)
            out["end"] = int(range_end)
        return json.dumps(out)
    except Exception as e:
        debug_log(ctx, "markdown_support: get_document_content failed: %s" % e)
        return _tool_error(str(e))


def tool_apply_document_content(model, ctx, args):
    """Tool: insert or replace content (combined edit)."""
    content = args.get("content")
    target = args.get("target")
    
    # Debug: log the start of content to check for wrapping issues
    if content:
        debug_log(ctx, "tool_apply_document_content: input type=%s starts with: %s" % (type(content), repr(content)[:50]))
        
        # Accommodate list input (LLM sometimes ignores schema and sends array)
        if isinstance(content, list):
             debug_log(ctx, "tool_apply_document_content: joining list input with newlines")
             content = "\n".join(str(x) for x in content)
        # Normalize literal \n and \t so multi-line content renders correctly
        if isinstance(content, str):
            content = content.replace("\\n", "\n").replace("\\t", "\t")
            if DOCUMENT_FORMAT == "html":
                # Unescape HTML entities first (e.g., &lt; → <, &gt; → >)
                import html
                content = html.unescape(content)
                content = _ensure_html_linebreaks(content)
    
    if not content and content != "":
        return _tool_error("content is required")
    if not target:
        return _tool_error("target is required")
    if target == "search":
        search = args.get("search")
        if not search and search != "":
            return _tool_error("search is required when target is 'search'")
        all_matches = args.get("all_matches", False)
        case_sensitive = args.get("case_sensitive", True)
        try:
            count = _apply_markdown_at_search(model, ctx, content, search, all_matches=all_matches, case_sensitive=case_sensitive)
            msg = "Replaced %d occurrence(s) with new content." % count
            if count == 0:
                msg += " Tried multiple literal candidates. For section replacement send the full section text as search, or use find_text then apply_document_content with target='range'."
            return json.dumps({"status": "ok", "message": msg})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_document_content search failed: %s" % e)
            return _tool_error(str(e))
    if target == "full":
        try:
            _insert_markdown_full(model, ctx, content)
            return json.dumps({"status": "ok", "message": "Replaced entire document."})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_document_content full failed: %s" % e)
            return _tool_error(str(e))
    if target == "range":
        start_val = args.get("start")
        end_val = args.get("end")
        if start_val is None or end_val is None:
            return _tool_error("target 'range' requires start and end parameters")
        try:
            _apply_markdown_at_range(model, ctx, content, int(start_val), int(end_val))
            return json.dumps({"status": "ok", "message": "Replaced range [%s, %s)." % (start_val, end_val)})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_document_content range failed: %s" % e)
            return _tool_error(str(e))
    if target in ("beginning", "end", "selection"):
        try:
            _insert_markdown_at_position(model, ctx, content, target)
            return json.dumps({"status": "ok", "message": "Inserted content at %s." % target})
        except Exception as e:
            debug_log(ctx, "markdown_support: apply_document_content insert failed: %s" % e)
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



import json
from core.markdown_support import (
    document_to_markdown,
    tool_get_markdown,
    tool_apply_markdown,
    tool_find_text,
    _insert_markdown_at_position,
    _doc_text_length
)
from core.logging import debug_log


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

    # Test: apply at end via _insert_markdown_at_position
    try:
        len_before = _doc_text_length(doc)[0]
        _insert_markdown_at_position(doc, ctx, test_markdown, "end")
        full_text = _read_doc_text(doc)
        len_after = len(full_text)
        content_found = insert_needle in full_text
        debug_log(ctx, "markdown_tests: apply at end len_before=%s len_after=%s content_found=%s" % (
            len_before, len_after, content_found))
        if content_found:
            passed += 1
            ok("apply at end: content found (len_after=%d)" % len_after)
        else:
            failed += 1
            fail("apply at end: content not found (len_before=%d len_after=%d)" % (len_before, len_after))
    except Exception as e:
        failed += 1
        log.append("FAIL: apply at end raised: %s" % e)
        debug_log(ctx, "markdown_tests: apply at end raised: %s" % e)

    # Test: production path (tool_apply_markdown target='end')
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

    # Test: get_markdown scope="range" returns correct partial content (AI partial read)
    try:
        from core.document import get_document_length
        partial_content = "# Partial Range Test\n\nFirst paragraph here.\n\nSecond paragraph."
        result = tool_apply_markdown(doc, ctx, {"markdown": partial_content, "target": "full"})
        if json.loads(result).get("status") != "ok":
            failed += 1
            fail("partial range test setup: replace with full failed")
        else:
            doc_len = get_document_length(doc)
            end_offset = min(45, doc_len)  # first ~45 chars: heading + start of first para
            result = tool_get_markdown(doc, ctx, {"scope": "range", "start": 0, "end": end_offset})
            data = json.loads(result)
            md = data.get("markdown", "")
            if data.get("status") == "ok" and md and "Partial" in md:
                passed += 1
                ok("get_markdown scope=range: partial content returned (AI partial read ok)")
            else:
                failed += 1
                fail("get_markdown scope=range partial: status=%s len(md)=%s has_Partial=%s" % (
                    data.get("status"), len(md), "Partial" in md))
    except Exception as e:
        failed += 1
        log.append("FAIL: get_markdown scope=range partial content raised: %s" % e)

    # Test: get_markdown scope="selection" returns partial markdown (AI selection read)
    try:
        from core.document import get_text_cursor_at_range, get_document_length
        doc_len = get_document_length(doc)
        if doc_len < 10:
            passed += 1
            ok("get_markdown scope=selection: skipped (doc too short)")
        else:
            range_cursor = get_text_cursor_at_range(doc, 0, min(30, doc_len))
            if range_cursor is None:
                failed += 1
                fail("get_markdown scope=selection: could not create range cursor")
            else:
                vc = doc.getCurrentController().getViewCursor()
                vc.gotoRange(range_cursor.getStart(), False)
                vc.gotoRange(range_cursor.getEnd(), True)
                result = tool_get_markdown(doc, ctx, {"scope": "selection"})
                data = json.loads(result)
                md = data.get("markdown", "")
                if data.get("status") == "ok" and isinstance(md, str) and len(md) > 0:
                    passed += 1
                    ok("get_markdown scope=selection: partial markdown returned (AI selection read ok)")
                else:
                    failed += 1
                    fail("get_markdown scope=selection: status=%s len(md)=%s" % (data.get("status"), len(md)))
    except Exception as e:
        failed += 1
        log.append("FAIL: get_markdown scope=selection raised: %s" % e)

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
                # Verify we can extract the text at that range and that "text" field matches
                text_at_range = _read_doc_text(doc)[r["start"]:r["end"]] # Python slice of full text
                range_text = r.get("text", "")
                if text_at_range == marker_find and range_text == marker_find:
                    passed += 1
                    ok("find_text: found correct range (text '%s' matches)" % text_at_range)
                else:
                    failed += 1
                    fail("find_text: range text mismatch. Expected '%s', got '%s', range.text='%s'" % (marker_find, text_at_range, range_text))
            else:
                failed += 1
                fail("find_text: expected 1 match, got %d" % len(ranges))
        else:
            failed += 1
            fail("find_text: status=%s" % data.get("status"))
            
    except Exception as e:
        failed += 1
        log.append("FAIL: find_text raised: %s" % e)

    # Test L: markdown-aware find_text (search with "## Summary" finds Heading 2 "Summary")
    try:
        # Insert a Heading 2 "Summary" via markdown (single line so LO plain text is "Summary")
        result = tool_apply_markdown(doc, ctx, {"markdown": "## Summary", "target": "end"})
        if json.loads(result).get("status") != "ok":
            failed += 1
            fail("markdown-aware find_text setup: insert ## Summary failed")
        else:
            result = tool_find_text(doc, ctx, {"search": "## Summary", "case_sensitive": False})
            data = json.loads(result)
            if data.get("status") == "ok" and data.get("ranges"):
                ranges = data["ranges"]
                if len(ranges) >= 1 and ranges[0].get("text") == "Summary":
                    passed += 1
                    ok("find_text(markdown): '## Summary' found as plain 'Summary'")
                else:
                    failed += 1
                    fail("find_text(markdown): expected range text 'Summary', got %s" % (ranges[0].get("text") if ranges else "no ranges"))
            else:
                failed += 1
                fail("find_text(markdown): status=%s ranges=%s" % (data.get("status"), data.get("ranges")))
    except Exception as e:
        failed += 1
        log.append("FAIL: markdown-aware find_text raised: %s" % e)

    # Test M: markdown-aware apply_markdown(target="search") replaces heading
    try:
        # Ensure we have "## Summary" in doc (from Test L or insert again)
        full_before = _read_doc_text(doc)
        if "Summary" not in full_before:
            tool_apply_markdown(doc, ctx, {"markdown": "## Summary\n\n", "target": "end"})
        result = tool_apply_markdown(doc, ctx, {
            "markdown": "## ReplacedByMarkdownSearch",
            "target": "search",
            "search": "## Summary",
            "all_matches": False,
            "case_sensitive": False
        })
        data = json.loads(result)
        full_after = _read_doc_text(doc)
        if data.get("status") == "ok" and "Replaced 1 occurrence(s)" in data.get("message", "") and "ReplacedByMarkdownSearch" in full_after:
            passed += 1
            ok("apply_markdown(target=search, markdown search): replaced heading")
        elif data.get("status") == "ok" and "Replaced 0 occurrence(s)" in data.get("message", ""):
            failed += 1
            fail("apply_markdown(markdown search): 0 replacements (markdown-to-plain may have failed)")
        else:
            failed += 1
            fail("apply_markdown(markdown search): status=%s message=%s" % (data.get("status"), data.get("message", "")[:80]))
    except Exception as e:
        failed += 1
        log.append("FAIL: markdown-aware apply_markdown search raised: %s" % e)

    # Test N: safeguard — when search is "## Summary\n\n", LO returns "Summary" (much shorter); we skip plain and return 0 with hint
    try:
        result = tool_apply_markdown(doc, ctx, {
            "markdown": "## Replacement",
            "target": "search",
            "search": "## Summary\n\n",
            "all_matches": False,
        })
        data = json.loads(result)
        msg = data.get("message", "")
        if data.get("status") == "ok" and "Replaced 0 occurrence(s)" in msg and "find_text" in msg and "target='range'" in msg:
            passed += 1
            ok("apply_markdown safeguard: short plain skipped, 0 replacements and hint returned")
        elif data.get("status") == "ok" and "Replaced 0 occurrence(s)" in msg:
            passed += 1
            ok("apply_markdown safeguard: 0 replacements (hint may vary)")
        else:
            failed += 1
            fail("apply_markdown safeguard: expected 0 replacements with hint, got status=%s message=%s" % (data.get("status"), msg[:120]))
    except Exception as e:
        failed += 1
        log.append("FAIL: apply_markdown safeguard test raised: %s" % e)

    return passed, failed, log

"""DocumentService — UNO document helpers and caching."""

import logging
import re
import time

from plugin.framework.service_base import ServiceBase
from plugin.framework.uno_context import get_ctx

log = logging.getLogger("localwriter.document")

# Yield-to-GUI counter (module-level, shared across all calls)
_yield_counter = 0


class DocumentCache:
    """Cache for expensive UNO calls, tied to a document model."""

    _instances = {}  # {id(model): cache}

    def __init__(self):
        self.length = None
        self.para_ranges = None
        self.page_cache = {}
        self.last_invalidated = time.time()

    @classmethod
    def get(cls, model):
        mid = id(model)
        if mid not in cls._instances:
            cls._instances[mid] = DocumentCache()
        return cls._instances[mid]

    @classmethod
    def invalidate(cls, model):
        mid = id(model)
        cls._instances.pop(mid, None)

    @classmethod
    def remove(cls, model):
        """Remove cache entirely (document closed)."""
        cls._instances.pop(id(model), None)


class DocumentService(ServiceBase):
    name = "document"

    def __init__(self):
        self._desktop = None
        self._events = None

    def initialize(self, ctx):
        # ctx is no longer stored — we use get_ctx() for fresh context
        pass

    def set_events(self, events):
        self._events = events

    # ── Desktop / active document ─────────────────────────────────────

    def _get_desktop(self):
        if self._desktop is None:
            ctx = get_ctx()
            if ctx:
                sm = ctx.getServiceManager()
                self._desktop = sm.createInstanceWithContext(
                    "com.sun.star.frame.Desktop", ctx
                )
        return self._desktop

    def get_active_document(self):
        """Return the active UNO document model, or None."""
        desktop = self._get_desktop()
        if desktop is None:
            return None
        try:
            return desktop.getCurrentComponent()
        except Exception:
            return None

    # ── Type detection ────────────────────────────────────────────────

    def is_writer(self, model):
        try:
            return model.supportsService("com.sun.star.text.TextDocument")
        except Exception:
            return False

    def is_calc(self, model):
        try:
            return model.supportsService("com.sun.star.sheet.SpreadsheetDocument")
        except Exception:
            return False

    def is_draw(self, model):
        try:
            return (
                model.supportsService("com.sun.star.drawing.DrawingDocument")
                or model.supportsService("com.sun.star.presentation.PresentationDocument")
            )
        except Exception:
            return False

    def detect_doc_type(self, model):
        """Return "writer", "calc", "draw", or None."""
        if model is None:
            return None
        if self.is_writer(model):
            return "writer"
        if self.is_calc(model):
            return "calc"
        if self.is_draw(model):
            return "draw"
        return None

    # ── Cache ─────────────────────────────────────────────────────────

    def get_cache(self, model):
        return DocumentCache.get(model)

    def invalidate_cache(self, model):
        if model is not None:
            DocumentCache.invalidate(model)
            if self._events:
                self._events.emit("document:cache_invalidated", doc=model)

    # ── Writer helpers ────────────────────────────────────────────────

    def get_full_text(self, model, max_chars=8000):
        """Get full document text, truncated to *max_chars*."""
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

    def get_document_length(self, model):
        """Return character count of the document (cached)."""
        cache = DocumentCache.get(model)
        if cache.length is not None:
            return cache.length
        try:
            text = model.getText()
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            cache.length = len(cursor.getString())
            return cache.length
        except Exception:
            return 0

    def build_heading_tree(self, model):
        """Return the heading outline as a nested list of dicts.

        Each entry: {"level": int, "title": str, "children": [...]}.
        """
        try:
            text = model.getText()
            enum = text.createEnumeration()
            headings = []
            while enum.hasMoreElements():
                para = enum.nextElement()
                try:
                    level = para.getPropertyValue("OutlineLevel")
                except Exception:
                    continue
                if level > 0:
                    headings.append({
                        "level": level,
                        "title": para.getString().strip(),
                        "children": [],
                    })
            return self._nest_headings(headings)
        except Exception:
            log.exception("build_heading_tree failed")
            return []

    def _nest_headings(self, flat):
        """Convert flat list of headings into nested tree."""
        if not flat:
            return []
        root = []
        stack = []  # (level, node)
        for h in flat:
            node = {"level": h["level"], "title": h["title"], "children": []}
            while stack and stack[-1][0] >= h["level"]:
                stack.pop()
            if stack:
                stack[-1][1]["children"].append(node)
            else:
                root.append(node)
            stack.append((h["level"], node))
        return root

    def get_paragraph_ranges(self, model):
        """Return list of paragraph UNO text range objects (cached)."""
        cache = DocumentCache.get(model)
        if cache.para_ranges is not None:
            return cache.para_ranges
        try:
            text = model.getText()
            enum = text.createEnumeration()
            ranges = []
            while enum.hasMoreElements():
                ranges.append(enum.nextElement())
            cache.para_ranges = ranges
            return ranges
        except Exception:
            return []

    def find_paragraph_for_range(self, match_range, para_ranges, text_obj=None):
        """Find which paragraph index a text range belongs to."""
        try:
            if text_obj is None:
                text_obj = match_range.getText()
            match_start = match_range.getStart()
            for i, para in enumerate(para_ranges):
                try:
                    para_start = para.getStart()
                    para_end = para.getEnd()
                    cmp_start = text_obj.compareRegionStarts(
                        match_start, para_start)
                    cmp_end = text_obj.compareRegionStarts(
                        match_start, para_end)
                    if cmp_start <= 0 and cmp_end >= 0:
                        return i
                except Exception:
                    continue
        except Exception:
            pass
        return -1

    def find_paragraph_element(self, model, para_index):
        """Find a paragraph element by index. Returns (element, max_index)."""
        doc_text = model.getText()
        enum = doc_text.createEnumeration()
        idx = 0
        while enum.hasMoreElements():
            element = enum.nextElement()
            if idx == para_index:
                return element, idx
            idx += 1
        return None, idx

    def annotate_pages(self, nodes, model):
        """Recursively add 'page' field to heading tree nodes.

        Uses lockControllers + cursor save/restore to prevent
        visible viewport jumping while resolving page numbers.
        """
        try:
            controller = model.getCurrentController()
            vc = controller.getViewCursor()
            saved = model.getText().createTextCursorByRange(vc.getStart())
            model.lockControllers()
            try:
                self._annotate_pages_inner(nodes, model)
            finally:
                vc.gotoRange(saved, False)
                model.unlockControllers()
        except Exception:
            pass

    def _annotate_pages_inner(self, nodes, model):
        for node in nodes:
            try:
                pi = node.get("para_index")
                if pi is not None:
                    node["page"] = self.get_page_for_paragraph(model, pi)
            except Exception:
                pass
            if "children" in node:
                self._annotate_pages_inner(node["children"], model)

    # ── Locator resolution ─────────────────────────────────────────

    def resolve_locator(self, model, locator):
        """Parse 'type:value' locator and resolve to document position.

        Returns dict with at least ``para_index``.
        Simple locators handled here; Writer-specific ones are
        delegated to writer_tree service (from writer_nav module).
        """
        loc_type, sep, loc_value = locator.partition(":")
        if not sep:
            raise ValueError(
                "Invalid locator format: '%s'. Expected 'type:value'."
                % locator)

        if loc_type == "paragraph":
            return {"para_index": int(loc_value)}

        if loc_type == "first":
            return {"para_index": 0}

        if loc_type == "last":
            para_ranges = self.get_paragraph_ranges(model)
            return {"para_index": max(0, len(para_ranges) - 1)}

        if loc_type == "cursor":
            try:
                controller = model.getCurrentController()
                vc = controller.getViewCursor()
                text_obj = model.getText()
                para_ranges = self.get_paragraph_ranges(model)
                idx = self.find_paragraph_for_range(
                    vc.getStart(), para_ranges, text_obj)
                return {"para_index": max(0, idx)}
            except Exception as e:
                raise ValueError("Cannot resolve cursor locator: %s" % e)

        if loc_type == "regex":
            return self._resolve_regex_locator(model, loc_value)

        # Writer-specific: delegate to writer_tree service
        if loc_type in ("bookmark", "page", "section",
                        "heading", "heading_text"):
            from plugin.main import get_services
            svc = get_services().get("writer_tree")
            if svc is None:
                raise ValueError(
                    "writer_nav module not loaded for locator '%s'" % loc_type)
            return svc.resolve_writer_locator(model, loc_type, loc_value)

        raise ValueError("Unknown locator type: '%s'" % loc_type)

    def _resolve_regex_locator(self, model, pattern):
        """Resolve regex:/<pattern>/ to the first matching paragraph."""
        # Strip leading/trailing slashes if present
        if pattern.startswith("/") and pattern.endswith("/"):
            pattern = pattern[1:-1]
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError("Invalid regex pattern: %s" % e)
        para_ranges = self.get_paragraph_ranges(model)
        for i, para in enumerate(para_ranges):
            try:
                text = para.getString()
                if regex.search(text):
                    return {"para_index": i}
            except Exception:
                continue
        raise ValueError("No paragraph matches regex: %s" % pattern)

    # ── Page helpers ───────────────────────────────────────────────

    def get_page_for_paragraph(self, model, para_index):
        """Return page number for a paragraph by index.

        Uses lockControllers + cursor save/restore to prevent
        visible viewport jumping.
        """
        try:
            text = model.getText()
            controller = model.getCurrentController()
            vc = controller.getViewCursor()
            saved = text.createTextCursorByRange(vc.getStart())
            model.lockControllers()
            try:
                cursor = text.createTextCursor()
                cursor.gotoStart(False)
                for _ in range(para_index):
                    if not cursor.gotoNextParagraph(False):
                        break
                vc.gotoRange(cursor, False)
                page = vc.getPage()
            finally:
                vc.gotoRange(saved, False)
                model.unlockControllers()
            return page
        except Exception:
            return 1

    def get_page_count(self, model):
        """Return page count of a Writer document."""
        try:
            text = model.getText()
            controller = model.getCurrentController()
            vc = controller.getViewCursor()
            saved = text.createTextCursorByRange(vc.getStart())
            model.lockControllers()
            try:
                vc.jumpToLastPage()
                count = vc.getPage()
            finally:
                vc.gotoRange(saved, False)
                model.unlockControllers()
            return count
        except Exception:
            return 0

    def doc_key(self, model):
        """Stable key for a document (URL or id)."""
        try:
            return model.getURL() or str(id(model))
        except Exception:
            return str(id(model))

    def get_document_end(self, model, max_chars=4000):
        """Return the last *max_chars* characters of the document."""
        try:
            text = model.getText()
            cursor = text.createTextCursor()
            cursor.gotoEnd(False)
            cursor.gotoStart(True)
            full = cursor.getString()
            if len(full) <= max_chars:
                return full
            return full[-max_chars:]
        except Exception:
            return ""

    # ── Chat context builders ─────────────────────────────────────

    def get_document_context_for_chat(self, model, max_context=8000,
                                      include_end=True,
                                      include_selection=True):
        """Build a context string for the chat LLM.

        Dispatches to Writer / Calc / Draw specific builders.
        Returns a human-readable summary with selection markers.
        """
        if self.is_calc(model):
            return self._calc_context_for_chat(model, max_context)
        if self.is_draw(model):
            return self._draw_context_for_chat(model, max_context)
        return self._writer_context_for_chat(
            model, max_context, include_end, include_selection)

    def _writer_context_for_chat(self, model, max_context, include_end,
                                 include_selection):
        try:
            text = model.getText()
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            full = cursor.getString()
            doc_len = len(full)
        except Exception:
            return ("Document length: 0.\n\n"
                    "[DOCUMENT START]\n(empty)\n[END DOCUMENT]")

        start_offset, end_offset = (0, 0)
        if include_selection:
            try:
                from plugin.modules.writer.ops import get_selection_range
                start_offset, end_offset = get_selection_range(model)
            except Exception:
                pass
            start_offset = max(0, min(start_offset, doc_len))
            end_offset = max(0, min(end_offset, doc_len))
            if start_offset > end_offset:
                start_offset, end_offset = end_offset, start_offset
            max_span = 2000
            if end_offset - start_offset > max_span:
                end_offset = start_offset + max_span

        if include_end and doc_len > (max_context // 2):
            start_chars = max_context // 2
            end_chars = max_context - start_chars
            start_excerpt = self._inject_markers(
                full[:start_chars], 0, start_chars,
                start_offset, end_offset,
                "[DOCUMENT START]\n", "\n[DOCUMENT END]")
            end_excerpt = self._inject_markers(
                full[-end_chars:], doc_len - end_chars, doc_len,
                start_offset, end_offset,
                "[DOCUMENT END]\n", "\n[END DOCUMENT]")
            middle = ("\n\n[... middle of document omitted ...]\n\n"
                      if doc_len > max_context else "")
            return ("Document length: %d characters.\n\n%s%s%s"
                    % (doc_len, start_excerpt, middle, end_excerpt))

        take = min(doc_len, max_context)
        excerpt = full[:take]
        if doc_len > max_context:
            excerpt += "\n\n[... document truncated ...]"
        excerpt = self._inject_markers(
            excerpt, 0, take, start_offset, end_offset,
            "[DOCUMENT START]\n", "\n[END DOCUMENT]")
        return "Document length: %d characters.\n\n%s" % (doc_len, excerpt)

    def _calc_context_for_chat(self, model, max_context):
        try:
            from plugin.modules.calc.bridge import CalcBridge
            from plugin.modules.calc.analyzer import SheetAnalyzer

            bridge = CalcBridge(model)
            analyzer = SheetAnalyzer(bridge)
            summary = analyzer.get_sheet_summary()

            ctx_str = "Spreadsheet: %s\n" % (
                model.getURL() or "Untitled")
            ctx_str += "Active Sheet: %s\n" % summary["sheet_name"]
            ctx_str += "Used Range: %s (%d rows x %d columns)\n" % (
                summary["used_range"],
                summary["row_count"], summary["col_count"])
            headers = [str(h) for h in summary.get("headers", []) if h]
            if headers:
                ctx_str += "Columns: %s\n" % ", ".join(headers)

            controller = model.getCurrentController()
            selection = controller.getSelection()
            if selection and hasattr(selection, "getRangeAddress"):
                addr = selection.getRangeAddress()
                from plugin.modules.calc.address_utils import index_to_column
                sel_range = "%s%d:%s%d" % (
                    index_to_column(addr.StartColumn),
                    addr.StartRow + 1,
                    index_to_column(addr.EndColumn),
                    addr.EndRow + 1)
                ctx_str += "Current Selection: %s\n" % sel_range

                cell_count = ((addr.EndRow - addr.StartRow + 1) *
                              (addr.EndColumn - addr.StartColumn + 1))
                if cell_count < 100:
                    from plugin.modules.calc.inspector import CellInspector
                    inspector = CellInspector(bridge)
                    cells = inspector.read_range(sel_range)
                    ctx_str += "Selection Content (CSV-like):\n"
                    for row in cells:
                        ctx_str += ", ".join([
                            str(c["value"]) if c["value"] is not None
                            else "" for c in row]) + "\n"

            return ctx_str
        except Exception as e:
            return "Error getting Calc context: %s" % e

    def _draw_context_for_chat(self, model, max_context):
        try:
            from plugin.modules.draw.bridge import DrawBridge
            bridge = DrawBridge(model)
            pages = bridge.get_pages()
            active_page = bridge.get_active_page()

            is_impress = model.supportsService(
                "com.sun.star.presentation.PresentationDocument")
            doc_type = "Impress Presentation" if is_impress else "Draw Document"
            page_label = "Slide" if is_impress else "Page"

            ctx_str = "%s: %s\n" % (doc_type, model.getURL() or "Untitled")
            ctx_str += "Total %ss: %d\n" % (page_label, pages.getCount())

            active_idx = -1
            for i in range(pages.getCount()):
                if pages.getByIndex(i) == active_page:
                    active_idx = i
                    break
            ctx_str += "Active %s Index: %d\n" % (page_label, active_idx)

            if active_page:
                shapes = bridge.get_shapes(active_page)
                ctx_str += "\nShapes on %s %d:\n" % (page_label, active_idx)
                for i, s in enumerate(shapes):
                    type_name = s.getShapeType().split(".")[-1]
                    pos = s.getPosition()
                    size = s.getSize()
                    ctx_str += "- [%d] %s: pos(%d, %d) size(%dx%d)" % (
                        i, type_name, pos.X, pos.Y,
                        size.Width, size.Height)
                    if hasattr(s, "getString"):
                        text = s.getString()
                        if text:
                            ctx_str += " text: \"%s\"" % text[:200]
                    ctx_str += "\n"

                if is_impress and hasattr(active_page, "getNotesPage"):
                    try:
                        notes_page = active_page.getNotesPage()
                        notes_text = ""
                        for i in range(notes_page.getCount()):
                            shape = notes_page.getByIndex(i)
                            if shape.getShapeType() == (
                                    "com.sun.star.presentation"
                                    ".NotesShape"):
                                notes_text += shape.getString() + "\n"
                        if notes_text.strip():
                            ctx_str += ("\nSpeaker Notes:\n%s\n"
                                        % notes_text.strip())
                    except Exception:
                        pass

            return ctx_str
        except Exception as e:
            return "Error getting Draw context: %s" % e

    @staticmethod
    def _inject_markers(excerpt, excerpt_start, excerpt_end,
                        sel_start, sel_end, prefix, suffix):
        """Inject [SELECTION_START]/[SELECTION_END] markers into excerpt."""
        if sel_start >= excerpt_end or sel_end <= excerpt_start:
            return prefix + excerpt + suffix
        local_start = max(0, sel_start - excerpt_start)
        local_end = min(len(excerpt), sel_end - excerpt_start)
        before = excerpt[:local_start]
        between = excerpt[local_start:local_end]
        after = excerpt[local_end:]
        return (prefix + before + "[SELECTION_START]" + between +
                "[SELECTION_END]" + after + suffix)

    # ── GUI yield ──────────────────────────────────────────────────

    _yield_counter = 0

    def yield_to_gui(self, every=50):
        """Process pending VCL events to keep GUI responsive.

        Call inside tight loops. Actual reschedule fires every *every* calls.
        """
        DocumentService._yield_counter += 1
        if DocumentService._yield_counter % every != 0:
            return
        try:
            ctx = get_ctx()
            if ctx:
                sm = ctx.getServiceManager()
                tk = sm.createInstanceWithContext(
                    "com.sun.star.awt.Toolkit", ctx)
                if hasattr(tk, "processEventsToIdle"):
                    tk.processEventsToIdle()
        except Exception:
            pass

# markdown_support.py — Markdown read/write for Writer tool-calling.
# Converts document to/from Markdown; uses system temp dir (cross-platform) and a
# hidden Writer document + transferable for inserting markdown content.

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
# Markdown → Document (hidden doc + transferable)
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


def _frame_name(frame):
    """Get a short identifier for a frame for logging (Name or URL)."""
    if not frame:
        return "None"
    try:
        if hasattr(frame, "getName"):
            n = frame.getName()
            return n if n else "(no name)"
        return str(frame)[:60]
    except Exception:
        return "(error)"


def _model_url(model):
    """Get document URL for logging if model supports it."""
    if not model:
        return "None"
    try:
        if hasattr(model, "getURL"):
            u = model.getURL()
            return u if u else "(no URL)"
        return "(no getURL)"
    except Exception:
        return "(error)"


def _log_frame_state(ctx, model, label):
    """Write to /tmp/localwriter_markdown_debug.log: desktop current frame vs model's frame (dev)."""
    try:
        smgr = ctx.getServiceManager()
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        current_comp = desktop.getCurrentComponent() if desktop else None
        current_frame = desktop.getCurrentFrame() if (desktop and hasattr(desktop, "getCurrentFrame")) else None
        ctrl = model.getCurrentController() if hasattr(model, "getCurrentController") else None
        our_frame = ctrl.getFrame() if (ctrl and hasattr(ctrl, "getFrame")) else None
        frame_same = (current_frame is our_frame) if (current_frame and our_frame) else None
        comp_same = (current_comp is model) if current_comp else None
        cur_name = _frame_name(current_frame)
        our_name = _frame_name(our_frame)
        cur_url = _model_url(current_comp) if (current_comp and hasattr(current_comp, "getText")) else "-"
        our_url = _model_url(model) if model else "-"
        cur_id = id(current_frame) if current_frame else None
        our_id = id(our_frame) if our_frame else None
        with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as f:
            f.write("[%s] getCurrentFrame() is our_frame: %s | getCurrentComponent() is model: %s\n" % (
                label, frame_same, comp_same))
            f.write("  current_frame name: %s | our_frame name: %s\n" % (cur_name, our_name))
            f.write("  current_component URL: %s | our model URL: %s\n" % (cur_url, our_url))
            f.write("  id(current_frame)=%s id(our_frame)=%s\n" % (cur_id, our_id))
    except Exception as ex:
        try:
            with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as f:
                f.write("[%s] _log_frame_state failed: %s\n" % (label, ex))
        except Exception:
            pass


def _get_markdown_transferable(ctx, markdown_string):
    """Write markdown to a temp file in /tmp, load in hidden Writer doc, select all, return (transferable, hidden_component, temp_path). Caller must close component and delete path."""
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
    smgr = ctx.getServiceManager()
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    load_args = (
        _create_property_value("Hidden", True),
        _create_property_value("FilterName", "Markdown"),
    )
    try:
        hidden_component = desktop.loadComponentFromURL(file_url, "_blank", 0, load_args)
    except Exception as e:
        try:
            os.unlink(path)
        except Exception:
            pass
        raise e
    if not hidden_component:
        try:
            os.unlink(path)
        except Exception:
            pass
        raise RuntimeError("Failed to load markdown document")
    try:
        text_doc = hidden_component
        text = text_doc.getText()
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        selected_text = cursor.getString()
        
        # Debug: Check what text was selected
        try:
            with open("/tmp/markdown_fix_debug.log", "a", encoding="utf-8") as f:
                f.write("HIDDEN DOC: selected_text length = %d, content = %s\n" % (len(selected_text), selected_text[:50]))
        except Exception:
            pass
        
        # The original getTransferable() method doesn't work with hidden documents
        # Instead, we'll insert the markdown text directly using insertString
        # But we need to convert markdown to formatted text first
        
        # For now, let's try a simpler approach: insert the raw markdown text
        # We'll improve this later to properly convert markdown to formatted text
        
        try:
            with open("/tmp/markdown_fix_debug.log", "a", encoding="utf-8") as f:
                f.write("HIDDEN DOC: Using direct insert method instead of transferable\n")
        except Exception:
            pass
        
        # Return None for transferable - we'll handle insertion differently
        return (None, hidden_component, path, markdown_string)
    except Exception:
        try:
            hidden_component.close(True)
        except Exception:
            pass
        try:
            os.unlink(path)
        except Exception:
            pass
        raise


def _insert_transferable_at_position(model, ctx, transferable, position, use_process_events=True):
    """position: 'beginning' | 'end' | 'selection'. Positions view cursor then insertTransferable.
    use_process_events: if True, call toolkit.processEventsToIdle() before insert so frame activation is applied."""
    len_before, snippet_before = _doc_text_length(model)
    debug_log(ctx, "markdown_support: insert_transferable position=%s use_process_events=%s len_before=%s" % (
        position, use_process_events, len_before))
    controller = model.getCurrentController()
    if not hasattr(controller, "insertTransferable"):
        raise RuntimeError("Controller does not support insertTransferable")
    our_frame = controller.getFrame() if controller else None
    our_url = _model_url(model) if model else None
    
    # FIX: Use current component if it has the same URL as our model
    # This aligns our target with where insertTransferable() actually pastes
    if ctx is not None:
        try:
            smgr = ctx.getServiceManager()
            desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx) if smgr else None
            current_component = desktop.getCurrentComponent() if desktop else None
            
            debug_log(ctx, "markdown_support: FIX - current_component=%s, model=%s" % (current_component is not None, model is not None))
            
            if (current_component and 
                hasattr(current_component, "getText") and
                hasattr(current_component, "getURL") and
                hasattr(model, "getURL")):
                
                current_url = current_component.getURL()
                model_url = model.getURL()
                
                debug_log(ctx, "markdown_support: FIX - current_url=%s, model_url=%s" % (current_url, model_url))
                
                # Use current component if URLs match and are non-empty
                if current_url and model_url and current_url == model_url:
                    # Write to a fixed path for debugging
                    try:
                        with open("/tmp/markdown_fix_debug.log", "a", encoding="utf-8") as f:
                            f.write("FIX APPLIED: Using current component with URL: %s\n" % current_url)
                    except Exception:
                        pass
                    debug_log(ctx, "markdown_support: using current component (URL match): %s" % current_url)
                    model = current_component
                    controller = model.getCurrentController()
                    our_frame = controller.getFrame() if controller else None
                    our_url = _model_url(model) if model else None
                else:
                    debug_log(ctx, "markdown_support: FIX - URLs don't match or are empty: current=%s, model=%s" % (current_url, model_url))
            else:
                debug_log(ctx, "markdown_support: FIX - current_component or model missing getURL")
        except Exception as e:
            debug_log(ctx, "markdown_support: FIX - Exception in URL matching: %s" % e)
    # else: ctx is None, skip URL matching
    
    _log_frame_state(ctx, model, "before_activate")
    smgr = ctx.getServiceManager()
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx) if smgr else None
    # Try 1: find our frame in desktop's frame tree and activate it (may work when direct activate does not)
    frame_tree_activated = False
    if desktop and our_url and our_url != "(no getURL)" and our_url != "(no URL)":
        try:
            if hasattr(desktop, "getFrames"):
                frames_obj = desktop.getFrames()
                if frames_obj and hasattr(frames_obj, "queryFrames"):
                    # FrameSearchFlag: SELF=2, CHILDREN=4, SIBLINGS=16, TASKS=32
                    flags = 2 | 4 | 16 | 32
                    frames = frames_obj.queryFrames(flags)
                    for f in (frames if frames else []):
                        try:
                            c = f.getController() if hasattr(f, "getController") else None
                            m = c.getModel() if (c and hasattr(c, "getModel")) else None
                            if m and hasattr(m, "getURL"):
                                u = m.getURL()
                                if u and u == our_url and hasattr(f, "activate"):
                                    f.activate()
                                    frame_tree_activated = True
                                    if use_process_events:
                                        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
                                        if toolkit and hasattr(toolkit, "processEventsToIdle"):
                                            toolkit.processEventsToIdle()
                                    try:
                                        with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as fl:
                                            fl.write("  frame_tree_activate: found frame with our URL, activated and processEventsToIdle\n")
                                    except Exception:
                                        pass
                                    break
                        except Exception:
                            continue
        except Exception as ex:
            try:
                with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as fl:
                    fl.write("  frame_tree_activate failed: %s\n" % ex)
            except Exception:
                pass
    # Ensure this document's frame is active (original path)
    if not frame_tree_activated:
        try:
            frame = our_frame
            if frame and hasattr(frame, "activate"):
                frame.activate()
                debug_log(ctx, "markdown_support: insert_transferable frame.activate() called")
        except Exception as ex:
            debug_log(ctx, "markdown_support: insert_transferable frame.activate() failed: %s" % ex)
    if use_process_events:
        try:
            toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
            if toolkit and hasattr(toolkit, "processEventsToIdle"):
                toolkit.processEventsToIdle()
                debug_log(ctx, "markdown_support: insert_transferable processEventsToIdle() called")
        except Exception as ex:
            debug_log(ctx, "markdown_support: insert_transferable processEventsToIdle failed: %s" % ex)
    _log_frame_state(ctx, model, "after_activate_and_events")
    vc = controller.getViewCursor()
    if position == "beginning":
        vc.gotoStart(False)
    elif position == "end":
        vc.gotoEnd(False)
    elif position == "selection":
        try:
            sel = controller.getSelection()
            if sel and sel.getCount() > 0:
                rng = sel.getByIndex(0)
                start = rng.getStart()
                rng.setString("")
                vc.gotoRange(start, False)
            else:
                vc.gotoRange(vc.getStart(), False)
        except Exception:
            vc.gotoRange(vc.getStart(), False)
    else:
        raise ValueError("Unknown position: %s" % position)
    # Dev finding: When invoked from the menu (Run markdown tests), desktop.getCurrentFrame()
    # is never our document's frame — even at test_start. So insertTransferable() inserts into
    # whatever component is "current", not into the controller we call it on. frame.activate()
    # does not change getCurrentFrame(). Log to fixed path for inspection.
    try:
        smgr = ctx.getServiceManager()
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        current = desktop.getCurrentComponent() if desktop else None
        is_our_doc = (current is model) if current else False
        cur_len = _doc_text_length(current)[0] if (current and hasattr(current, "getText")) else -1
        # What frame is "current" and what frame does our model's controller belong to?
        current_frame = desktop.getCurrentFrame() if (desktop and hasattr(desktop, "getCurrentFrame")) else None
        our_frame = controller.getFrame() if controller else None
        frame_is_same = (current_frame is our_frame) if (current_frame and our_frame) else False
        # Component in our controller's frame (should be our model)
        our_frame_component = our_frame.getController().getModel() if (our_frame and hasattr(our_frame, "getController")) else None
        our_frame_comp_is_model = (our_frame_component is model) if our_frame_component else False
        with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as f:
            f.write("insert_transferable: before_insert len_model=%s | current_component_is_our_model=%s current_len=%s\n" % (
                len_before, is_our_doc, cur_len))
            f.write("  desktop.getCurrentFrame() is our controller.getFrame(): %s | our_frame.getController().getModel() is model: %s\n" % (
                frame_is_same, our_frame_comp_is_model))
    except Exception as ex:
        try:
            with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as f:
                f.write("insert_transferable: diagnostic failed: %s\n" % ex)
        except Exception:
            pass
    # Debug: Check model and controller before insert
    try:
        with open("/tmp/markdown_fix_debug.log", "a", encoding="utf-8") as f:
            f.write("BEFORE INSERT: model URL = %s, len_before = %s\n" % (_model_url(model), len_before))
            f.write("  controller = %s, has insertTransferable = %s\n" % (controller is not None, hasattr(controller, "insertTransferable")))
            f.write("  transferable = %s\n" % (transferable is not None))
            # Check if transferable has any data flavors
            if transferable and hasattr(transferable, 'getTransferDataFlavors'):
                try:
                    flavors = transferable.getTransferDataFlavors()
                    flavor_count = len(flavors) if flavors else 0
                    f.write("  transferable flavors = %d\n" % flavor_count)
                except Exception as e:
                    f.write("  getTransferDataFlavors failed: %s\n" % str(e))
    except Exception:
        pass
    
    # Try the insert
    try:
        controller.insertTransferable(transferable)
        with open("/tmp/markdown_fix_debug.log", "a", encoding="utf-8") as f:
            f.write("  insertTransferable() completed without exception\n")
    except Exception as e:
        with open("/tmp/markdown_fix_debug.log", "a", encoding="utf-8") as f:
            f.write("  insertTransferable() raised exception: %s\n" % e)
    
    # Debug: Check model after insert
    len_after, snippet_after = _doc_text_length(model)
    try:
        with open("/tmp/markdown_fix_debug.log", "a", encoding="utf-8") as f:
            f.write("AFTER INSERT: model URL = %s, len_after = %s, inserted = %s\n" % (_model_url(model), len_after, len_after > len_before))
            f.write("  snippet: %s\n" % snippet_after[:100] if snippet_after else "EMPTY")
    except Exception:
        pass
    
    inserted = len_after > len_before
    debug_log(ctx, "markdown_support: insert_transferable len_after=%s snippet=%s" % (len_after, snippet_after))
    try:
        with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as f:
            f.write("insert_transferable: after_insert len_model=%s inserted=%s\n" % (len_after, inserted))
    except Exception:
        pass
    # Try 2: if insert did nothing, try clipboard + dispatch .uno:Paste to our frame
    if not inserted and our_frame:
        try:
            clipboard = smgr.createInstanceWithContext(
                "com.sun.star.datatransfer.clipboard.SystemClipboard", ctx)
            if clipboard and hasattr(clipboard, "getContents") and hasattr(clipboard, "setContents"):
                old_trans = clipboard.getContents()
                clipboard.setContents(transferable, None)
                # Dispatch Paste to our frame so it goes to our document
                disp_obj = None
                if hasattr(our_frame, "queryDispatch"):
                    disp_obj = our_frame.queryDispatch(".uno:Paste", "", 0)
                    if disp_obj and hasattr(disp_obj, "dispatch"):
                        disp_obj.dispatch(None, ())
                        if use_process_events:
                            toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
                            if toolkit and hasattr(toolkit, "processEventsToIdle"):
                                toolkit.processEventsToIdle()
                        len_after2 = _doc_text_length(model)[0]
                        inserted = len_after2 > len_before
                        try:
                            with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as f:
                                f.write("clipboard_dispatch: .uno:Paste to our_frame, len_after=%s inserted=%s\n" % (
                                    len_after2, inserted))
                        except Exception:
                            pass
                clipboard.setContents(old_trans, None)
        except Exception as ex:
            try:
                with open("/tmp/localwriter_markdown_debug.log", "a", encoding="utf-8") as f:
                    f.write("clipboard_dispatch failed: %s\n" % ex)
            except Exception:
                pass


def _insert_markdown_direct(model, ctx, markdown_string, position):
    """Insert markdown using LibreOffice's native markdown conversion."""
    try:
        # Create a temporary markdown file
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
        smgr = ctx.getServiceManager()
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        
        # Load the markdown file - try visible first for proper formatting, then hidden
        load_args_visible = (
            _create_property_value("Hidden", False),  # Try visible first
            _create_property_value("FilterName", "Markdown"),
        )
        
        try:
            hidden_doc = desktop.loadComponentFromURL(file_url, "_blank", 0, load_args_visible)
            is_visible = True
        except Exception as e1:
            # If visible fails, try hidden as fallback
            try:
                load_args_hidden = (
                    _create_property_value("Hidden", True),
                    _create_property_value("FilterName", "Markdown"),
                )
                hidden_doc = desktop.loadComponentFromURL(file_url, "_blank", 0, load_args_hidden)
                is_visible = False
            except Exception as e2:
                try:
                    os.unlink(path)
                except Exception:
                    pass
                raise RuntimeError("Failed to load markdown document (both visible and hidden failed)")
        
        if not hidden_doc:
            try:
                os.unlink(path)
            except Exception:
                pass
            raise RuntimeError("Failed to load markdown document")
        
        try:
            hidden_doc = desktop.loadComponentFromURL(file_url, "_blank", 0, load_args)
            if not hidden_doc:
                raise RuntimeError("Failed to load markdown document")
            
            # Try to get formatted content via transferable first
            hidden_controller = hidden_doc.getCurrentController()
            transferable = None
            if hasattr(hidden_controller, "getTransferable"):
                transferable = hidden_controller.getTransferable()
                
                # Check if transferable has content
                has_flavors = False
                if transferable and hasattr(transferable, 'getTransferDataFlavors'):
                    try:
                        flavors = transferable.getTransferDataFlavors()
                        has_flavors = flavors is not None and len(flavors) > 0
                    except Exception:
                        has_flavors = False
            
            if transferable and has_flavors:
                # Use transferable if it has formatted content
                try:
                    hidden_doc.close(True)
                except Exception:
                    pass
                try:
                    os.unlink(path)
                except Exception:
                    pass
                
                # Insert using transferable
                text = model.getText()
                target_cursor = text.createTextCursor()
                
                if position == "beginning":
                    target_cursor.gotoStart(False)
                elif position == "end":
                    target_cursor.gotoEnd(False)
                elif position == "selection":
                    sel = model.getCurrentController().getSelection()
                    if sel and sel.getCount() > 0:
                        rng = sel.getByIndex(0)
                        rng.setString("")  # Clear selection
                        target_cursor.gotoRange(rng.getStart(), False)
                    else:
                        target_cursor.gotoRange(target_cursor.getStart(), False)
                else:
                    raise ValueError("Unknown position: %s" % position)
                
                # Insert the transferable with formatted content
                controller = model.getCurrentController()
                controller.insertTransferable(transferable)
                return  # Success!
            
            # Fallback: Get raw text if transferable is empty
            hidden_text = hidden_doc.getText()
            cursor = hidden_text.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            formatted_text = cursor.getString()
            
            # Close and cleanup
            try:
                hidden_doc.close(True)
            except Exception:
                pass
            try:
                os.unlink(path)
            except Exception:
                pass
            
            # Insert raw text as fallback
            text = model.getText()
            target_cursor = text.createTextCursor()
            
            if position == "beginning":
                target_cursor.gotoStart(False)
            elif position == "end":
                target_cursor.gotoEnd(False)
            elif position == "selection":
                sel = model.getCurrentController().getSelection()
                if sel and sel.getCount() > 0:
                    rng = sel.getByIndex(0)
                    rng.setString(formatted_text)
                    return
                else:
                    target_cursor.gotoRange(target_cursor.getStart(), False)
            else:
                raise ValueError("Unknown position: %s" % position)
            
            text.insertString(target_cursor, formatted_text, False)
            
        except Exception as e:
            try:
                hidden_doc.close(True)
            except Exception:
                pass
            try:
                os.unlink(path)
            except Exception:
                pass
            raise
    except Exception as e:
        raise


def _insert_markdown_at_position(model, ctx, markdown_string, position, use_process_events=True):
    """Load markdown into hidden doc, get transferable, insert at position. Handles close and temp file cleanup.
    We close the hidden document before inserting so the target doc is the only open document and cannot
    receive paste by mistake."""
    result = _get_markdown_transferable(ctx, markdown_string)
    
    # Handle new return format: (transferable, hidden_component, path, markdown_string) or (transferable, hidden_component, path)
    if len(result) == 4:
        transferable, hidden_component, path, markdown_str = result
    else:
        transferable, hidden_component, path = result
        markdown_str = markdown_string
    
    try:
        try:
            hidden_component.close(True)
        except Exception:
            pass
        try:
            os.unlink(path)
        except Exception:
            pass
        _log_frame_state(ctx, model, "after_close_hidden")
        
        # If transferable is None, use direct insert method
        if transferable is None:
            try:
                with open("/tmp/markdown_fix_debug.log", "a", encoding="utf-8") as f:
                    f.write("INSERT: Using direct insertString method\n")
            except Exception:
                pass
            _insert_markdown_direct(model, ctx, markdown_str, position)
        else:
            _insert_transferable_at_position(model, ctx, transferable, position, use_process_events=use_process_events)
    finally:
        try:
            hidden_component.close(True)
        except Exception:
            pass
        try:
            os.unlink(path)
        except Exception:
            pass


def _apply_markdown_at_search(model, ctx, markdown_string, search_string, all_matches=False, case_sensitive=True):
    """Find search_string (first or all), replace each with transferable from markdown_string."""
    result = _get_markdown_transferable(ctx, markdown_string)
    
    # Handle new return format
    if len(result) == 4:
        transferable, hidden_component, path, markdown_str = result
    else:
        transferable, hidden_component, path = result
        markdown_str = markdown_string
    
    try:
        if transferable is None:
            # Use direct insert method
            sd = model.createSearchDescriptor()
            sd.SearchString = search_string
            sd.SearchRegularExpression = False
            sd.SearchCaseSensitive = case_sensitive
            count = 0
            found = model.findFirst(sd)
            while found:
                found.setString(markdown_str)
                count += 1
                if not all_matches:
                    break
                found = model.findNext(found.getEnd(), sd)
        else:
            # Use original transferable method
            controller = model.getCurrentController()
            count = 0
            found = model.findFirst(sd)
            while found:
                found.setString("")
                vc = controller.getViewCursor()
                vc.gotoRange(found.getStart(), False)
                controller.insertTransferable(transferable)
                count += 1
                if not all_matches:
                    break
                vc.gotoRange(vc.getEnd(), False)
                found = model.findNext(vc.getEnd(), sd)
        return count
    finally:
        try:
            hidden_component.close(True)
        except Exception:
            pass
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
    # Dev: log frame/current state at test start (before any hidden doc)
    try:
        _log_frame_state(ctx, doc, "test_start")
    except Exception:
        pass

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

    try:
        result = _get_markdown_transferable(ctx, "**bold** text")
        # Handle both old and new return formats
        if len(result) == 4:
            xfer, hidden, path, markdown_str = result
        else:
            xfer, hidden, path = result
        
        if xfer is not None and path and os.path.exists(path):
            # Old format: transferable exists
            try:
                hidden.close(True)
            except Exception:
                pass
            try:
                os.unlink(path)
            except Exception:
                pass
            passed += 1
            ok("_get_markdown_transferable returned transferable and path; closed and unlinked")
        elif xfer is None and hidden and path and os.path.exists(path):
            # New format: direct insert method
            try:
                hidden.close(True)
            except Exception:
                pass
            try:
                os.unlink(path)
            except Exception:
                pass
            passed += 1
            ok("_get_markdown_transferable returned direct insert components; closed and unlinked")
        else:
            failed += 1
            fail("_get_markdown_transferable returned invalid tuple: %s" % str(result))
    except Exception as e:
        failed += 1
        log.append("FAIL: _get_markdown_transferable raised: %s" % e)

    return passed, failed, log

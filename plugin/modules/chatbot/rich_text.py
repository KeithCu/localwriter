import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.awt import Rectangle
from com.sun.star.awt import WindowDescriptor
from com.sun.star.awt.WindowClass import TOP, CONTAINER

from plugin.framework.logging import debug_log


_CREATION_GUARDS = set()


def create_embedded_writer_doc(ctx, parent_window, placeholder_control):
    """
    Creates an embedded Writer document that replaces a placeholder text control.
    """
    guard_key = id(placeholder_control)
    if guard_key in _CREATION_GUARDS:
        debug_log(
            "create_embedded_writer_doc: re-entrant call detected; aborting to avoid loops (placeholder_id=%s)"
            % guard_key,
            context="Chat",
        )
        return None

    _CREATION_GUARDS.add(guard_key)
    try:
        smgr = ctx.ServiceManager

        # We need the parent's actual toolkit window
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)

        # Get position of the placeholder
        pos_size = placeholder_control.getPosSize()
        x, y, w, h = pos_size.X, pos_size.Y, pos_size.Width, pos_size.Height
        debug_log(f"create_embedded_writer_doc: placeholder pos: ({x}, {y}, {w}, {h})", context="Chat")

        # 1. Create an embedded container window at the exact position.
        # On some LibreOffice builds, the toolkit-created window lacks a GUI peer
        # (hasPeer=False), which prevents XFrame::initialize from working.
        # We try multiple descriptor combinations and only proceed when hasPeer=True.
        placeholder_peer = None
        try:
            if hasattr(placeholder_control, "getPeer"):
                placeholder_peer = placeholder_control.getPeer()
        except Exception:
            placeholder_peer = None

        root_peer = None
        try:
            if hasattr(parent_window, "getPeer"):
                root_peer = parent_window.getPeer()
        except Exception:
            root_peer = None

        debug_log(
            "create_embedded_writer_doc: peers placeholder_peer_ok=%s root_peer_ok=%s"
            % (bool(placeholder_peer), bool(root_peer)),
            context="Chat",
        )

        parent_peer_candidates = [("placeholder", placeholder_peer), ("root", root_peer)]
        type_candidates = [("CONTAINER", CONTAINER), ("TOP", TOP)]
        service_candidates = ["", "control", "dockingwindow", "container", "framewindow"]

        win = None
        last_err = None
        for parent_label, parent_peer in parent_peer_candidates:
            for type_label, type_val in type_candidates:
                for service_name in service_candidates:
                    desc = WindowDescriptor()
                    desc.Type = type_val
                    desc.WindowServiceName = service_name
                    desc.ParentIndex = -1
                    if parent_peer:
                        desc.Parent = parent_peer
                        desc.ParentIndex = 0
                    else:
                        desc.Parent = parent_window

                    desc.Bounds = Rectangle(x, y, w, h)
                    # Some LO UNO environments don't expose WindowAttribute constants
                    # via Python imports, so we keep the original numeric flags.
                    desc.WindowAttributes = 2 | 4

                    debug_log(
                        "create_embedded_writer_doc: trying parent=%s type=%s service=%r"
                        % (parent_label, type_label, service_name),
                        context="Chat",
                    )

                    win = toolkit.createWindow(desc)
                    if win and hasattr(win, "setVisible"):
                        win.setVisible(True)

                        # Give VCL a chance to realize the window peer. On some LO
                        # builds `getPeer()` is only populated after events run.
                        try:
                            if hasattr(toolkit, "processEventsToIdle"):
                                toolkit.processEventsToIdle()
                        except Exception:
                            pass

                    has_peer = bool(win and getattr(win, "getPeer", None) and win.getPeer())
                    debug_log(
                        "create_embedded_writer_doc: created win_ok=%s hasPeer=%s (parent=%s type=%s service=%r)"
                        % (bool(win), has_peer, parent_label, type_label, service_name),
                        context="Chat",
                    )

                    # One more re-check after events processing.
                    if win and has_peer is False:
                        try:
                            if hasattr(toolkit, "processEventsToIdle"):
                                toolkit.processEventsToIdle()
                        except Exception:
                            pass
                        has_peer = bool(win and getattr(win, "getPeer", None) and win.getPeer())
                        debug_log(
                            "create_embedded_writer_doc: post-idle recheck hasPeer=%s (parent=%s type=%s service=%r)"
                            % (has_peer, parent_label, type_label, service_name),
                            context="Chat",
                        )

                    # Never attempt to initialize a Frame on a window without a GUI peer.
                    if not has_peer:
                        continue

                    try:
                        frame = smgr.createInstanceWithContext("com.sun.star.frame.Frame", ctx)
                        debug_log(
                            "create_embedded_writer_doc: initializing Frame (parent=%s type=%s service=%r, hasPeer=%s)"
                            % (parent_label, type_label, service_name, has_peer),
                            context="Chat",
                        )
                        frame.initialize(win)

                        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
                        frame.setCreator(desktop)

                        props = (
                            PropertyValue("Hidden", 0, False, 0),
                            PropertyValue("ReadOnly", 0, True, 0),
                            PropertyValue("AsTemplate", 0, True, 0),
                        )

                        import uuid
                        frame_name = "chat_sidebar_rich_text_frame_" + str(uuid.uuid4()).replace("-", "")
                        frame.setName(frame_name)

                        desktop.getFrames().append(frame)
                        doc = desktop.loadComponentFromURL("private:factory/swriter", frame_name, 0, props)

                        try:
                            ctrl = doc.getCurrentController()
                            if ctrl:
                                view_settings = ctrl.getViewSettings()
                                view_settings.ShowRulers = False
                                view_settings.ZoomType = 0  # Optimal zoom
                        except Exception as e:
                            debug_log(
                                "create_embedded_writer_doc view settings error: %s" % e,
                                context="Chat",
                            )

                        return {"doc": doc, "win": win}
                    except Exception as e:
                        last_err = e
                        debug_log(
                            "create_embedded_writer_doc: frame.initialize/load failed parent=%s type=%s service=%r hasPeer=%s err=%s"
                            % (parent_label, type_label, service_name, has_peer, e),
                            context="Chat",
                        )
                        try:
                            if "frame" in locals() and hasattr(frame, "dispose"):
                                frame.dispose()
                        except Exception:
                            pass
        if last_err:
            debug_log(
                "create_embedded_writer_doc: all container candidates failed; last_err=%s" % last_err,
                context="Chat",
            )
        else:
            debug_log(
                "create_embedded_writer_doc: no container window candidates succeeded (no usable GUI peer)",
                context="Chat",
            )
        return None
    except Exception as e:
        debug_log(f"create_embedded_writer_doc error: {e}", context="Chat")
        return None
    finally:
        _CREATION_GUARDS.discard(guard_key)

def append_rich_text(doc, text, role):
    """
    Appends text to the embedded Writer document with different colors based on the role.
    """
    if not doc:
        return

    try:
        text_obj = doc.getText()
        cursor = text_obj.createTextCursor()
        cursor.gotoEnd(False)

        # Add new line if not at start
        if len(text_obj.getString()) > 0:
            text_obj.insertControlCharacter(cursor, uno.Enum("com.sun.star.text.ControlCharacter", "PARAGRAPH_BREAK"), False)

        cursor.gotoEnd(False)

        # Set colors
        if role == "user":
            cursor.CharColor = 0x0000FF # Blue
            cursor.CharWeight = uno.getConstantByName("com.sun.star.awt.FontWeight.BOLD")
            text_obj.insertString(cursor, "You: ", False)
            cursor.gotoEnd(False)
            cursor.CharColor = -1 # Default
            cursor.CharWeight = uno.getConstantByName("com.sun.star.awt.FontWeight.NORMAL")
            text_obj.insertString(cursor, text, False)
        elif role == "assistant":
            cursor.CharColor = 0x008000 # Green
            cursor.CharWeight = uno.getConstantByName("com.sun.star.awt.FontWeight.BOLD")
            text_obj.insertString(cursor, "Assistant: ", False)
            cursor.gotoEnd(False)
            cursor.CharColor = -1
            cursor.CharWeight = uno.getConstantByName("com.sun.star.awt.FontWeight.NORMAL")
            text_obj.insertString(cursor, text, False)
        elif role == "system" or role == "greeting":
            cursor.CharColor = 0x808080 # Gray
            cursor.CharWeight = uno.getConstantByName("com.sun.star.awt.FontWeight.NORMAL")
            text_obj.insertString(cursor, text, False)
        else:
            cursor.CharColor = -1
            cursor.CharWeight = uno.getConstantByName("com.sun.star.awt.FontWeight.NORMAL")
            text_obj.insertString(cursor, text, False)

        # Scroll to bottom using the view cursor
        # Actually in an embedded doc without a full UI controller, view cursor might not exist or work right away.
        # But we can try:
        try:
            controllers = doc.getCurrentController()
            if controllers:
                view_cursor = controllers.getViewCursor()
                view_cursor.gotoEnd(False)
        except Exception:
            pass

    except Exception as e:
        debug_log(f"append_rich_text error: {e}", context="Chat")

def clear_rich_text(doc, greeting=""):
    """
    Clears the embedded Writer document and optionally adds a greeting.
    """
    if not doc:
        return

    try:
        text_obj = doc.getText()
        cursor = text_obj.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        cursor.setString("")

        if greeting:
            append_rich_text(doc, greeting, "greeting")
    except Exception as e:
        debug_log(f"clear_rich_text error: {e}", context="Chat")

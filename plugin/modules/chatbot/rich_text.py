import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.awt import Rectangle
from com.sun.star.awt import WindowDescriptor
from com.sun.star.awt.WindowClass import TOP, CONTAINER

from plugin.framework.logging import debug_log


def create_embedded_writer_doc(ctx, parent_window, placeholder_control):
    """
    Creates an embedded Writer document that replaces a placeholder text control.
    """
    try:
        smgr = ctx.ServiceManager

        # We need the parent's actual toolkit window
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)

        # Get position of the placeholder
        pos_size = placeholder_control.getPosSize()
        x, y, w, h = pos_size.X, pos_size.Y, pos_size.Width, pos_size.Height
        debug_log(f"create_embedded_writer_doc: placeholder pos: ({x}, {y}, {w}, {h})", context="Chat")

        # 1. Create a container window at the exact position
        desc = WindowDescriptor()
        desc.Type = CONTAINER
        desc.WindowServiceName = "container"
        desc.ParentIndex = -1

        # It needs a parent window, we will try to get it from the toolkit or dialog
        if hasattr(parent_window, "getPeer"):
            peer = parent_window.getPeer()
            if peer:
                desc.Parent = peer
        else:
            desc.Parent = parent_window

        desc.Bounds = Rectangle(x, y, w, h)

        # WAB_CLIPCHILDREN | WAB_SIZEABLE
        desc.WindowAttributes = 2 | 4

        win = toolkit.createWindow(desc)

        # Make the embedded window visible
        if hasattr(win, "setVisible"):
            win.setVisible(True)

        # 2. Create the Frame
        frame = smgr.createInstanceWithContext("com.sun.star.frame.Frame", ctx)
        frame.initialize(win)

        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        frame.setCreator(desktop)

        # 3. Load the Writer Document inside the frame
        props = (
            PropertyValue("Hidden", 0, False, 0),
            PropertyValue("ReadOnly", 0, True, 0),
            PropertyValue("AsTemplate", 0, True, 0)
        )

        import uuid
        frame_name = "chat_sidebar_rich_text_frame_" + str(uuid.uuid4()).replace("-", "")
        frame.setName(frame_name)

        # We must append the frame to the desktop's frame list so the desktop can find it
        desktop.getFrames().append(frame)

        # Notice we use the exact frame name to load it *into* the frame we just created
        doc = desktop.loadComponentFromURL("private:factory/swriter", frame_name, 0, props)

        # Hide the rulers and set some nice view settings
        try:
            ctrl = doc.getCurrentController()
            if ctrl:
                view_settings = ctrl.getViewSettings()
                view_settings.ShowRulers = False
                view_settings.ZoomType = 0  # Optimal zoom
        except Exception as e:
            debug_log(f"create_embedded_writer_doc view settings error: {e}", context="Chat")

        return {"doc": doc, "win": win}
    except Exception as e:
        debug_log(f"create_embedded_writer_doc error: {e}", context="Chat")
        return None

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

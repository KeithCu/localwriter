# Chat with Document - Sidebar Panel implementation
# Implements XUIElementFactory and XToolPanel for LibreOffice Writer sidebar

import os
import uno
import unohelper

# Import uno first to init bridge; minimize com.sun.star.awt to avoid registration issues
from com.sun.star.ui import XUIElementFactory, XUIElement, XToolPanel, XSidebarPanel
from com.sun.star.awt import XActionListener


def _get_arg(args, name):
    """Extract PropertyValue from args by Name."""
    for pv in args:
        if hasattr(pv, "Name") and pv.Name == name:
            return pv.Value
    return None


def _debug_log(ctx, msg):
    """Write one line to debug log in LibreOffice user config dir."""
    for path in _debug_log_paths(ctx):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            return
        except Exception:
            continue


def _debug_log_paths(ctx):
    """Candidate paths for debug log (same dir as localwriter.json)."""
    out = []
    try:
        path_settings = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.util.PathSettings", ctx)
        user_config = getattr(path_settings, "UserConfig", "")
        if user_config.startswith("file://"):
            user_config = str(uno.fileUrlToSystemPath(user_config))
        out.append(os.path.join(user_config, "localwriter_chat_debug.log"))
    except Exception:
        pass
    out.append(os.path.expanduser("~/localwriter_chat_debug.log"))
    out.append("/tmp/localwriter_chat_debug.log")
    return out


class SendButtonListener(unohelper.Base, XActionListener):
    """Listener for the Send button - runs chat with document, updates response area."""

    def __init__(self, ctx, frame, query_control, response_control):
        self.ctx = ctx
        self.frame = frame
        self.query_control = query_control
        self.response_control = response_control

    def actionPerformed(self, evt):
        try:
            query_text = ""
            if self.query_control and self.query_control.getModel():
                query_text = (self.query_control.getModel().Text or "").strip()
            if not query_text:
                from main import MainJob
                job = MainJob(self.ctx)
                query_text = job.input_box("Ask a question about your document:", "Chat with Document", "").strip()
            if not query_text:
                return

            from main import MainJob
            job = MainJob(self.ctx)
            model = None
            if self.frame:
                try:
                    model = self.frame.getController().getModel()
                except Exception:
                    pass
            if not model:
                desktop = job.ctx.getServiceManager().createInstanceWithContext(
                    "com.sun.star.frame.Desktop", job.ctx)
                model = desktop.getCurrentComponent()
            if not model or not hasattr(model, "getText"):
                job.show_error("No document open.", "Chat with Document")
                return

            max_context = int(job.get_config("chat_context_length", 8000))
            doc_text = job.get_full_document_text(model, max_context)
            if not doc_text.strip():
                job.show_error("Document is empty.", "Chat with Document")
                return

            prompt = "Document content:\n\n%s\n\nUser question: %s" % (doc_text, query_text)
            system_prompt = job.get_config("chat_system_prompt",
                "You are a helpful assistant. Answer the user's question based on the document content provided.")
            max_tokens = int(job.get_config("chat_max_tokens", 512))
            api_type = str(job.get_config("api_type", "completions")).lower()

            doc_cursor = None
            if not (self.response_control and self.response_control.getModel()):
                try:
                    text = model.getText()
                    doc_cursor = text.createTextCursor()
                    doc_cursor.gotoEnd(False)
                    doc_cursor.insertString("\n\n--- Chat response ---\n\n", False)
                except Exception:
                    pass

            def append_chunk(chunk_text):
                if self.response_control and self.response_control.getModel():
                    current = self.response_control.getModel().Text or ""
                    self.response_control.getModel().Text = current + chunk_text
                elif doc_cursor is not None:
                    doc_cursor.insertString(chunk_text, False)

            job.stream_completion(prompt, system_prompt, max_tokens, api_type, append_chunk)

            if self.query_control and self.query_control.getModel():
                self.query_control.getModel().Text = ""
        except Exception as e:
            try:
                from main import MainJob
                job = MainJob(self.ctx)
                job.show_error(str(e), "Chat with Document")
            except Exception:
                pass

    def disposing(self, evt):
        pass


class ChatPanel(unohelper.Base, XToolPanel, XSidebarPanel, XUIElement):
    """Panel implementing XToolPanel - provides getWindow() for the sidebar."""

    def __init__(self, ctx, resource_url, frame, parent_window):
        self.ctx = ctx
        self.resource_url = resource_url
        self.frame = frame
        self.parent_window = parent_window
        self._window = None
        _debug_log(ctx, "ChatPanel.__init__ done")
        # Show a message box to confirm panel initialization
        try:
            sm = ctx.getServiceManager()
            toolkit = sm.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
            parent = self.parent_window or toolkit.getDesktopWindow()
            box = toolkit.createMessageBox(parent, 0, 0, 200, 100, "ChatPanel Initialized", "Chat Panel")
            box.execute()
        except Exception as e:
            _debug_log(ctx, "Failed to show init MessageBox: %s" % (e,))

    def getWindow(self):
        """Return the panel's XWindow (required by XToolPanel)."""
        _debug_log(self.ctx, "ChatPanel.getWindow called")
        if self._window is None:
            self._create_panel()
        return self._window

    def getHeightForWidth(self, width):
        """Return the preferred height for the given width (required by XSidebarPanel)."""
        return 280

    def _create_panel(self):
        """Create the panel window and embed ChatPanelDialog."""
        _debug_log(self.ctx, "_create_panel entered")
        sm = self.ctx.getServiceManager()
        toolkit = sm.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)

        parent_peer = self.parent_window

        desc = uno.createUnoStruct("com.sun.star.awt.WindowDescriptor")
        desc.Type = 1
        desc.WindowServiceName = "window"
        desc.Parent = parent_peer
        desc.Bounds = uno.createUnoStruct("com.sun.star.awt.Rectangle", 0, 0, 220, 280)
        desc.WindowAttributes = 1 | 512

        try:
            peer = toolkit.createWindow(desc)
            self._window = peer
        except Exception:
            desc.WindowServiceName = ""
            try:
                peer = toolkit.createWindow(desc)
                self._window = peer
            except Exception as e:
                raise RuntimeError("Could not create panel window: " + str(e))

        try:
            from com.sun.star.awt import PosSize
            flags = PosSize.POSSIZE
        except ImportError:
            flags = 15
        self._window.setPosSize(0, 0, 220, 280, flags)
        self._window.setVisible(True)

        self._create_controls(toolkit)

    def _create_controls_fallback(self, toolkit):
        """Fallback: simple button that opens Chat with Document (no inline edit)."""
        try:
            btn_desc = uno.createUnoStruct("com.sun.star.awt.WindowDescriptor")
            btn_desc.Type = 1
            btn_desc.WindowServiceName = "pushbutton"
            btn_desc.Parent = self._window
            btn_desc.Bounds = uno.createUnoStruct("com.sun.star.awt.Rectangle", 8, 8, 200, 26)
            btn_desc.WindowAttributes = 1
            btn = toolkit.createWindow(btn_desc)
            btn.setPosSize(8, 8, 200, 26, 15)
            btn.setVisible(True)
            if hasattr(btn, "setPropertyValue"):
                btn.setPropertyValue("Label", "Ask about document (opens dialog)")
            if hasattr(btn, "addActionListener"):
                btn.addActionListener(SendButtonListener(self.ctx, self.frame, None, None))
        except Exception as e:
            _debug_log(self.ctx, "Fallback also failed: %s" % (e,))

    def _create_controls(self, toolkit):
        """Create query input, response area, and Send button using UnoControl instances."""
        try:
            from com.sun.star.awt import PosSize
            flags = PosSize.POSSIZE
        except ImportError:
            flags = 15
        _debug_log(self.ctx, "_create_controls entered")
        try:
            sm = self.ctx.getServiceManager()

            # Create control models
            resp_model = sm.createInstanceWithContext("com.sun.star.awt.UnoControlEditModel", self.ctx)
            resp_model.MultiLine = True
            resp_model.ReadOnly = True
            resp_model.Text = ""

            query_model = sm.createInstanceWithContext("com.sun.star.awt.UnoControlEditModel", self.ctx)
            query_model.Text = ""

            btn_model = sm.createInstanceWithContext("com.sun.star.awt.UnoControlButtonModel", self.ctx)
            btn_model.Label = "Send"

            # Create controls
            response_ctrl = sm.createInstanceWithContext("com.sun.star.awt.UnoControlEdit", self.ctx)
            response_ctrl.setModel(resp_model)
            response_ctrl.createPeer(toolkit, self._window)
            response_ctrl.setPosSize(4, 16, 212, 180, flags)
            response_ctrl.setVisible(True)
            _debug_log(self.ctx, "response created")

            query_ctrl = sm.createInstanceWithContext("com.sun.star.awt.UnoControlEdit", self.ctx)
            query_ctrl.setModel(query_model)
            query_ctrl.createPeer(toolkit, self._window)
            query_ctrl.setPosSize(4, 212, 212, 24, flags)
            query_ctrl.setVisible(True)

            send_btn = sm.createInstanceWithContext("com.sun.star.awt.UnoControlButton", self.ctx)
            send_btn.setModel(btn_model)
            send_btn.createPeer(toolkit, self._window)
            send_btn.setPosSize(4, 240, 100, 22, flags)
            send_btn.setVisible(True)
            _debug_log(self.ctx, "all controls created")

            send_btn.addActionListener(SendButtonListener(
                self.ctx, self.frame, query_ctrl, response_ctrl))
        except Exception as e:
            _debug_log(self.ctx, "Chat panel _create_controls failed: %s" % (e,))
            import traceback
            _debug_log(self.ctx, traceback.format_exc())
            _create_controls_fallback(self, toolkit)

    def getRealInterface(self):
        return self

    @property
    def Frame(self):
        return self.frame

    @property
    def ResourceURL(self):
        return self.resource_url

    @property
    def Type(self):
        try:
            from com.sun.star.ui import UIElementType
            return UIElementType.TOOLPANEL
        except ImportError:
            return 6


class ChatPanelFactory(unohelper.Base, XUIElementFactory):
    """Factory that creates ChatPanel instances for the sidebar."""

    def __init__(self, ctx):
        self.ctx = ctx

    def createUIElement(self, resource_url, args):
        """Create a ChatPanel for private:resource/toolpanel/ChatPanelFactory/ChatPanel."""
        _debug_log(self.ctx, "ChatPanelFactory.createUIElement called: %s" % resource_url)
        if "ChatPanel" not in resource_url:
            from com.sun.star.container import NoSuchElementException
            raise NoSuchElementException("Unknown resource: " + resource_url)

        frame = _get_arg(args, "Frame")
        parent_window = _get_arg(args, "ParentWindow")

        if not parent_window:
            from com.sun.star.lang import IllegalArgumentException
            raise IllegalArgumentException("ParentWindow is required")

        _debug_log(self.ctx, "Creating ChatPanel instance")
        panel = ChatPanel(self.ctx, resource_url, frame, parent_window)
        _debug_log(self.ctx, "ChatPanel created, returning")
        return panel


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ChatPanelFactory,
    "org.extension.localwriter.ChatPanelFactory",
    ("com.sun.star.ui.UIElementFactory",),
)

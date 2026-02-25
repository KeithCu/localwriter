"""Sidebar panel factory — UNO wiring for the chat panel.

Creates the XUIElement and XToolPanel that LibreOffice needs for
the sidebar. Loads the XDL dialog, wires controls to the framework's
ChatSession and ChatToolAdapter, and handles streaming responses.

Registered as a UNO component in META-INF/manifest.xml.
"""

import json
import logging
import os
import queue
import sys
import threading

# Ensure plugin parent is on path so "plugin.xxx" imports work
_this_dir = os.path.dirname(os.path.abspath(__file__))
_plugin_dir = os.path.join(_this_dir, os.pardir, os.pardir)
_parent = os.path.normpath(os.path.join(_plugin_dir, os.pardir))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

log = logging.getLogger("localwriter.chatbot.factory")

EXTENSION_ID = "org.extension.localwriter"
XDL_PATH = "LocalWriterDialogs/ChatPanelDialog.xdl"


def _get_arg(args, name):
    """Extract PropertyValue from UNO args by Name."""
    for pv in args:
        if hasattr(pv, "Name") and pv.Name == name:
            return pv.Value
    return None


def _get_optional(root_window, name):
    """Get an optional control from the XDL root window."""
    try:
        ctrl = root_window.getControl(name)
        return ctrl
    except Exception:
        return None


try:
    import uno
    import unohelper
    from com.sun.star.ui import XUIElementFactory, XUIElement, XToolPanel, XSidebarPanel
    from com.sun.star.ui.UIElementType import TOOLPANEL
    from com.sun.star.awt import XActionListener

    class ChatToolPanel(unohelper.Base, XToolPanel, XSidebarPanel):
        """Holds the panel window; implements XToolPanel + XSidebarPanel."""

        def __init__(self, panel_window, parent_window, ctx):
            self.ctx = ctx
            self.PanelWindow = panel_window
            self.Window = panel_window
            self.parent_window = parent_window

        def getWindow(self):
            return self.Window

        def createAccessible(self, parent_accessible):
            return self.PanelWindow

        def getHeightForWidth(self, width):
            if self.parent_window and self.PanelWindow and width > 0:
                parent_rect = self.parent_window.getPosSize()
                h = parent_rect.Height if parent_rect.Height > 0 else 280
                self.PanelWindow.setPosSize(0, 0, width, h, 15)
            return uno.createUnoStruct(
                "com.sun.star.ui.LayoutSize", 280, -1, 280)

        def getMinimalWidth(self):
            return 180

    class ChatPanelElement(unohelper.Base, XUIElement):
        """XUIElement wrapper — creates panel in getRealInterface()."""

        def __init__(self, ctx, frame, parent_window, resource_url):
            self.ctx = ctx
            self.xFrame = frame
            self.xParentWindow = parent_window
            self.ResourceURL = resource_url
            self.Frame = frame
            self.Type = TOOLPANEL
            self.toolpanel = None
            self.m_panelRootWindow = None

        def getRealInterface(self):
            if not self.toolpanel:
                try:
                    root_window = self._create_panel_window()
                    self.toolpanel = ChatToolPanel(
                        root_window, self.xParentWindow, self.ctx)
                    self._wire_controls(root_window)
                except Exception:
                    log.exception("getRealInterface failed")
                    raise
            return self.toolpanel

        def _create_panel_window(self):
            """Load the XDL dialog as a container window."""
            pip = self.ctx.getValueByName(
                "/singletons/com.sun.star.deployment"
                ".PackageInformationProvider")
            base_url = pip.getPackageLocation(EXTENSION_ID)
            dialog_url = base_url + "/" + XDL_PATH

            provider = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.awt.ContainerWindowProvider", self.ctx)
            self.m_panelRootWindow = provider.createContainerWindow(
                dialog_url, "", self.xParentWindow, None)

            if self.m_panelRootWindow:
                self.m_panelRootWindow.setVisible(True)
            parent_rect = self.xParentWindow.getPosSize()
            if parent_rect.Width > 0 and parent_rect.Height > 0:
                self.m_panelRootWindow.setPosSize(
                    0, 0, parent_rect.Width, parent_rect.Height, 15)

            return self.m_panelRootWindow

        def _wire_controls(self, root_window):
            """Attach listeners to UI controls using the new framework."""
            if not hasattr(root_window, "getControl"):
                return

            send_btn = root_window.getControl("send")
            query_ctrl = root_window.getControl("query")
            response_ctrl = root_window.getControl("response")
            stop_btn = _get_optional(root_window, "stop")
            status_ctrl = _get_optional(root_window, "status")
            clear_btn = _get_optional(root_window, "clear")

            # ── Bootstrap framework ────────────────────────────────

            from plugin.main import bootstrap, get_services, get_tools
            bootstrap(self.ctx)

            services = get_services()
            tools = get_tools()

            # ── Determine doc type and system prompt ───────────────

            from plugin.modules.chatbot.constants import (
                get_system_prompt, get_greeting)

            doc = None
            doc_type = "writer"
            if self.xFrame:
                try:
                    doc = self.xFrame.getController().getModel()
                except Exception:
                    pass
            if doc is None:
                try:
                    smgr = self.ctx.getServiceManager()
                    desktop = smgr.createInstanceWithContext(
                        "com.sun.star.frame.Desktop", self.ctx)
                    doc = desktop.getCurrentComponent()
                except Exception:
                    pass

            if doc:
                try:
                    doc_svc = services.document
                    doc_type = doc_svc.detect_doc_type(doc) or "writer"
                except Exception:
                    pass

            # Extra instructions from config
            extra = ""
            try:
                cfg = services.config.proxy_for("chatbot")
                extra = cfg.get("system_prompt") or ""
            except Exception:
                pass

            system_prompt = get_system_prompt(doc_type, extra)

            # ── Create session and adapter ─────────────────────────

            from plugin.modules.chatbot.panel import (
                ChatSession, ChatToolAdapter, SendButtonListener)

            session = ChatSession(system_prompt)
            adapter = ChatToolAdapter(tools, services)

            # ── Wire send button ───────────────────────────────────

            listener = SendButtonListener(services, session, adapter)

            # Connect UI callbacks
            def set_status(text):
                try:
                    if status_ctrl:
                        status_ctrl.setText(text)
                except Exception:
                    pass

            def append_response(text, is_thinking=False):
                try:
                    if response_ctrl and response_ctrl.getModel():
                        current = response_ctrl.getModel().Text or ""
                        response_ctrl.getModel().Text = current + text
                        # Scroll to bottom
                        length = len(response_ctrl.getModel().Text)
                        response_ctrl.setSelection(
                            uno.createUnoStruct(
                                "com.sun.star.awt.Selection",
                                length, length))
                except Exception:
                    pass

            def set_buttons(send_enabled, stop_enabled):
                for ctrl, enabled in [(send_btn, send_enabled),
                                      (stop_btn, stop_enabled)]:
                    if ctrl and ctrl.getModel():
                        ctrl.getModel().Enabled = bool(enabled)

            def on_done():
                set_buttons(True, False)
                set_status("Ready")

            listener.on_status = set_status
            listener.on_append_response = append_response
            listener.on_set_buttons = set_buttons
            listener.on_done = on_done

            # UNO action listener wrapper
            class _SendAction(unohelper.Base, XActionListener):
                def __init__(self, listener, query_ctrl, ctx, frame):
                    self._listener = listener
                    self._query = query_ctrl
                    self._ctx = ctx
                    self._frame = frame

                def actionPerformed(self, evt):
                    text = ""
                    if self._query and self._query.getModel():
                        text = (self._query.getModel().Text or "").strip()
                    if not text:
                        return
                    self._query.getModel().Text = ""

                    append_response("\nYou: %s\n" % text)
                    set_buttons(False, True)

                    # Get current document
                    d = None
                    if self._frame:
                        try:
                            d = self._frame.getController().getModel()
                        except Exception:
                            pass
                    if d is None:
                        try:
                            smgr = self._ctx.getServiceManager()
                            desktop = smgr.createInstanceWithContext(
                                "com.sun.star.frame.Desktop", self._ctx)
                            d = desktop.getCurrentComponent()
                        except Exception:
                            pass

                    self._listener.send(text, d, self._ctx)

                def disposing(self, evt):
                    pass

            send_btn.addActionListener(
                _SendAction(listener, query_ctrl, self.ctx, self.xFrame))

            # ── Wire stop button ───────────────────────────────────

            if stop_btn:
                class _StopAction(unohelper.Base, XActionListener):
                    def __init__(self, listener):
                        self._listener = listener

                    def actionPerformed(self, evt):
                        self._listener.stop_requested = True
                        set_status("Stopping...")

                    def disposing(self, evt):
                        pass

                stop_btn.addActionListener(_StopAction(listener))

            # ── Wire clear button ──────────────────────────────────

            if clear_btn:
                class _ClearAction(unohelper.Base, XActionListener):
                    def __init__(self, session, response_ctrl, status_ctrl):
                        self._session = session
                        self._response = response_ctrl
                        self._status = status_ctrl

                    def actionPerformed(self, evt):
                        self._session.clear()
                        if self._response and self._response.getModel():
                            self._response.getModel().Text = ""
                        if self._status:
                            self._status.setText("")

                    def disposing(self, evt):
                        pass

                clear_btn.addActionListener(
                    _ClearAction(session, response_ctrl, status_ctrl))

            # ── Initial state ──────────────────────────────────────

            set_buttons(True, False)

            greeting = get_greeting(doc_type)
            if response_ctrl and response_ctrl.getModel():
                response_ctrl.getModel().Text = "%s\n" % greeting

            if status_ctrl:
                status_ctrl.setText("Ready")

    class ChatPanelFactory(unohelper.Base, XUIElementFactory):
        """Factory that creates ChatPanelElement instances for the sidebar."""

        def __init__(self, ctx):
            self.ctx = ctx

        def createUIElement(self, resource_url, args):
            log.info("createUIElement: %s", resource_url)
            if "ChatPanel" not in resource_url:
                from com.sun.star.container import NoSuchElementException
                raise NoSuchElementException(
                    "Unknown resource: " + resource_url)

            frame = _get_arg(args, "Frame")
            parent_window = _get_arg(args, "ParentWindow")
            if not parent_window:
                from com.sun.star.lang import IllegalArgumentException
                raise IllegalArgumentException("ParentWindow is required")

            return ChatPanelElement(
                self.ctx, frame, parent_window, resource_url)

    # Register with LibreOffice
    g_ImplementationHelper = unohelper.ImplementationHelper()
    g_ImplementationHelper.addImplementation(
        ChatPanelFactory,
        "org.extension.localwriter.ChatPanelFactory",
        ("com.sun.star.ui.UIElementFactory",),
    )

except ImportError:
    # Not running inside LibreOffice
    pass

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
    from com.sun.star.awt import (
        XActionListener, XItemListener, XWindowListener, XFocusListener,
        XKeyListener)
    from com.sun.star.awt.Key import UP, DOWN, RETURN

    SETTINGS_XDL_PATH = "LocalWriterDialogs/ChatSettingsDialog.xdl"

    class ChatToolPanel(unohelper.Base, XToolPanel, XSidebarPanel):
        """Holds the panel window; implements XToolPanel + XSidebarPanel."""

        def __init__(self, panel_window, parent_window, ctx,
                     preferred_height=280, fixed_height=False):
            self.ctx = ctx
            self.PanelWindow = panel_window
            self.Window = panel_window
            self.parent_window = parent_window
            self._preferred_height = preferred_height
            self._fixed = fixed_height

        def getWindow(self):
            return self.Window

        def createAccessible(self, parent_accessible):
            return self.PanelWindow

        def getHeightForWidth(self, width):
            h = self._preferred_height
            if self.parent_window and self.PanelWindow and width > 0:
                if not self._fixed:
                    parent_rect = self.parent_window.getPosSize()
                    if parent_rect.Height > 0:
                        h = parent_rect.Height
                self.PanelWindow.setPosSize(0, 0, width, h, 15)
            if self._fixed:
                return uno.createUnoStruct(
                    "com.sun.star.ui.LayoutSize", h, h, h)
            return uno.createUnoStruct(
                "com.sun.star.ui.LayoutSize", h, -1, h)

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
            query_label = _get_optional(root_window, "query_label")

            def set_status(text):
                try:
                    if query_label and query_label.getModel():
                        query_label.getModel().Label = "Ask (%s)" % text
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
                    set_status("...")

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

            send_action = _SendAction(
                listener, query_ctrl, self.ctx, self.xFrame)
            send_btn.addActionListener(send_action)

            # ── Query input history (up/down arrows) ──────────────

            class _QueryHistory:
                """Ring buffer for sent messages, navigable with arrows.

                Persisted to ``chatbot.query_history`` config key (JSON list).
                """

                def __init__(self, config_proxy, max_size=50):
                    self._cfg = config_proxy
                    self._max = max_size
                    self._pos = -1
                    self._draft = ""
                    self._items = self._load()

                def _load(self):
                    try:
                        raw = self._cfg.get("query_history") or "[]"
                        items = json.loads(raw)
                        if isinstance(items, list):
                            return items[-self._max:]
                    except Exception:
                        pass
                    return []

                def _save(self):
                    try:
                        self._cfg.set(
                            "query_history",
                            json.dumps(self._items[-self._max:],
                                       ensure_ascii=False))
                    except Exception:
                        pass

                def push(self, text):
                    if text and (not self._items or self._items[-1] != text):
                        self._items.append(text)
                        if len(self._items) > self._max:
                            self._items.pop(0)
                        self._save()
                    self._pos = -1
                    self._draft = ""

                def up(self, current_text):
                    if not self._items:
                        return None
                    if self._pos == -1:
                        self._draft = current_text
                        self._pos = len(self._items) - 1
                    elif self._pos > 0:
                        self._pos -= 1
                    else:
                        return None
                    return self._items[self._pos]

                def down(self, current_text):
                    if self._pos == -1:
                        return None
                    if self._pos < len(self._items) - 1:
                        self._pos += 1
                        return self._items[self._pos]
                    self._pos = -1
                    return self._draft

            cfg = services.config.proxy_for("chatbot")
            history = _QueryHistory(cfg)

            # Patch send_action to record history
            _orig_action = send_action.actionPerformed

            def _action_with_history(evt):
                text = ""
                if query_ctrl and query_ctrl.getModel():
                    text = (query_ctrl.getModel().Text or "").strip()
                if text:
                    history.push(text)
                _orig_action(evt)

            send_action.actionPerformed = _action_with_history

            enter_sends = cfg.get("enter_sends") if cfg else True
            if enter_sends is None:
                enter_sends = True

            class _QueryKeyListener(unohelper.Base, XKeyListener):
                def __init__(self, query_ctrl, history, send_action):
                    self._query = query_ctrl
                    self._history = history
                    self._send = send_action

                def keyPressed(self, evt):
                    if evt.KeyCode == UP:
                        current = (self._query.getModel().Text or "")
                        prev = self._history.up(current)
                        if prev is not None:
                            self._query.getModel().Text = prev
                    elif evt.KeyCode == DOWN:
                        current = (self._query.getModel().Text or "")
                        nxt = self._history.down(current)
                        if nxt is not None:
                            self._query.getModel().Text = nxt
                    elif (evt.KeyCode == RETURN
                          and enter_sends
                          and not (evt.Modifiers & 1)):
                        # Enter sends, Shift+Enter inserts newline
                        # Modifiers & 1 = SHIFT
                        self._send.actionPerformed(None)

                def keyReleased(self, evt):
                    pass

                def disposing(self, evt):
                    pass

            query_ctrl.addKeyListener(
                _QueryKeyListener(query_ctrl, history, send_action))

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
                    def __init__(self, session, response_ctrl):
                        self._session = session
                        self._response = response_ctrl

                    def actionPerformed(self, evt):
                        self._session.clear()
                        if self._response and self._response.getModel():
                            self._response.getModel().Text = ""

                    def disposing(self, evt):
                        pass

                clear_btn.addActionListener(
                    _ClearAction(session, response_ctrl))

            # ── Initial state ──────────────────────────────────────

            set_buttons(True, False)
            set_status("Ready")

            greeting = get_greeting(doc_type)
            if response_ctrl and response_ctrl.getModel():
                response_ctrl.getModel().Text = "%s\n" % greeting

            # Prevent cursor in response area — redirect focus to query
            class _NoFocus(unohelper.Base, XFocusListener):
                def __init__(self, target):
                    self._target = target

                def focusGained(self, evt):
                    try:
                        self._target.setFocus()
                    except Exception:
                        pass

                def focusLost(self, evt):
                    pass

                def disposing(self, evt):
                    pass

            response_ctrl.addFocusListener(_NoFocus(query_ctrl))

            # ── Dynamic resize ────────────────────────────────────

            ctrls = {
                "response": response_ctrl,
                "query_label": query_label,
                "query": query_ctrl,
                "send": send_btn,
                "stop": stop_btn,
                "clear": clear_btn,
            }

            class _ChatResize(unohelper.Base, XWindowListener):
                def __init__(self, ctrls):
                    self._c = ctrls

                def windowResized(self, evt):
                    try:
                        self._relayout(evt.Source)
                    except Exception:
                        pass

                def windowMoved(self, evt):
                    pass

                def windowShown(self, evt):
                    pass

                def windowHidden(self, evt):
                    pass

                def disposing(self, evt):
                    pass

                def _relayout(self, win):
                    r = win.getPosSize()
                    w, h = r.Width, r.Height
                    if w <= 0 or h <= 0:
                        return
                    m = 6
                    btn_h = 24
                    query_h = 50
                    label_h = 16
                    gap = 4

                    # Bottom-up layout
                    btn_y = h - m - btn_h
                    btn_w = max(50, (w - 2 * m - 2 * gap) // 3)
                    for i, name in enumerate(["send", "stop", "clear"]):
                        c = self._c.get(name)
                        if c:
                            c.setPosSize(
                                m + i * (btn_w + gap), btn_y,
                                btn_w, btn_h, 15)

                    query_y = btn_y - gap - query_h
                    c = self._c.get("query")
                    if c:
                        c.setPosSize(m, query_y, w - 2 * m, query_h, 15)

                    qlabel_y = query_y - label_h
                    c = self._c.get("query_label")
                    if c:
                        c.setPosSize(m, qlabel_y, w - 2 * m, label_h, 15)

                    # Response fills remaining space from top
                    resp_h = max(30, qlabel_y - gap - m)
                    c = self._c.get("response")
                    if c:
                        c.setPosSize(m, m, w - 2 * m, resp_h, 15)

            resize_listener = _ChatResize(ctrls)
            root_window.addWindowListener(resize_listener)
            # Trigger initial layout
            resize_listener._relayout(root_window)

    class ChatSettingsElement(unohelper.Base, XUIElement):
        """XUIElement for the AI Settings panel."""

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
                        root_window, self.xParentWindow, self.ctx,
                        preferred_height=80, fixed_height=True)
                    self._wire_controls(root_window)
                except Exception:
                    log.exception("ChatSettingsElement.getRealInterface failed")
                    raise
            return self.toolpanel

        def _create_panel_window(self):
            """Load XDL container, then add ListBox controls in code."""
            pip = self.ctx.getValueByName(
                "/singletons/com.sun.star.deployment"
                ".PackageInformationProvider")
            base_url = pip.getPackageLocation(EXTENSION_ID)
            dialog_url = base_url + "/" + SETTINGS_XDL_PATH

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
            if not hasattr(root_window, "getControl"):
                return

            from plugin.main import bootstrap, get_services
            bootstrap(self.ctx)
            services = get_services()

            from plugin.modules.ai.service import (
                get_text_instance_options, get_image_instance_options)

            smgr = self.ctx.getServiceManager()

            _M = 6
            _LABEL_W = 66
            _DD_W = 320

            def _add_label(name, y, text):
                fm = smgr.createInstanceWithContext(
                    "com.sun.star.awt.UnoControlFixedTextModel", self.ctx)
                fm.Label = text
                fc = smgr.createInstanceWithContext(
                    "com.sun.star.awt.UnoControlFixedText", self.ctx)
                fc.setModel(fm)
                fc.setPosSize(_M, y + 3, _LABEL_W, 16, 15)
                root_window.addControl(name, fc)
                return fc

            ai = services.get("ai")

            def _add_dropdown(name, y, options, capability):
                lm = smgr.createInstanceWithContext(
                    "com.sun.star.awt.UnoControlListBoxModel", self.ctx)
                lm.Dropdown = True
                lm.LineCount = 8
                lc = smgr.createInstanceWithContext(
                    "com.sun.star.awt.UnoControlListBox", self.ctx)
                lc.setModel(lm)
                dd_x = _M + _LABEL_W + 4
                lc.setPosSize(dd_x, y, _DD_W, 22, 15)
                root_window.addControl(name, lc)

                ids = []
                for opt in options:
                    lc.addItem(opt["label"], len(ids))
                    ids.append(opt["value"])

                # Init from volatile, fall back to config default
                current = ""
                if ai:
                    current = ai._get_active_instance_id(capability)
                sel = 0
                for i, v in enumerate(ids):
                    if v == current:
                        sel = i
                        break
                if ids:
                    lc.selectItemPos(sel, True)

                class _Listener(unohelper.Base, XItemListener):
                    def __init__(self, ai_svc, cap, ids):
                        self._ai = ai_svc
                        self._cap = cap
                        self._ids = ids

                    def itemStateChanged(self, evt):
                        pos = evt.Selected
                        if self._ai and 0 <= pos < len(self._ids):
                            self._ai.set_active_instance(
                                self._cap, self._ids[pos])

                    def disposing(self, evt):
                        pass

                lc.addItemListener(
                    _Listener(ai, capability, ids))
                return lc

            # Label + dropdown on same row, 22px row height, 12px gap
            _add_label("text_label", 10, "Text AI")
            _add_dropdown(
                "text_instance", 10,
                get_text_instance_options(services),
                "text")

            _add_label("image_label", 46, "Image AI")
            _add_dropdown(
                "image_instance", 46,
                get_image_instance_options(services),
                "image")

    class ChatPanelFactory(unohelper.Base, XUIElementFactory):
        """Factory that creates chat and settings panel elements."""

        def __init__(self, ctx):
            self.ctx = ctx

        def createUIElement(self, resource_url, args):
            log.info("createUIElement: %s", resource_url)

            frame = _get_arg(args, "Frame")
            parent_window = _get_arg(args, "ParentWindow")
            if not parent_window:
                from com.sun.star.lang import IllegalArgumentException
                raise IllegalArgumentException("ParentWindow is required")

            if "ChatSettingsPanel" in resource_url:
                return ChatSettingsElement(
                    self.ctx, frame, parent_window, resource_url)
            if "ChatPanel" in resource_url:
                return ChatPanelElement(
                    self.ctx, frame, parent_window, resource_url)

            from com.sun.star.container import NoSuchElementException
            raise NoSuchElementException(
                "Unknown resource: " + resource_url)

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

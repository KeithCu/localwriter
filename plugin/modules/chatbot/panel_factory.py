"""Sidebar panel factory — UNO wiring for the chat panel.

Creates the XUIElement and XToolPanel that LibreOffice needs for
the sidebar. Builds controls programmatically (no XDL), wires them
to the framework's ChatSession and ChatToolAdapter, and handles
streaming responses.

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
                "com.sun.star.ui.LayoutSize", 100, -1, h)

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
            """Build panel container and controls programmatically."""
            from plugin.framework.panel_layout import (
                create_panel_window, add_control)

            self.m_panelRootWindow = create_panel_window(
                self.ctx, self.xParentWindow)

            add_control(self.ctx, self.m_panelRootWindow,
                        "response", "Edit",
                        {"ReadOnly": True, "MultiLine": True,
                         "VScroll": True})
            add_control(self.ctx, self.m_panelRootWindow,
                        "query_label", "FixedText",
                        {"Label": "Chat (Ready)"})
            add_control(self.ctx, self.m_panelRootWindow,
                        "query", "Edit",
                        {"MultiLine": True, "VScroll": True})
            add_control(self.ctx, self.m_panelRootWindow,
                        "send", "Button", {"Label": "Send"})
            add_control(self.ctx, self.m_panelRootWindow,
                        "stop", "Button", {"Label": "Stop"})
            add_control(self.ctx, self.m_panelRootWindow,
                        "clear", "Button", {"Label": "Clear"})

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
            use_broker = False
            try:
                cfg = services.config.proxy_for("chatbot")
                extra = cfg.get("system_prompt") or ""
                use_broker = cfg.get("tool_broker") or False
            except Exception:
                pass

            system_prompt = get_system_prompt(doc_type, extra,
                                              broker=use_broker)

            # ── Create session and adapter ─────────────────────────

            from plugin.modules.chatbot.panel import (
                ChatSession, ChatToolAdapter, SendButtonListener)

            session = ChatSession(system_prompt)
            adapter = ChatToolAdapter(tools, services)

            # ── Wire send button ───────────────────────────────────

            listener = SendButtonListener(services, session, adapter)

            # Connect UI callbacks
            query_label = _get_optional(root_window, "query_label")

            _spinner_active = [False]
            _spinner_text = [""]

            def _start_spinner(text=""):
                """Start or update spinner. No restart if already running."""
                _spinner_text[0] = text
                if _spinner_active[0]:
                    return  # thread running, just updated text
                _spinner_active[0] = True
                def _spin():
                    # Braille circling dot
                    frames = ["\u280B", "\u2819", "\u2839", "\u2838",
                              "\u283C", "\u2834", "\u2826", "\u2827",
                              "\u2807", "\u280F"]
                    i = 0
                    while _spinner_active[0]:
                        try:
                            if query_label and query_label.getModel():
                                t = _spinner_text[0]
                                label = frames[i % len(frames)]
                                if t:
                                    label = "%s  %s" % (label, t)
                                query_label.getModel().Label = label
                        except Exception:
                            break
                        i += 1
                        threading.Event().wait(0.1)
                threading.Thread(
                    target=_spin, daemon=True).start()

            def set_status(text):
                if text == "Ready":
                    _spinner_active[0] = False
                    try:
                        if query_label and query_label.getModel():
                            query_label.getModel().Label = (
                                "Chat (%s)" % text)
                    except Exception:
                        pass
                elif text.startswith(("Error", "Provider ", "Model ",
                                     "No LLM", "Not ready")):
                    # Static error — no spinner
                    _spinner_active[0] = False
                    try:
                        if query_label and query_label.getModel():
                            query_label.getModel().Label = text
                    except Exception:
                        pass
                else:
                    _start_spinner(text)

            def append_response(text, is_thinking=False):
                _start_spinner()
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
                                      (stop_btn, stop_enabled),
                                      (query_ctrl, send_enabled)]:
                    if ctrl and ctrl.getModel():
                        ctrl.getModel().Enabled = bool(enabled)

            def on_done():
                _spinner_active[0] = False
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
                    self._use_tools = "lazy"  # default: auto-detect

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

                    use_tools = self._use_tools
                    self._use_tools = "lazy"  # reset for next call

                    # Run in background thread to avoid UI freeze
                    def _worker():
                        self._listener.send(text, d, self._ctx,
                                            use_tools=use_tools)
                    threading.Thread(
                        target=_worker, daemon=True).start()

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
                          and not (evt.Modifiers & 1)):
                        # Shift+Enter (bit 1) → newline, handled by default
                        # Guard: only send if the send button is enabled
                        if not (send_btn and send_btn.getModel()
                                and send_btn.getModel().Enabled):
                            return
                        if evt.Modifiers & 2:
                            # Ctrl+Enter → Do mode (force tools)
                            self._send._use_tools = True
                            self._send.actionPerformed(None)
                        elif enter_sends:
                            # Enter → Lazy mode (auto-detect tools)
                            self._send._use_tools = "lazy"
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

            # ── Initial state + warmup check ──────────────────────

            ai = services.get("ai")
            events = services.get("events")

            # Check if provider is ready; grey out if not
            _provider_ready = [True]
            try:
                if ai:
                    st = ai.get_active_status("text")
                    if not st.get("ready", True):
                        _provider_ready[0] = False
                        set_buttons(False, False)
                        msg = st.get("message", "Loading...")
                        if not msg.startswith(("Error", "Provider ",
                                               "Model ", "Loading")):
                            msg = "Error: %s" % msg
                        set_status(msg)
            except Exception:
                pass

            if _provider_ready[0]:
                set_buttons(True, False)
                set_status("Ready")

            # Subscribe to warmup status events
            if events and ai:
                def _on_instance_status(instance_id="", status="",
                                        message="", **kw):
                    try:
                        active_id = ai._get_active_instance_id("text")
                        if instance_id != active_id and active_id:
                            return
                        if status == "ready":
                            _provider_ready[0] = True
                            set_buttons(True, False)
                            set_status("Ready")
                        else:
                            _provider_ready[0] = False
                            set_buttons(False, False)
                            msg = message or status
                            if not msg.startswith(("Error", "Provider ",
                                                   "Model ", "Loading")):
                                msg = "Error: %s" % msg
                            set_status(msg)
                    except Exception:
                        pass

                events.subscribe("ai:instance_status",
                                 _on_instance_status)

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

            input_position = cfg.get("input_position") if cfg else "bottom"
            if input_position not in ("top", "bottom"):
                input_position = "bottom"

            class _ChatResize(unohelper.Base, XWindowListener):
                def __init__(self, ctrls, position):
                    self._c = ctrls
                    self._pos = position

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
                    # Determine a rough scaling factor for High DPI based on the vertical height
                    # of the LibreOffice window. A typical 1080p window is ~1000px high.
                    # A 4K window is comfortably >2000px high.
                    scale_factor = max(1.0, h / 1000.0)
                        
                    m = int(8 * scale_factor)
                    btn_h = int(28 * scale_factor)
                    query_h = int(70 * scale_factor)
                    label_h = int(22 * scale_factor)
                    gap = int(10 * scale_factor)
                    
                    cw = w - 2 * m
                    btn_w = max(int(50 * scale_factor), (cw - 2 * gap) // 3)

                    if self._pos == "top":
                        # Top-down: label, query, buttons, then response
                        y = m
                        c = self._c.get("query_label")
                        if c:
                            c.setPosSize(m, y, cw, label_h, 15)
                        y += label_h

                        c = self._c.get("query")
                        if c:
                            c.setPosSize(m, y, cw, query_h, 15)
                        y += query_h + gap

                        for i, name in enumerate(
                                ["send", "stop", "clear"]):
                            c = self._c.get(name)
                            if c:
                                c.setPosSize(
                                    m + i * (btn_w + gap), y,
                                    btn_w, btn_h, 15)
                        y += btn_h + gap

                        resp_h = max(30, h - y - m - 200)
                        c = self._c.get("response")
                        if c:
                            c.setPosSize(m, y, cw, resp_h, 15)
                    else:
                        # Bottom-up: response at top, input at bottom
                        # The layout needs to be:
                        # [response box]
                        # [query label]
                        # [query box]
                        # [buttons]
                        # [200px spacer]
                        
                        # To guarantee no overlap, we pack top-to-bottom.
                        # Total height required by controls at the bottom:
                        bottom_ctrls_h = label_h + gap + query_h + gap + btn_h
                        resp_h = h - m - bottom_ctrls_h - m
                        resp_h = max(30, resp_h)
                        
                        log.info(f"_relayout bottom-up: w={w}, h={h}, bottom_ctrls_h={bottom_ctrls_h}, resp_h={resp_h}")
                        
                        y = m
                        c = self._c.get("response")
                        if c:
                            c.setPosSize(m, y, cw, resp_h, 15)
                            log.info(f"  response: y={y}, h={resp_h}")
                        y += resp_h + gap
                        
                        c = self._c.get("query_label")
                        if c:
                            c.setPosSize(m, y, cw, label_h, 15)
                            log.info(f"  query_label: y={y}, h={label_h}")
                        y += label_h + gap
                        
                        c = self._c.get("query")
                        if c:
                            c.setPosSize(m, y, cw, query_h, 15)
                            log.info(f"  query: y={y}, h={query_h}")
                        y += query_h + gap
                        
                        for i, name in enumerate(["send", "stop", "clear"]):
                            c = self._c.get(name)
                            if c:
                                btn_x = m + i * (btn_w + gap)
                                c.setPosSize(btn_x, y, btn_w, btn_h, 15)
                                log.info(f"  button {name}: y={y}, h={btn_h}")

            resize_listener = _ChatResize(ctrls, input_position)
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
            """Build settings container programmatically."""
            from plugin.framework.panel_layout import create_panel_window

            self.m_panelRootWindow = create_panel_window(
                self.ctx, self.xParentWindow)
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

            events_bus = services.get("events")

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
                    def __init__(self, ai_svc, cap, ids, events_bus=None):
                        self._ai = ai_svc
                        self._cap = cap
                        self._ids = ids
                        self._events = events_bus

                    def itemStateChanged(self, evt):
                        pos = evt.Selected
                        if self._ai and 0 <= pos < len(self._ids):
                            instance_id = self._ids[pos]
                            self._ai.set_active_instance(
                                self._cap, instance_id)
                            # Emit status so the chat panel updates
                            if self._events and self._cap == "text":
                                try:
                                    st = self._ai.get_active_status(
                                        self._cap)
                                    self._events.emit(
                                        "ai:instance_status",
                                        instance_id=instance_id,
                                        status="ready" if st.get(
                                            "ready", True) else "error",
                                        message=st.get(
                                            "message", ""))
                                except Exception:
                                    pass

                    def disposing(self, evt):
                        pass

                lc.addItemListener(
                    _Listener(ai, capability, ids,
                              events_bus=events_bus))
                return lc, ids

            # Label + dropdown on same row, 22px row height, 12px gap
            _add_label("text_label", 10, "Text AI")
            text_dd, text_ids = _add_dropdown(
                "text_instance", 10,
                get_text_instance_options(services),
                "text")

            _add_label("image_label", 46, "Image AI")
            image_dd, image_ids = _add_dropdown(
                "image_instance", 46,
                get_image_instance_options(services),
                "image")

            # Refresh dropdowns when config changes (e.g. new AI instances)
            events = services.get("events")
            if events:
                def _refresh_dropdown(lc, options_fn, capability, ids_ref):
                    """Repopulate a ListBox from fresh options."""
                    lc.removeItems(0, lc.getItemCount())
                    ids_ref.clear()
                    for opt in options_fn(services):
                        lc.addItem(opt["label"], len(ids_ref))
                        ids_ref.append(opt["value"])
                    current = ""
                    if ai:
                        current = ai._get_active_instance_id(capability)
                    sel = 0
                    for i, v in enumerate(ids_ref):
                        if v == current:
                            sel = i
                            break
                    if ids_ref:
                        lc.selectItemPos(sel, True)

                def _on_config_changed(**data):
                    try:
                        _refresh_dropdown(
                            text_dd, get_text_instance_options,
                            "text", text_ids)
                        _refresh_dropdown(
                            image_dd, get_image_instance_options,
                            "image", image_ids)
                    except Exception:
                        pass

                events.subscribe("config:changed", _on_config_changed)

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

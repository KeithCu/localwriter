import sys
import os

# Ensure extension directory is on path so core.streaming_deltas can be imported
_ext_dir = os.path.dirname(os.path.abspath(__file__))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)

import unohelper
import officehelper

from core.config import get_config, set_config, as_bool, get_api_config, get_current_endpoint, validate_api_config, populate_combobox_with_lru, update_lru_history, notify_config_changed, populate_image_model_selector, populate_endpoint_selector, endpoint_from_selector_text, get_image_model, set_image_model, get_api_key_for_endpoint, set_api_key_for_endpoint
from core.api import LlmClient, format_error_message
from core.uno_ui_helpers import is_checkbox_control, get_checkbox_state, set_checkbox_state
from core.document import get_full_document_text, get_document_context_for_chat
from core.async_stream import run_stream_completion_async
from core.logging import agent_log, init_logging
from core.constants import get_chat_system_prompt_for_document
from com.sun.star.task import XJobExecutor
from com.sun.star.awt import MessageBoxButtons as MSG_BUTTONS, XItemListener
from com.sun.star.awt.MessageBoxType import ERRORBOX
from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK
import uno
import logging
import re

from com.sun.star.beans import PropertyValue
from com.sun.star.container import XNamed

# ---------------------------------------------------------------------------
# MCP Server (module-level state; UNO Timer for main-thread drain)
# ---------------------------------------------------------------------------
# The timer is needed because MCP request work is queued and must be drained on
# LibreOffice's main thread. We use a UNO Timer (not the sidebar's processEventsToIdle
# pattern) because we need periodic ticks even when no user action is active.

_mcp_server = None
_mcp_timer_thread = None
_mcp_timer_stop_event = None


def _start_mcp_timer(ctx):
    """Start Python background thread that periodically dispatches a drain command
    to the main thread. We use dispatch instead of a UNO Timer because UNO Timers
    fail to instantiate in the system Python environment (missing 'com' package).
    """
    global _mcp_timer_thread, _mcp_timer_stop_event
    from core.logging import debug_log
    import threading
    import time

    if _mcp_timer_thread and _mcp_timer_thread.is_alive():
        return

    _mcp_timer_stop_event = threading.Event()

    def timer_loop():
        try:
            smgr = ctx.getServiceManager()
            async_cb = smgr.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx)
            
            from com.sun.star.awt import XCallback
            import unohelper
            
            class _MCPDrainCallback(unohelper.Base, XCallback):
                def notify(self, data):
                    try:
                        from core.mcp_thread import drain_mcp_queue
                        drain_mcp_queue()
                    except Exception as e:
                        debug_log("MCP drain failed: %s" % e, context="MCP")
            
            callback = _MCPDrainCallback()
            
        except Exception as e:
            debug_log("MCP Timer thread failed to initialize AsyncCallback or XCallback: %s" % e, context="MCP")
            return

        while not _mcp_timer_stop_event.is_set():
            time.sleep(0.1) # 100ms
            if _mcp_timer_stop_event.is_set():
                break
            try:
                async_cb.addCallback(callback, None)
            except Exception as e:
                debug_log("MCP async_cb error: %s" % str(e), context="MCP")

    _mcp_timer_thread = threading.Thread(target=timer_loop, daemon=True)
    _mcp_timer_thread.start()
    debug_log("MCP Timer thread started (drain every 100ms via Dispatch)", context="MCP")


def try_ensure_mcp_timer(ctx):
    """Start the MCP drain timer if the server is running but the timer is not.
    Called from the sidebar when the panel is created.
    If config has mcp_enabled but the server was not started this session (e.g. after
    restart), start the server first so the timer can run."""
    global _mcp_server, _mcp_timer_thread
    from core.logging import debug_log
    if _mcp_server is None:
        if as_bool(get_config(ctx, "mcp_enabled", False)):
            debug_log("MCP: config enabled but server not running, starting server from sidebar", context="MCP")
            _start_mcp_server(ctx)
        if _mcp_server is None:
            debug_log("MCP: server not running, skipping timer start", context="MCP")
            return
    if _mcp_timer_thread is not None and _mcp_timer_thread.is_alive():
        debug_log("MCP: timer already running", context="MCP")
        return
    debug_log("MCP: starting drain timer from sidebar", context="MCP")
    _start_mcp_timer(ctx)


def _stop_mcp_timer():
    global _mcp_timer_stop_event
    try:
        if _mcp_timer_stop_event:
            _mcp_timer_stop_event.set()
    except Exception:
        pass


def _start_mcp_server(ctx):
    """Start MCP HTTP server and drain timer if enabled in config."""
    global _mcp_server
    from core.config import get_config
    from core.mcp_server import MCPHttpServer, _kill_zombies_on_port, _probe_health
    from core.logging import debug_log
    if not as_bool(get_config(ctx, "mcp_enabled", False)):
        return
    if _mcp_server is not None:
        return
    port = int(get_config(ctx, "mcp_port", 8765))
    if port <= 0 or port > 65535:
        port = 8765
    _kill_zombies_on_port("127.0.0.1", port)
    try:
        _mcp_server = MCPHttpServer(ctx, port=port)
        _mcp_server.start()
        # Timer is started from the sidebar (try_ensure_mcp_timer) where 'com' is available
    except OSError as e:
        if getattr(e, "errno", None) == 98 or "Address already in use" in str(e):
            if _probe_health("127.0.0.1", port):
                debug_log("MCP server already running on port %s (e.g. from sidebar), not starting again" % port, context="MCP")
                _show_mcp_already_running(ctx, port)
                return
        _mcp_server = None
        debug_log("MCP server start failed: %s" % e, context="MCP")
    except Exception as e:
        _mcp_server = None
        debug_log("MCP server start failed: %s" % e, context="MCP")


def _stop_mcp_server():
    global _mcp_server
    _stop_mcp_timer()
    try:
        if _mcp_server is not None:
            _mcp_server.stop()
            _mcp_server = None
    except Exception:
        _mcp_server = None


def _toggle_mcp_server(ctx):
    """Start server if stopped, stop if running."""
    global _mcp_server
    if _mcp_server is not None:
        _stop_mcp_server()
    else:
        _start_mcp_server(ctx)


def _show_mcp_already_running(ctx, port):
    """Tell user the server is already running (e.g. started by the sidebar)."""
    try:
        smgr = ctx.getServiceManager()
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        frame = desktop.getCurrentFrame()
        if frame and frame.ActiveFrame:
            frame = frame.ActiveFrame
        window_peer = frame.getContainerWindow() if frame else None
        if not window_peer:
            return
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        msg = "MCP server is already running on port %s (e.g. started by the sidebar).\n\nUse 'MCP Server Status' to confirm." % port
        box = toolkit.createMessageBox(window_peer, 0, BUTTONS_OK, "MCP Server", msg)
        box.execute()
    except Exception:
        pass


def _do_mcp_status(ctx):
    """Show a small status dialog: running/stopped, port, health check."""
    global _mcp_server
    from core.config import get_config
    from core.mcp_server import _probe_health
    smgr = ctx.getServiceManager()
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    frame = desktop.getCurrentFrame()
    if frame and frame.ActiveFrame:
        frame = frame.ActiveFrame
    window_peer = frame.getContainerWindow() if frame else None
    if not window_peer:
        return
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    port = int(get_config(ctx, "mcp_port", 8765))
    ok = _probe_health("127.0.0.1", port)
    # Show RUNNING if we have a handle or if the port responds (e.g. server started by sidebar)
    status = "RUNNING" if (_mcp_server is not None or ok) else "STOPPED"
    url = "http://localhost:%s" % port
    health = "OK" if ok else ("FAIL" if _mcp_server else "N/A")
    msg = "MCP Server: %s\nPort: %s\nURL: %s\nHealth: %s" % (status, port, url, health)
    box = toolkit.createMessageBox(window_peer, 0, BUTTONS_OK, "MCP Server Status", msg)
    box.execute()


# The MainJob is a UNO component derived from unohelper.Base class
# and also the XJobExecutor, the implemented interface
class MainJob(unohelper.Base, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx
        # handling different situations (inside LibreOffice or other process)
        try:
            self.sm = ctx.getServiceManager()
            self.desktop = XSCRIPTCONTEXT.getDesktop()
            self.document = XSCRIPTCONTEXT.getDocument()
        except NameError:
            self.sm = ctx.ServiceManager
            self.desktop = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx)
        self.client = None
    

    def get_config(self, key, default):
        """Delegate to core.config. Kept for API compatibility (chat_panel, etc.)."""
        return get_config(self.ctx, key, default)

    def set_config(self, key, value):
        """Delegate to core.config."""
        set_config(self.ctx, key, value)

    def _populate_combobox_with_lru(self, ctrl, current_val, lru_key, endpoint, strict=False):
        """Delegate to core.config. When strict=True, only show models for this endpoint."""
        return populate_combobox_with_lru(self.ctx, ctrl, current_val, lru_key, endpoint, strict)

    def _update_lru_history(self, val, lru_key, endpoint, max_items=None):
        """Delegate to core.config. Uses LRU_MAX_ITEMS (6) when max_items not given."""
        update_lru_history(self.ctx, val, lru_key, endpoint, max_items)

    def _get_settings_field_specs(self):
        """Return field specs for Settings dialog (single source for dialog and apply keys)."""
        openai_compatibility_value = "true" if as_bool(self.get_config("openai_compatibility", False)) else "false"
        is_openwebui_value = "true" if as_bool(self.get_config("is_openwebui", False)) else "false"
        current_endpoint_for_specs = get_current_endpoint(self.ctx)
        return [
            {"name": "endpoint", "value": str(self.get_config("endpoint", "http://127.0.0.1:5000"))},
            {"name": "text_model", "value": str(self.get_config("text_model", "") or self.get_config("model", ""))},
            {"name": "image_model", "value": str(get_image_model(self.ctx))},
            {"name": "api_key", "value": str(get_api_key_for_endpoint(self.ctx, current_endpoint_for_specs))},
            {"name": "api_type", "value": str(self.get_config("api_type", "completions"))},
            {"name": "is_openwebui", "value": is_openwebui_value, "type": "bool"},
            {"name": "openai_compatibility", "value": openai_compatibility_value, "type": "bool"},
            {"name": "temperature", "value": str(self.get_config("temperature", "0.5")), "type": "float"},
            {"name": "seed", "value": str(self.get_config("seed", ""))},
            {"name": "extend_selection_max_tokens", "value": str(self.get_config("extend_selection_max_tokens", "70")), "type": "int"},
            {"name": "edit_selection_max_new_tokens", "value": str(self.get_config("edit_selection_max_new_tokens", "0")), "type": "int"},
            {"name": "chat_max_tokens", "value": str(self.get_config("chat_max_tokens", "16384")), "type": "int"},
            {"name": "chat_context_length", "value": str(self.get_config("chat_context_length", "8000")), "type": "int"},
            {"name": "additional_instructions", "value": str(self.get_config("additional_instructions", ""))},
            {"name": "request_timeout", "value": str(self.get_config("request_timeout", "120")), "type": "int"},
            {"name": "chat_max_tool_rounds", "value": str(self.get_config("chat_max_tool_rounds", "5")), "type": "int"},
            {"name": "use_aihorde", "value": "true" if self.get_config("image_provider", "aihorde") == "aihorde" else "false", "type": "bool"},
            {"name": "aihorde_api_key", "value": str(self.get_config("aihorde_api_key", ""))},
            {"name": "image_base_size", "value": str(self.get_config("image_base_size", "512")), "type": "int"},
            {"name": "image_default_aspect", "value": str(self.get_config("image_default_aspect", "Square"))},
            {"name": "image_cfg_scale", "value": str(self.get_config("image_cfg_scale", "7.5")), "type": "float"},
            {"name": "image_steps", "value": str(self.get_config("image_steps", "30")), "type": "int"},
            {"name": "image_nsfw", "value": "true" if as_bool(self.get_config("image_nsfw", False)) else "false", "type": "bool"},
            {"name": "image_censor_nsfw", "value": "true" if as_bool(self.get_config("image_censor_nsfw", True)) else "false", "type": "bool"},
            {"name": "image_max_wait", "value": str(self.get_config("image_max_wait", "5")), "type": "int"},
            {"name": "image_auto_gallery", "value": "true" if as_bool(self.get_config("image_auto_gallery", True)) else "false", "type": "bool"},
            {"name": "image_insert_frame", "value": "true" if as_bool(self.get_config("image_insert_frame", False)) else "false", "type": "bool"},
            {"name": "image_translate_prompt", "value": "true" if as_bool(self.get_config("image_translate_prompt", True)) else "false", "type": "bool"},
            {"name": "image_translate_from", "value": str(self.get_config("image_translate_from", ""))},
            {"name": "mcp_enabled", "value": "true" if as_bool(self.get_config("mcp_enabled", False)) else "false", "type": "bool"},
            {"name": "mcp_port", "value": str(self.get_config("mcp_port", 8765)), "type": "int"},
        ]

    def _apply_settings_result(self, result):
        """Apply settings dialog result to config. Shared by Writer and Calc."""
        # Keys to set directly from result; derived from dialog field specs (exclude specially handled ones)
        _apply_skip = ("endpoint", "api_key", "use_aihorde", "api_type", "mcp_port")
        apply_keys = [f["name"] for f in self._get_settings_field_specs() if f["name"] not in _apply_skip]

        # Resolve endpoint first so LRU updates use the endpoint being saved
        effective_endpoint = endpoint_from_selector_text(result.get("endpoint", "")) if "endpoint" in result else get_current_endpoint(self.ctx)
        if "endpoint" in result and effective_endpoint:
            self.set_config("endpoint", effective_endpoint)
        current_endpoint = effective_endpoint or get_current_endpoint(self.ctx)

        # Set keys from result (endpoint, api_key, use_aihorde, api_type, mcp_port handled below)
        for key in apply_keys:
            if key in result:
                val = result[key]
                self.set_config(key, val)
                
                # Update LRU history
                if key == "text_model" and val:
                    self._update_lru_history(val, "model_lru", current_endpoint)
                elif key == "image_model" and val:
                    set_image_model(self.ctx, val)
                elif key == "additional_instructions" and val:
                    self._update_lru_history(val, "prompt_lru", "")
                elif key == "image_base_size" and val:
                    self._update_lru_history(str(val), "image_base_size_lru", "")

        # Handle provider toggle from checkbox
        if "use_aihorde" in result:
            provider = "aihorde" if result["use_aihorde"] else "endpoint"
            self.set_config("image_provider", provider)

        
        # Update endpoint_lru when user changed endpoint (endpoint already set above)
        if "endpoint" in result and effective_endpoint:
            self._update_lru_history(effective_endpoint, "endpoint_lru", "")
        
        if "api_type" in result:
            api_type_value = str(result["api_type"]).strip().lower()
            if api_type_value not in ("chat", "completions"):
                api_type_value = "completions"
            self.set_config("api_type", api_type_value)

        if "mcp_port" in result:
            try:
                port = int(result["mcp_port"])
                if 1 <= port <= 65535:
                    self.set_config("mcp_port", port)
            except (TypeError, ValueError):
                pass

        if "api_key" in result:
            set_api_key_for_endpoint(self.ctx, current_endpoint, result["api_key"])

        notify_config_changed(self.ctx)

    def _get_client(self):
        """Get or create LlmClient with current config."""
        config = get_api_config(self.ctx)
        if not self.client:
            self.client = LlmClient(config, self.ctx)
        else:
            self.client.config = config
        return self.client

    def show_error(self, message, title="LocalWriter Error"):
        """Show an error message in a dialog instead of writing to the document."""
        desktop = self.sm.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        frame = desktop.getCurrentFrame()
        if frame and frame.ActiveFrame:
            frame = frame.ActiveFrame
        window_peer = frame.getContainerWindow() if frame else None
        if window_peer:
            toolkit = self.sm.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
            box = toolkit.createMessageBox(window_peer, ERRORBOX, BUTTONS_OK, title, str(message))
            box.execute()

    def stream_completion(
        self,
        prompt,
        system_prompt,
        max_tokens,
        api_type,
        append_callback,
        append_thinking_callback=None,
        stop_checker=None,
    ):
        """Single entry point for streaming completions. Raises on error."""
        self._get_client().stream_completion(
            prompt,
            system_prompt,
            max_tokens,
            api_type,
            append_callback,
            append_thinking_callback=append_thinking_callback,
            stop_checker=stop_checker,
        )

    def make_chat_request(self, messages, max_tokens=512, tools=None, stream=False):
        """Delegate to LlmClient."""
        return self._get_client().make_chat_request(
            messages, max_tokens, tools=tools, stream=stream
        )

    def request_with_tools(self, messages, max_tokens=512, tools=None):
        """Delegate to LlmClient."""
        return self._get_client().request_with_tools(
            messages, max_tokens, tools=tools
        )

    def stream_request_with_tools(
        self,
        messages,
        max_tokens=512,
        tools=None,
        append_callback=None,
        append_thinking_callback=None,
        stop_checker=None,
    ):
        """Delegate to LlmClient."""
        return self._get_client().stream_request_with_tools(
            messages,
            max_tokens,
            tools=tools,
            append_callback=append_callback,
            append_thinking_callback=append_thinking_callback,
            stop_checker=stop_checker,
        )

    def stream_chat_response(
        self,
        messages,
        max_tokens,
        append_callback,
        append_thinking_callback=None,
        stop_checker=None,
    ):
        """Delegate to LlmClient."""
        self._get_client().stream_chat_response(
            messages,
            max_tokens,
            append_callback,
            append_thinking_callback=append_thinking_callback,
            stop_checker=stop_checker,
        )

    def get_full_document_text(self, model, max_chars=8000):
        """Delegate to core.document."""
        return get_full_document_text(model, max_chars)

    def input_box(self, message, title="", default="", x=None, y=None):
        """ Shows input dialog (EditInputDialog.xdl). Returns (result_text, extra_prompt) if OK, else ("", ""). """
        import uno
        ctx = self.ctx
        smgr = ctx.getServiceManager()
        pip = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation("org.extension.localwriter")
        dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
        dlg = dp.createDialog(base_url + "/LocalWriterDialogs/EditInputDialog.xdl")
        try:
            dlg.getControl("label").getModel().Label = str(message)
            dlg.getControl("edit").getModel().Text = str(default)
            if title:
                dlg.getModel().Title = title
            
            # Populate prompt selector history
            prompt_ctrl = dlg.getControl("prompt_selector")
            current_prompt = self.get_config("additional_instructions", "")
            self._populate_combobox_with_lru(prompt_ctrl, current_prompt, "prompt_lru", "")

            dlg.getControl("edit").setFocus()
            dlg.getControl("edit").setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 0, len(str(default))))
            
            if dlg.execute():
                ret_text = dlg.getControl("edit").getModel().Text
                ret_prompt = prompt_ctrl.getText()
                return ret_text, ret_prompt
            return "", ""
        finally:
            dlg.dispose()

    def settings_box(self, title="", x=None, y=None):
        """ Settings dialog loaded from XDL (LocalWriterDialogs/SettingsDialog.xdl).
        Uses DialogProvider for proper Map AppFont sizing. """
        import uno

        ctx = self.ctx
        smgr = ctx.getServiceManager()

        field_specs = self._get_settings_field_specs()

        pip = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation("org.extension.localwriter")
        dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
        dialog_url = base_url + "/LocalWriterDialogs/SettingsDialog.xdl"
        try:
            dlg = dp.createDialog(dialog_url)
        except Exception as e:
            error_msg = getattr(e, "Message", str(e))
            from core.logging import debug_log
            debug_log(f"createDialog failed for {dialog_url}: {error_msg}", context="Settings")
            agent_log("main.py:settings_box", "createDialog failed", data={"url": dialog_url, "error": error_msg}, hypothesis_id="H5")
            raise Exception(f"Could not create dialog from {dialog_url}: {error_msg}")


        # Wire tab-switching buttons
        from com.sun.star.awt import XActionListener

        class TabListener(unohelper.Base, XActionListener):
            def __init__(self, dialog, page):
                self._dlg = dialog
                self._page = page
            def actionPerformed(self, ev):
                self._dlg.getModel().Step = self._page
            def disposing(self, ev):
                pass

        dlg.getControl("btn_tab_chat").addActionListener(TabListener(dlg, 1))
        dlg.getControl("btn_tab_image").addActionListener(TabListener(dlg, 2))

        # Get current endpoint for LRU scoping
        current_endpoint = get_current_endpoint(self.ctx)

        try:
            for field in field_specs:
                ctrl = dlg.getControl(field["name"])
                if ctrl:
                    if field["name"] == "text_model":
                        self._populate_combobox_with_lru(ctrl, field["value"], "model_lru", current_endpoint, strict=True)
                    elif field["name"] == "image_model":
                        populate_image_model_selector(self.ctx, ctrl)
                    elif field["name"] == "additional_instructions":
                        self._populate_combobox_with_lru(ctrl, field["value"], "prompt_lru", "")
                    elif field["name"] == "endpoint":
                        populate_endpoint_selector(self.ctx, ctrl, field["value"])
                        # When user selects an item from dropdown, set combobox text to URL and refresh model combos
                        if hasattr(ctrl, "addItemListener"):
                            class EndpointItemListener(unohelper.Base, XItemListener):
                                def __init__(self, dialog, main_job, combo_ctrl):
                                    self._dlg = dialog
                                    self._main = main_job
                                    self._ctrl = combo_ctrl
                                def itemStateChanged(self, ev):
                                    try:
                                        idx = getattr(ev, "Selected", -1)
                                        if idx < 0:
                                            return
                                        item_text = self._ctrl.getItem(idx)
                                        if item_text:
                                            url = endpoint_from_selector_text(item_text)
                                            if url:
                                                self._ctrl.setText(url)
                                            resolved = endpoint_from_selector_text(self._ctrl.getText())
                                            if not resolved:
                                                return
                                            text_ctrl = self._dlg.getControl("text_model")
                                            image_ctrl = self._dlg.getControl("image_model")
                                            if text_ctrl:
                                                populate_combobox_with_lru(
                                                    self._main.ctx, text_ctrl,
                                                    get_config(self._main.ctx, "text_model", "") or get_config(self._main.ctx, "model", ""),
                                                    "model_lru", resolved, strict=True)
                                            if image_ctrl:
                                                if get_config(self._main.ctx, "image_provider", "aihorde") == "endpoint":
                                                    populate_combobox_with_lru(
                                                        self._main.ctx, image_ctrl, get_image_model(self._main.ctx),
                                                        "image_model_lru", resolved, strict=True)
                                                else:
                                                    populate_image_model_selector(self._main.ctx, image_ctrl)
                                            api_key_ctrl = self._dlg.getControl("api_key")
                                            if api_key_ctrl:
                                                try:
                                                    api_key_ctrl.getModel().Text = get_api_key_for_endpoint(self._main.ctx, resolved)
                                                except Exception:
                                                    pass
                                    except Exception:
                                        pass
                                def disposing(self, ev):
                                    pass
                            ctrl.addItemListener(EndpointItemListener(dlg, self, ctrl))
                    elif field["name"] == "image_base_size":
                        self._populate_combobox_with_lru(ctrl, field["value"], "image_base_size_lru", "")
                    else:
                                is_checkbox = is_checkbox_control(ctrl)
                                if field.get("type") == "bool" and is_checkbox:
                                    val = 1 if as_bool(field["value"]) else 0
                                    try:
                                        set_checkbox_state(ctrl, val)
                                    except Exception as e:
                                        agent_log("main.py:settings_box", "checkbox init error", data={"field": field["name"], "error": str(e)}, hypothesis_id="H5")
                                else:
                                    ctrl.getModel().Text = field["value"]
            dlg.getControl("endpoint").setFocus()

            try:
                exec_result = dlg.execute()

                result = {}
                if exec_result:
                    for field in field_specs:
                        try:
                            ctrl = dlg.getControl(field["name"])
                            if ctrl:
                                if field["name"] in ("text_model", "image_model", "additional_instructions", "endpoint", "image_base_size"):
                                    # For ComboBox, use getText() to get the actual edit text (user input)
                                    control_text = ctrl.getText()
                                else:
                                    try:
                                        control_text = ctrl.getModel().Text if ctrl else ""
                                    except Exception:
                                        control_text = ""
                                
                                field_type = field.get("type", "text")
                                if field_type == "int":
                                    result[field["name"]] = int(control_text) if control_text.isdigit() else control_text
                                elif field_type == "bool":
                                    val = as_bool(control_text)
                                    if is_checkbox_control(ctrl):
                                        try:
                                            val = (get_checkbox_state(ctrl) == 1)
                                        except Exception as e:
                                            from core.logging import debug_log
                                            debug_log(f"checkbox state error for {field['name']}: {e}", context="Settings")
                                    result[field["name"]] = val
                                    from core.logging import debug_log
                                    debug_log(f"Field {field['name']}: is_checkbox={is_checkbox_control(ctrl)}, val={val}, ctrl_services={ctrl.getSupportedServiceNames() if hasattr(ctrl, 'getSupportedServiceNames') else 'N/A'}", context="Settings")
                                elif field_type == "float":
                                    try:
                                        result[field["name"]] = float(control_text)
                                    except ValueError:
                                        result[field["name"]] = control_text
                                else:
                                    result[field["name"]] = control_text
                            else:
                                result[field["name"]] = ""
                        except Exception:
                            result[field["name"]] = ""
            except Exception:
                result = {}
                raise

        finally:
            dlg.dispose()
        return result

    def _show_eval_dashboard(self):
        """Show the Evaluation Dashboard (EvalDialog.xdl)."""
        import uno
        from com.sun.star.awt import XActionListener
        from core.eval_runner import run_benchmark_suite

        ctx = self.ctx
        smgr = ctx.getServiceManager()
        pip = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation("org.extension.localwriter")
        dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
        dlg = dp.createDialog(base_url + "/LocalWriterDialogs/EvalDialog.xdl")

        try:
            # 1. Populate fields
            endpoint_ctrl = dlg.getControl("endpoint")
            endpoint_ctrl.getModel().Text = str(get_config(self.ctx, "endpoint", ""))
            
            model_ctrl = dlg.getControl("models")
            current_model = str(get_config(self.ctx, "text_model", "") or get_config(self.ctx, "model", ""))
            current_endpoint = str(get_config(self.ctx, "endpoint", "")).strip()
            populate_combobox_with_lru(self.ctx, model_ctrl, current_model, "model_lru", current_endpoint)
            
            log_area = dlg.getControl("log_area")
            status_text = dlg.getControl("status")

            # 2. Wire Run button
            class EvalRunListener(unohelper.Base, XActionListener):
                def __init__(self, main_job, dialog, toolkit):
                    self.main_job = main_job
                    self.dialog = dialog
                    self.toolkit = toolkit
                    self.is_running = False

                def actionPerformed(self, ev):
                    if self.is_running: return
                    self.is_running = True
                    try:
                        self.run_suite()
                    finally:
                        self.is_running = False

                def run_suite(self):
                    # Get UI values
                    model_name = self.dialog.getControl("models").getText()
                    categories = []
                    if self.dialog.getControl("cat_writer").getState(): categories.append("Writer")
                    if self.dialog.getControl("cat_calc").getState(): categories.append("Calc")
                    if self.dialog.getControl("cat_draw").getState(): categories.append("Draw")
                    if self.dialog.getControl("cat_multimodal").getState(): categories.append("Multimodal")
                    
                    self.dialog.getControl("log_area").setText(f"Starting benchmark for model: {model_name}...\n")
                    self.dialog.getControl("status").setText("Running...")
                    self.toolkit.processEventsToIdle()
                    
                    desktop = self.main_job.ctx.getServiceManager().createInstanceWithContext("com.sun.star.frame.Desktop", self.main_job.ctx)
                    doc = desktop.getCurrentComponent()
                    
                    # In a real impl, we might want to start separate worker threads
                    # but for benchmarks, sequential block-and-drain is fine if we call processEvents
                    from core.eval_runner import EvalRunner
                    runner = EvalRunner(self.main_job.ctx, doc, model_name)
                    
                    # We'll define the tests here or in eval_runner
                    # For dry run, use the basic ones in run_benchmark_suite
                    summary = run_benchmark_suite(self.main_job.ctx, doc, model_name, categories)
                    
                    # Update Log Area
                    log_text = f"Benchmarks Complete for {model_name}!\n"
                    log_text += f"Passed: {summary['passed']}, Failed: {summary['failed']}\n"
                    log_text += f"Total Est. Cost: ${summary['total_cost']:.4f}\n\n Details:\n"
                    for res in summary['results']:
                        log_text += f"[{res['status']}] {res['name']} ({res.get('latency', 0):.1f}s)\n"
                    
                    self.dialog.getControl("log_area").setText(log_text)
                    self.dialog.getControl("status").setText("Finished")

                def disposing(self, ev): pass

            toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
            dlg.getControl("btn_run").addActionListener(EvalRunListener(self, dlg, toolkit))
            dlg.getControl("btn_close").addActionListener(TabListener(dlg, 0)) # Close button (0 is dummy)
            
            # Close button needs its own listener or using dlg.endDialog()
            class CloseListener(unohelper.Base, XActionListener):
                def __init__(self, dialog): self.dialog = dialog
                def actionPerformed(self, ev): self.dialog.endDialog(0)
                def disposing(self, ev): pass
            dlg.getControl("btn_close").addActionListener(CloseListener(dlg))

            dlg.execute()
        finally:
            dlg.dispose()

    def trigger(self, args):
        init_logging(self.ctx)
        agent_log("main.py:trigger", "trigger called", data={"args": str(args)}, hypothesis_id="H1,H2")
        desktop = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx)
        model = desktop.getCurrentComponent()
        from core.document import is_writer, is_calc, is_draw
        agent_log("main.py:trigger", "model state", data={"model_is_none": model is None, "is_writer": is_writer(model) if model else False, "is_calc": is_calc(model) if model else False, "is_draw": is_draw(model) if model else False}, hypothesis_id="H2")
        #if not hasattr(model, "Text"):
        #    model = self.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())

        if args == "settings" and (not model or (not is_writer(model) and not is_calc(model) and not is_draw(model))):
            agent_log("main.py:trigger", "settings requested but no compatible document", data={"args": str(args)}, hypothesis_id="H2")

        if args == "ToggleMCPServer":
            _toggle_mcp_server(self.ctx)
            return
        if args == "MCPStatus":
            _do_mcp_status(self.ctx)
            return
        if args == "TestTypes":
            from core.test_types import test_types
            test_types(self.ctx)
            return
        if args == "DrainMCP":
            from core.mcp_thread import drain_mcp_queue
            drain_mcp_queue()
            return
        if args == "NoOp":
            return

        if args == "RunFormatTests":
            try:
                from core.format_tests import run_markdown_tests
                writer_model = model if (model and is_writer(model)) else None
                p, f, log = run_markdown_tests(self.ctx, writer_model)
                msg = "Format tests: %d passed, %d failed.\n\n%s" % (p, f, "\n".join(log))
                self.show_error(msg, "Format tests")
            except Exception as e:
                self.show_error("Tests failed to run: %s" % e, "Format tests")
            return

        if args == "RunCalcTests":
            try:
                from core.calc_tests import run_calc_tests
                calc_model = model if (model and is_calc(model)) else None
                p, f, log = run_calc_tests(self.ctx, calc_model)
                msg = "Calc tests: %d passed, %d failed.\n\n%s" % (p, f, "\n".join(log))
                self.show_error(msg, "Calc tests")
            except Exception as e:
                self.show_error("Tests failed to run: %s" % e, "Calc tests")
            return

        if args == "RunDrawTests":
            try:
                from core.draw_tests import run_draw_tests
                draw_model = model if (model and is_draw(model)) else None
                p, f, log = run_draw_tests(self.ctx, draw_model)
                msg = "Draw tests: %d passed, %d failed.\n\n%s" % (p, f, "\n".join(log))
                self.show_error(msg, "Draw tests")
            except Exception as e:
                self.show_error("Tests failed to run: %s" % e, "Draw tests")
            return

        if args == "RunCalcIntegrationTests":
            try:
                from core.calc_tests import run_calc_integration_tests
                calc_model = model if (model and is_calc(model)) else None
                p, f, log = run_calc_integration_tests(self.ctx, calc_model)
                msg = "Calc API integration: %d passed, %d failed.\n\n%s" % (p, f, "\n".join(log))
                self.show_error(msg, "Calc API integration tests")
            except Exception as e:
                self.show_error("Integration tests failed: %s" % e, "Calc API integration tests")
            return

        if args == "EvaluationDashboard":
            try:
                self._show_eval_dashboard()
            except Exception as e:
                self.show_error("Could not show evaluation dashboard: %s" % e, "Evaluation Dashboard")
            return

        if is_writer(model):
            text = model.Text
            selection = model.CurrentController.getSelection()
            text_range = selection.getByIndex(0)

            
            if args == "ExtendSelection":
                # Access the current selection
                if len(text_range.getString()) > 0:
                    try:
                        extra_instructions = self.get_config("additional_instructions", "")
                        system_prompt = extra_instructions # Extend usually benefits from just the custom prompt or none
                        current_endpoint = get_current_endpoint(self.ctx)
                        self._update_lru_history(system_prompt, "prompt_lru", current_endpoint)
                        prompt = text_range.getString()
                        max_tokens = self.get_config("extend_selection_max_tokens", 70)
                        model_val = self.get_config("text_model", "") or self.get_config("model", "")
                        self._update_lru_history(model_val, "model_lru", current_endpoint)
                        api_type = str(self.get_config("api_type", "completions")).lower()
                        api_config = get_api_config(self.ctx)
                        ok, err_msg = validate_api_config(api_config)
                        if not ok:
                            self.show_error(err_msg, "LocalWriter: Extend Selection")
                            return
                        client = self._get_client()

                        def apply_chunk(chunk_text, is_thinking=False):
                            if not is_thinking:
                                text_range.setString(text_range.getString() + chunk_text)

                        run_stream_completion_async(
                            self.ctx, client, prompt, system_prompt, max_tokens, api_type,
                            apply_chunk, lambda: None,
                            lambda e: self.show_error(format_error_message(e), "LocalWriter: Extend Selection"),
                        )
                    except Exception as e:
                        self.show_error(format_error_message(e), "LocalWriter: Extend Selection")

            elif args == "EditSelection":
                # Access the current selection
                original_text = text_range.getString()
                try:
                    user_input, extra_instructions = self.input_box("Please enter edit instructions!", "Input", "")
                    if not user_input:
                        return
                    
                    if extra_instructions:
                        self.set_config("additional_instructions", extra_instructions)
                        current_endpoint = get_current_endpoint(self.ctx)
                        self._update_lru_history(extra_instructions, "prompt_lru", current_endpoint)

                except Exception as e:
                    self.show_error(format_error_message(e), "LocalWriter: Edit Selection")
                    return
                prompt = "ORIGINAL VERSION:\n" + original_text + "\n Below is an edited version according to the following instructions. There are no comments in the edited version. The edited version is followed by the end of the document. The original version will be edited as follows to create the edited version:\n" + user_input + "\nEDITED VERSION:\n"
                system_prompt = extra_instructions or ""
                max_tokens = len(original_text) + self.get_config("edit_selection_max_new_tokens", 0)
                api_type = str(self.get_config("api_type", "completions")).lower()
                api_config = get_api_config(self.ctx)
                ok, err_msg = validate_api_config(api_config)
                if not ok:
                    self.show_error(err_msg, "LocalWriter: Edit Selection")
                    return
                text_range.setString("")
                client = self._get_client()

                def apply_chunk(chunk_text, is_thinking=False):
                    if not is_thinking:
                        text_range.setString(text_range.getString() + chunk_text)

                def on_error(e):
                    text_range.setString(original_text)
                    self.show_error(format_error_message(e), "LocalWriter: Edit Selection")

                try:
                    run_stream_completion_async(
                        self.ctx, client, prompt, system_prompt, max_tokens, api_type,
                        apply_chunk, lambda: None, on_error,
                    )
                except Exception as e:
                    text_range.setString(original_text)
                    self.show_error(format_error_message(e), "LocalWriter: Edit Selection")

            elif args == "settings":
                try:
                    agent_log("main.py:trigger", "about to call settings_box (Writer)", hypothesis_id="H1,H2")
                    result = self.settings_box("Settings")
                    self._apply_settings_result(result)
                    _start_mcp_server(self.ctx)
                except Exception as e:
                    agent_log("main.py:trigger", "settings exception (Writer)", data={"error": str(e)}, hypothesis_id="H5")
                    self.show_error(format_error_message(e), "LocalWriter: Settings")
        elif is_calc(model):
            try:
                sheet = model.CurrentController.ActiveSheet
                selection = model.CurrentController.Selection

                if args == "settings":
                    try:
                        agent_log("main.py:trigger", "about to call settings_box (Calc)", hypothesis_id="H1,H2")
                        result = self.settings_box("Settings")
                        self._apply_settings_result(result)
                        _start_mcp_server(self.ctx)
                    except Exception as e:
                        agent_log("main.py:trigger", "settings exception (Calc)", data={"error": str(e)}, hypothesis_id="H5")
                        self.show_error(format_error_message(e), "LocalWriter: Settings")
                    return

                user_input = ""
                if args == "EditSelection":
                    user_input = self.input_box("Please enter edit instructions!", "Input", "")

                area = selection.getRangeAddress()
                start_row = area.StartRow
                end_row = area.EndRow
                start_col = area.StartColumn
                end_col = area.EndColumn

                col_range = range(start_col, end_col + 1)
                row_range = range(start_row, end_row + 1)

                api_type = str(self.get_config("api_type", "completions")).lower()
                extend_system_prompt = self.get_config("extend_selection_system_prompt", "")
                extend_max_tokens = self.get_config("extend_selection_max_tokens", 70)
                edit_system_prompt = self.get_config("edit_selection_system_prompt", "")
                edit_max_new_tokens = self.get_config("edit_selection_max_new_tokens", 0)
                try:
                    edit_max_new_tokens = int(edit_max_new_tokens)
                except (TypeError, ValueError):
                    edit_max_new_tokens = 0

                # Build list of (cell, prompt, system_prompt, max_tokens, original_for_restore or None)
                tasks = []
                for row in row_range:
                    for col in col_range:
                        cell = sheet.getCellByPosition(col, row)
                        if args == "ExtendSelection":
                            cell_text = cell.getString()
                            if not cell_text:
                                continue
                            tasks.append((cell, cell_text, extend_system_prompt, extend_max_tokens, None))
                        elif args == "EditSelection":
                            cell_original = cell.getString()
                            prompt = "ORIGINAL VERSION:\n" + cell_original + "\n Below is an edited version according to the following instructions. Don't waste time thinking, be as fast as you can. The edited text will be a shorter or longer version of the original text based on the instructions. There are no comments in the edited version. The edited version is followed by the end of the document. The original version will be edited as follows to create the edited version:\n" + user_input + "\nEDITED VERSION:\n"
                            max_tokens = len(cell_original) + edit_max_new_tokens
                            tasks.append((cell, prompt, edit_system_prompt, max_tokens, cell_original))

                api_config = get_api_config(self.ctx)
                ok, err_msg = validate_api_config(api_config)
                if not ok:
                    self.show_error(err_msg, "LocalWriter: Edit Selection (Calc)" if args == "EditSelection" else "LocalWriter: Extend Selection (Calc)")
                    return
                client = self._get_client()
                task_index = [0]

                def run_next_cell():
                    if task_index[0] >= len(tasks):
                        return
                    cell, prompt, system_prompt, max_tokens, original = tasks[task_index[0]]
                    task_index[0] += 1
                    if args == "EditSelection" and original is not None:
                        cell.setString("")

                    def apply_chunk(chunk_text, is_thinking=False):
                        if not is_thinking:
                            cell.setString(cell.getString() + chunk_text)

                    def on_done():
                        run_next_cell()

                    def on_error(e):
                        if original is not None:
                            cell.setString(original)
                        self.show_error(format_error_message(e), "LocalWriter: Edit Selection (Calc)" if args == "EditSelection" else "LocalWriter: Extend Selection (Calc)")
                        # Stop on first error: do not call run_next_cell()

                    run_stream_completion_async(
                        self.ctx, client, prompt, system_prompt, max_tokens, api_type,
                        apply_chunk, on_done, on_error,
                    )

                if tasks:
                    run_next_cell()
            except Exception as e:
                self.show_error(format_error_message(e), "LocalWriter: Calc Processing")
        elif is_draw(model):
            if args == "settings":
                try:
                    result = self.settings_box("Settings")
                    self._apply_settings_result(result)
                    _start_mcp_server(self.ctx)
                except Exception as e:
                    self.show_error(format_error_message(e), "LocalWriter: Settings")
                return
# Starting from Python IDE
def main():
    try:
        ctx = XSCRIPTCONTEXT
    except NameError:
        ctx = officehelper.bootstrap()
        if ctx is None:
            print("ERROR: Could not bootstrap default Office.")
            sys.exit(1)
    job = MainJob(ctx)
    job.trigger("hello")
# Starting from command line
if __name__ == "__main__":
    main()

# pythonloader loads a static g_ImplementationHelper variable
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    MainJob,  # UNO object class
    "org.extension.localwriter.Main",  # implementation name (customize for yourself)
    ("com.sun.star.task.Job",), )  # implemented services (only 1)
# vim: set shiftwidth=4 softtabstop=4 expandtab:

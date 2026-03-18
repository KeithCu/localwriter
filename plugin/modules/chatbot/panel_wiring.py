import weakref

from plugin.framework.logging import debug_log
from plugin.framework.uno_helpers import (
    get_optional as get_optional_control,
    get_checkbox_state,
)
from plugin.modules.chatbot.panel_resize import _PanelResizeListener


def _wireControls(self, root_window, has_recording, ensure_extension_on_path):
    """Main entry point to wire all controls for the panel."""
    debug_log("_wireControls entered", context="Chat")
    if not hasattr(root_window, "getControl"):
        debug_log("_wireControls: root_window has no getControl, aborting", context="Chat")
        return

    def get_optional(name):
        return get_optional_control(root_window, name)

    controls = {
        "send": root_window.getControl("send"),
        "query": root_window.getControl("query"),
        "response": root_window.getControl("response"),
        "stop": get_optional("stop"),
        "clear": get_optional("clear"),
        "image_model_selector": get_optional("image_model_selector"),
        "prompt_selector": get_optional("prompt_selector"),
        "model_selector": get_optional("model_selector"),
        "model_label": get_optional("model_label"),
        "status": get_optional("status"),
        "direct_image_check": get_optional("direct_image_check"),
        "web_research_check": get_optional("web_research_check"),
        "aspect_ratio_selector": get_optional("aspect_ratio_selector"),
        "base_size_input": get_optional("base_size_input"),
        "base_size_label": get_optional("base_size_label"),
        "response_label": get_optional("response_label"),
        "query_label": get_optional("query_label"),
        "backend_indicator": get_optional("backend_indicator"),
    }

    # Helper to show errors visibly in the response area
    def _show_init_error(msg):
        debug_log("_wireControls ERROR: %s" % msg, context="Chat")
        try:
            if controls["response"] and controls["response"].getModel():
                current = controls["response"].getModel().Text or ""
                controls["response"].getModel().Text = current + "[Init error: %s]\n" % msg
        except Exception:
            pass

    ensure_extension_on_path(self.ctx)

    # 1. Config, Models, and UI
    try:
        from plugin.framework.config import get_config
        extra_instructions = get_config(self.ctx, "additional_instructions")
        
        self._wire_model_selectors(controls["model_selector"], controls["image_model_selector"])
        
        set_control_enabled = self._wire_image_ui(
            controls["aspect_ratio_selector"], controls["base_size_input"], controls["base_size_label"],
            controls["direct_image_check"], controls["web_research_check"], controls["model_label"], 
            controls["model_selector"], controls["image_model_selector"]
        )
    except Exception as e:
        import traceback
        _show_init_error("Config: %s" % e)
        debug_log(traceback.format_exc(), context="Chat")
        extra_instructions = ""
        set_control_enabled = lambda ctrl, en: None

    # 2. Setup embedded rich text document if we have a response control
    try:
        from plugin.modules.chatbot.rich_text import create_embedded_writer_doc
        if controls["response"]:
            # Create our embedded Writer document in the same position.
            # If this fails, keep the old plain text response visible as a fallback.
            doc_info = create_embedded_writer_doc(self.ctx, root_window, controls["response"])
            if doc_info:
                # Hide the old plain text field only if we created a separate
                # container window for the rich Writer document.
                controls["response"].setVisible(False)
                controls["rich_response_doc"] = doc_info["doc"]
                controls["rich_response_win"] = doc_info["win"]
            else:
                debug_log(
                    "Rich embedded doc creation failed; leaving plain response control visible",
                    context="Chat",
                )
    except Exception as e:
        debug_log("Failed to create rich text embedded document: %s" % e, context="Chat")

    # 3. Setup Sessions
    model = self._get_document_model()
    self._setup_sessions(model, extra_instructions)

    # 4. Determine Mode & Greeting
    from plugin.framework.constants import get_greeting_for_document, DEFAULT_RESEARCH_GREETING
    web_checked = False
    if controls["web_research_check"]:
        try: web_checked = (get_checkbox_state(controls["web_research_check"]) == 1)
        except Exception: pass
        
    if web_checked:
        self.session = self.web_session
        active_greeting = DEFAULT_RESEARCH_GREETING
    else:
        self.session = self.doc_session
        active_greeting = get_greeting_for_document(model)

    self._render_session_history(self.session, controls, model, active_greeting)

    # 5. Buttons
    self._wire_buttons(controls, model, active_greeting, set_control_enabled)

    # Wire query listener to update Record/Send button label
    if controls["query"] and controls["send"]:
        try:
            from plugin.modules.chatbot.panel import QueryTextListener
            controls["query"].addTextListener(QueryTextListener(controls["send"]))
            if controls["query"].getModel().Text.strip():
                controls["send"].getModel().Label = "Send"
            else:
                controls["send"].getModel().Label = "Record" if has_recording else "Send"
        except Exception as e:
            debug_log("QueryTextListener setup error: %s" % e, context="Chat")

    if controls["status"] and hasattr(controls["status"], "setText"):
        try: controls["status"].setText("Ready")
        except Exception: pass

    # 5. Timer and Resize
    try:
        from main import try_ensure_mcp_timer
        try_ensure_mcp_timer(self.ctx)
    except Exception as e:
        debug_log("try_ensure_mcp_timer: %s" % e, context="Chat")

    try:
        debug_log(
            "Attaching _PanelResizeListener to root_window; controls=%s"
            % (sorted(k for k, v in controls.items() if v)),
            context="Chat",
        )
        _resize = _PanelResizeListener(controls)
        root_window.addWindowListener(_resize)
        _resize._relayout(root_window)
    except Exception as e:
        debug_log("Resize listener error: %s" % e, context="Chat")

    # Backend indicator (Aider / Hermes when external agent enabled)
    self._update_backend_indicator(root_window)

    # 6. Global Config Listener
    from plugin.framework.config import add_config_listener
    _self_ref = weakref.ref(self)
    def on_config_changed(ctx):
        panel = _self_ref()
        if panel is not None:
            panel._refresh_controls_from_config()
    add_config_listener(on_config_changed)

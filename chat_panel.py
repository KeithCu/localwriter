# Chat with Document - Sidebar Panel implementation
# Follows the working pattern from LibreOffice's Python ToolPanel example:
# XUIElement wrapper creates panel in getRealInterface() via ContainerWindowProvider + XDL.

import os
import sys
import json
import queue
import threading
import weakref
import uno
import unohelper

# Ensure extension directory is on path so core can be imported
_ext_dir = os.path.dirname(os.path.abspath(__file__))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)

from core.logging import agent_log, debug_log, update_activity_state, start_watchdog_thread, init_logging
from core.async_stream import run_stream_completion_async, run_stream_drain_loop
from core.uno_ui_helpers import get_optional as get_optional_control, get_checkbox_state, set_checkbox_state

from com.sun.star.ui import XUIElementFactory, XUIElement, XToolPanel, XSidebarPanel
from com.sun.star.ui.UIElementType import TOOLPANEL
from com.sun.star.awt import XActionListener, XItemListener

# Extension ID from description.xml; XDL path inside the .oxt
EXTENSION_ID = "org.extension.localwriter"
XDL_PATH = "LocalWriterDialogs/ChatPanelDialog.xdl"

# Default max tool rounds when not in config (get_api_config supplies chat_max_tool_rounds)
DEFAULT_MAX_TOOL_ROUNDS = 5

# Default system prompt for the chat sidebar (imported from main inside methods to avoid unopkg errors)
DEFAULT_SYSTEM_PROMPT_FALLBACK = "You are a helpful assistant."


def _get_arg(args, name):
    """Extract PropertyValue from args by Name."""
    for pv in args:
        if hasattr(pv, "Name") and pv.Name == name:
            return pv.Value
    return None





def _ensure_extension_on_path(ctx):
    """Add the extension's directory to sys.path so cross-module imports work.
    LibreOffice registers each .py as a UNO component individually but does not
    put the extension folder on sys.path, so 'from main import ...' and
    'from document_tools import ...' fail without this."""
    import sys
    try:
        pip = ctx.getValueByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        ext_url = pip.getPackageLocation(EXTENSION_ID)
        if ext_url.startswith("file://"):
            ext_path = str(uno.fileUrlToSystemPath(ext_url))
        else:
            ext_path = ext_url
        if ext_path and ext_path not in sys.path:
            sys.path.insert(0, ext_path)
            init_logging(ctx)
            debug_log("Added extension path to sys.path: %s" % ext_path, context="Chat")
        else:
            init_logging(ctx)
            debug_log("Extension path already on sys.path: %s" % ext_path, context="Chat")
    except Exception as e:
        init_logging(ctx)
        debug_log("_ensure_extension_on_path ERROR: %s" % e, context="Chat")


# ---------------------------------------------------------------------------
# ChatSession - holds conversation history for multi-turn chat
# ---------------------------------------------------------------------------

class ChatSession:
    """Maintains the message history for one sidebar chat session."""

    def __init__(self, system_prompt=None):
        self.messages = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content=None, tool_calls=None):
        msg = {"role": "assistant"}
        if content:
            msg["content"] = content
        else:
            msg["content"] = None
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id, content):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def update_document_context(self, doc_text):
        """Update or insert the document context as a system message.
        Replaces the existing document context if present, otherwise appends."""
        context_marker = "[DOCUMENT CONTENT]"
        context_msg = "%s\n%s\n[END DOCUMENT]" % (context_marker, doc_text)

        # Check if we already have a document context message
        for i, msg in enumerate(self.messages):
            if msg["role"] == "system" and context_marker in (msg.get("content") or ""):
                self.messages[i]["content"] = context_msg
                return
        # Insert after the first system prompt
        insert_at = 1 if self.messages and self.messages[0]["role"] == "system" else 0
        self.messages.insert(insert_at, {"role": "system", "content": context_msg})

    def clear(self):
        """Reset to just the system prompt."""
        system = None
        for msg in self.messages:
            if msg["role"] == "system" and "[DOCUMENT CONTENT]" not in (msg.get("content") or ""):
                system = msg
                break
        self.messages = []
        if system:
            self.messages.append(system)


# ---------------------------------------------------------------------------
# SendButtonListener - handles Send button click with tool-calling loop
# ---------------------------------------------------------------------------

class SendButtonListener(unohelper.Base, XActionListener):
    """Listener for the Send button - runs chat with document, supports tool-calling."""

    def __init__(self, ctx, frame, send_control, stop_control, query_control, response_control, image_model_selector, model_selector, status_control, session, direct_image_checkbox=None, aspect_ratio_selector=None, base_size_input=None):
        self.ctx = ctx
        self.frame = frame
        self.send_control = send_control
        self.stop_control = stop_control
        self.query_control = query_control
        self.response_control = response_control
        self.image_model_selector = image_model_selector
        self.model_selector = model_selector
        self.status_control = status_control
        self.session = session
        self.direct_image_checkbox = direct_image_checkbox
        self.aspect_ratio_selector = aspect_ratio_selector
        self.base_size_input = base_size_input
        self.initial_doc_type = None # Set by _wireControls
        self.stop_requested = False
        self._terminal_status = "Ready"
        self._send_busy = False
        self.client = None

        # Subscribe to MCP/tool bus events
        try:
            from core.tool_bus import tool_bus
            tool_bus.subscribe(self._on_mcp_event)
        except Exception as e:
            debug_log("MCP subscribe error: %s" % e, context="Chat")

    def _set_status(self, text):
        """Update the status field in the sidebar (read-only TextField).
        Uses setText() (XTextComponent) to write directly to the control/peer,
        bypassing model→view notifications which can desync after document edits."""
        try:
            if self.status_control:
                self.status_control.setText(text)
            else:
                debug_log("_set_status: NO CONTROL for '%s'" % text, context="Chat")
        except Exception as e:
            debug_log("_set_status('%s') EXCEPTION: %s" % (text, e), context="Chat")

    def _scroll_response_to_bottom(self):
        """Scroll the response area to show the bottom (newest content).
        Uses XTextComponent.setSelection to place caret at end, which scrolls the view."""
        try:
            if self.response_control:
                model = self.response_control.getModel()
                if model and hasattr(self.response_control, "setSelection"):
                    text = model.Text or ""
                    length = len(text)
                    self.response_control.setSelection(
                        uno.createUnoStruct("com.sun.star.awt.Selection", length, length))
        except Exception:
            pass

    def _append_response(self, text):
        """Append text to the response area."""
        try:
            if self.response_control and self.response_control.getModel():
                current = self.response_control.getModel().Text or ""
                self.response_control.getModel().Text = current + text
                self._scroll_response_to_bottom()
        except Exception:
            pass

    def _on_mcp_event(self, event_type, data):
        """Handle MCP events from the bus (background thread)."""
        from core.mcp_thread import post_to_main_thread
        from core.config import get_config
        
        # Default to show if key is missing
        if not get_config(self.ctx, "show_mcp_activity", True):
            return

        def _update_ui():
            try:
                if event_type == "request":
                    tool = data.get("tool", "")
                    args = data.get("args", {})
                    
                    arg_vals = []
                    if isinstance(args, dict):
                        for v in args.values():
                            s = str(v)
                            if len(s) > 10:
                                s = s[:10]
                            arg_vals.append(s)
                    
                    args_str = " (%s)" % ", ".join(arg_vals) if arg_vals else ""
                    msg = "\n[MCP Request] Tool: %s%s\n" % (tool, args_str) if tool else "\n[MCP Request] %s\n" % data.get("method", "GET")
                    self._append_response(msg)
                elif event_type == "result":
                    tool = data.get("tool", "")
                    res = data.get("result", "")
                    msg = "[MCP Result] %s: %s\n" % (tool, res[:100])
                    self._append_response(msg)
            except Exception as e:
                debug_log("_on_mcp_event UI update error: %s" % e, context="Chat")
        
        try:
            post_to_main_thread(_update_ui)
        except Exception as e:
            debug_log("_on_mcp_event post error: %s" % e, context="Chat")

    def _get_document_model(self):
        """Get the Writer document model."""
        model = None
        if self.frame:
            try:
                model = self.frame.getController().getModel()
            except Exception:
                pass
        if not model:
            desktop = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx)
            model = desktop.getCurrentComponent()

        from core.document import is_writer, is_calc, is_draw
        if model and (is_writer(model) or is_calc(model) or is_draw(model)):
            return model
        return None

    def _set_button_states(self, send_enabled, stop_enabled):
        """Set Send/Stop button enabled states. Per-control try/except so one failure cannot leave Send stuck disabled.
        Prefer model Enabled property (LibreOffice UNO); fallback to control.setEnable if available."""
        def set_control_enabled(control, enabled):
            if control and control.getModel():
                control.getModel().Enabled = bool(enabled)
        set_control_enabled(self.send_control, send_enabled)
        set_control_enabled(self.stop_control, stop_enabled)

    def actionPerformed(self, evt):
        try:
            self.stop_requested = False
            self._terminal_status = "Ready"
            self._send_busy = True
            self._set_button_states(send_enabled=False, stop_enabled=True)
            self._do_send()
        except Exception as e:
            self._terminal_status = "Error"
            import traceback
            tb = traceback.format_exc()
            self._append_response("\n\n[Error: %s]\n%s\n" % (str(e), tb))
            debug_log("SendButton error: %s\n%s" % (e, tb), context="Chat")
        finally:
            self._send_busy = False
            debug_log("actionPerformed finally: resetting UI", context="Chat")
            self._set_status(self._terminal_status)
            self._set_button_states(send_enabled=True, stop_enabled=False)
            debug_log("control returned to LibreOffice", context="Chat")
            update_activity_state("")  # clear phase so watchdog does not report after we return

    def _do_send(self):
        self._set_status("Starting...")
        update_activity_state("do_send")
        debug_log("=== _do_send START ===", context="Chat")

        # Ensure extension directory is on sys.path
        _ensure_extension_on_path(self.ctx)

        try:
            debug_log("_do_send: importing core modules...", context="Chat")
            from core.config import get_config, get_api_config, update_lru_history, validate_api_config
            from core.api import LlmClient
            from core.document import get_document_context_for_chat, is_calc, is_draw, is_writer
            debug_log("_do_send: core modules imported OK", context="Chat")
        except Exception as e:
            debug_log("_do_send: core import FAILED: %s" % e, context="Chat")
            self._append_response("\n[Import error - core: %s]\n" % e)
            self._terminal_status = "Error"
            return

        # 1. Get document model
        self._set_status("Getting document...")
        debug_log("_do_send: getting document model...", context="Chat")
        model = self._get_document_model()
        if not model:
            debug_log("_do_send: no document found", context="Chat")
            self._append_response("\n[No compatible LibreOffice document (Writer, Calc, or Draw) found in the active window.]\n")
            self._terminal_status = "Error"
            return
        debug_log("_do_send: got document model OK", context="Chat")
        
        # Verify document type matches what we expect from sidebar initialization
        # (A new sidebar is created/wired for a new document, so it shouldn't change).
        is_calc_doc = is_calc(model)
        is_draw_doc = is_draw(model)
        is_writer_doc = is_writer(model)
        
        doc_type_str = "Calc" if is_calc_doc else "Draw" if is_draw_doc else "Writer" if is_writer_doc else "Unknown"
        debug_log("_do_send: detected document type: %s" % doc_type_str, context="Chat")
        
        # Verify document type hasn't changed since this sidebar was wired
        if self.initial_doc_type and doc_type_str != self.initial_doc_type:
            err_msg = "[Internal Error: Document type changed from %s to %s! Please file an error.]" % (self.initial_doc_type, doc_type_str)
            debug_log("_do_send ERROR: %s" % err_msg, context="Chat")
            self._append_response("\n%s\n" % err_msg)
            self._terminal_status = "Error"
            return

        # If no type detected, show error as per user request to identify "slop"
        if not (is_calc_doc or is_draw_doc or is_writer_doc):
            err_msg = "[Internal Error: Could not identify document type for %s. Please report this!]" % (model.getImplementationName() if hasattr(model, "getImplementationName") else "Unknown")
            debug_log("_do_send ERROR: %s" % err_msg, context="Chat")
            self._append_response("\n%s\n" % err_msg)
            self._terminal_status = "Error"
            return

        # Get user query and clear field (before loading tools, so direct-image path can return early)
        query_text = ""
        if self.query_control and self.query_control.getModel():
            query_text = (self.query_control.getModel().Text or "").strip()
        if not query_text:
            self._terminal_status = ""
            return
        if self.query_control and self.query_control.getModel():
            self.query_control.getModel().Text = ""

        # Direct image path: orthogonal to LLM tool list; uses document_tools.execute_tool for all doc types
        direct_image_checked = False
        read_state = None
        if self.direct_image_checkbox:
            try:
                read_state = get_checkbox_state(self.direct_image_checkbox)
                direct_image_checked = (read_state == 1)
            except Exception as e:
                debug_log("_do_send: Use Image model checkbox read error: %s" % e, context="Chat")
        debug_log("_do_send: Use Image model checkbox state=%s -> %s" % (read_state, "image model (direct)" if direct_image_checked else "chat model"), context="Chat")
        if direct_image_checked:
            debug_log("_do_send: using image model (direct) — skip chat model", context="Chat")
            try:
                self._append_response("\nYou: %s\n" % query_text)
                self._append_response("\n[Using image model (direct).]\n")
                self._append_response("AI: Creating image...\n")
                self._set_status("Creating image...")
                q = queue.Queue()
                job_done = [False]

                def run_direct_image():
                    try:
                        # Fetch aspect ratio and base size from UI
                        aspect_ratio_str = "Square"
                        if self.aspect_ratio_selector and hasattr(self.aspect_ratio_selector, "getText"):
                            aspect_ratio_str = self.aspect_ratio_selector.getText()
                            
                        # Map UI string to backend enum
                        aspect_map = {
                            "Square": "square",
                            "Landscape (16:9)": "landscape_16_9",
                            "Portrait (9:16)": "portrait_9_16",
                            "Landscape (3:2)": "landscape_3_2",
                            "Portrait (2:3)": "portrait_2_3"
                        }
                        mapped_aspect = aspect_map.get(aspect_ratio_str, "square")
                        
                        image_model_text = ""
                        if self.image_model_selector and hasattr(self.image_model_selector, "getText"):
                            image_model_text = self.image_model_selector.getText()

                        base_size_val = 512
                        if self.base_size_input:
                            if hasattr(self.base_size_input, "getText"):
                                base_size_val = self.base_size_input.getText()
                            elif hasattr(self.base_size_input.getModel(), "Text"):
                                base_size_val = self.base_size_input.getModel().Text
                        try:
                            base_size_val = int(base_size_val)
                        except (ValueError, TypeError):
                            base_size_val = 512

                        from core.document_tools import execute_tool
                        try:
                            # Also update LRU
                            from core.config import update_lru_history, get_current_endpoint
                            current_endpoint = get_current_endpoint(self.ctx)
                            update_lru_history(self.ctx, base_size_val, "image_base_size_lru", "")
                        except Exception as elru:
                            debug_log("LRU update error: %s" % elru, context="Chat")
                            
                        result = execute_tool(
                            "generate_image",
                            {
                                "prompt": query_text,
                                "aspect_ratio": mapped_aspect,
                                "base_size": base_size_val,
                                "image_model": image_model_text
                            },
                            model,
                            self.ctx,
                            status_callback=lambda t: q.put(("status", t)),
                        )
                        try:
                            data = json.loads(result)
                            note = data.get("message", data.get("status", "done"))
                        except Exception:
                            note = "done"
                        q.put(("chunk", "[generate_image: %s]\n" % note))
                        q.put(("stream_done", {}))
                    except Exception as e:
                        debug_log("Direct image path ERROR: %s" % e, context="Chat")
                        q.put(("error", e))

                threading.Thread(target=run_direct_image, daemon=True).start()
                try:
                    toolkit = self.ctx.getServiceManager().createInstanceWithContext(
                        "com.sun.star.awt.Toolkit", self.ctx)
                except Exception as e:
                    self._append_response("\n[Error: %s]\n" % str(e))
                    self._terminal_status = "Error"
                    return

                def apply_chunk(chunk_text, is_thinking=False):
                    self._append_response(chunk_text)

                def on_stream_done(response):
                    job_done[0] = True
                    return True

                def on_stopped():
                    self._terminal_status = "Stopped"
                    self._set_status("Stopped")

                def on_error(e):
                    from core.api import format_error_message
                    self._append_response("\n[%s]\n" % format_error_message(e))
                    self._terminal_status = "Error"
                    self._set_status("Error")

                run_stream_drain_loop(
                    q, toolkit, job_done, apply_chunk,
                    on_stream_done=on_stream_done,
                    on_stopped=on_stopped,
                    on_error=on_error,
                    on_status_fn=self._set_status,
                    ctx=self.ctx,
                )
                if self._terminal_status != "Error":
                    self._terminal_status = "Ready"
            finally:
                self._set_status(self._terminal_status)
                self._set_button_states(send_enabled=True, stop_enabled=False)
            return

        try:
            if is_calc_doc:
                debug_log("_do_send: importing calc_tools...", context="Chat")
                from core.calc_tools import CALC_TOOLS, execute_calc_tool
                active_tools = CALC_TOOLS
                # Calc tools don't support status_callback yet, but we should handle the kwarg safely
                execute_fn = lambda name, args, doc, ctx, status_callback=None: execute_calc_tool(name, args, doc)
                debug_log("_do_send: calc_tools imported OK (%d tools)" % len(CALC_TOOLS), context="Chat")
            elif is_draw_doc:
                debug_log("_do_send: importing draw_tools...", context="Chat")
                from core.draw_tools import DRAW_TOOLS, execute_draw_tool
                active_tools = DRAW_TOOLS
                execute_fn = execute_draw_tool
                debug_log("_do_send: draw_tools imported OK (%d tools)" % len(DRAW_TOOLS), context="Chat")
            else:
                debug_log("_do_send: importing document_tools...", context="Chat")
                from core.document_tools import WRITER_TOOLS, execute_tool
                active_tools = WRITER_TOOLS
                execute_fn = execute_tool

                debug_log("_do_send: document_tools imported OK (%d tools)" % len(WRITER_TOOLS), context="Chat")
        except Exception as e:
            debug_log("_do_send: tool import FAILED: %s" % e, context="Chat")
            self._append_response("\n[Import error - tools: %s]\n" % e)
            self._terminal_status = "Error"
            return

        # System prompt: extra_instructions from config only (not in sidebar)
        from core.config import set_config, update_lru_history, set_image_model, get_config, get_current_endpoint
        extra_instructions = get_config(self.ctx, "additional_instructions", "") or ""
        from core.constants import get_chat_system_prompt_for_document
        self.session.messages[0]["content"] = get_chat_system_prompt_for_document(model, extra_instructions)

        # Update text model and image model from selectors
        if self.model_selector:
            selected_model = self.model_selector.getText()
            if selected_model:
                set_config(self.ctx, "text_model", selected_model)
                current_endpoint = get_current_endpoint(self.ctx)
                update_lru_history(self.ctx, selected_model, "model_lru", current_endpoint)
                debug_log("_do_send: text model updated to %s" % selected_model, context="Chat")
        if self.image_model_selector:
            selected_image_model = self.image_model_selector.getText()
            if selected_image_model:
                set_image_model(self.ctx, selected_image_model)
                debug_log("_do_send: image model updated to %s" % selected_image_model, context="Chat")

        # 3. Set up config and LlmClient
        max_context = int(get_config(self.ctx, "chat_context_length", 8000))
        max_tokens = int(get_config(self.ctx, "chat_max_tokens", 16384))
        api_type = str(get_config(self.ctx, "api_type", "chat")).lower()
        debug_log("_do_send: config loaded: api_type=%s, max_tokens=%d, max_context=%d" %
                    (api_type, max_tokens, max_context), context="Chat")

        # Determine if tool-calling is available (requires chat API)
        use_tools = (api_type == "chat")

        api_config = get_api_config(self.ctx)
        ok, err_msg = validate_api_config(api_config)
        if not ok:
            self._append_response("\n[%s]\n" % err_msg)
            self._terminal_status = "Error"
            self._set_status("Error")
            return

        if not self.client:
            self.client = LlmClient(api_config, self.ctx)
        else:
            self.client.config = api_config
        client = self.client

        # 4. Refresh document context in session (start + end excerpts, inline selection/cursor markers)
        self._set_status("Reading document...")
        try:
            doc_text = get_document_context_for_chat(model, max_context, include_end=True, include_selection=True, ctx=self.ctx)
            debug_log("_do_send: document context length=%d" % len(doc_text), context="Chat")
            agent_log("chat_panel.py:doc_context", "Document context for AI", data={"doc_length": len(doc_text), "doc_prefix_first_200": (doc_text or "")[:200], "max_context": max_context}, hypothesis_id="B")
            self.session.update_document_context(doc_text)
        except Exception as e:
            debug_log("_do_send: document context FAILED: %s" % e, context="Chat")
            self._append_response("\n[Document unavailable or closed.]\n")
            self._terminal_status = "Error"
            self._set_status("Error")
            return

        # 5. Add user message to session and display
        self.session.add_user_message(query_text)
        self._append_response("\nYou: %s\n" % query_text)
        self._append_response("\n[Using chat model.]\n")
        debug_log("_do_send: using chat model", context="Chat")
        debug_log("_do_send: user query='%s'" % query_text[:100], context="Chat")

        self._set_status("Connecting to AI (api_type=%s, tools=%s)..." % (api_type, use_tools))
        debug_log("_do_send: calling AI, use_tools=%s, messages=%d" %
                    (use_tools, len(self.session.messages)), context="Chat")
        if use_tools:
            max_tool_rounds = api_config.get("chat_max_tool_rounds", DEFAULT_MAX_TOOL_ROUNDS)
            self._start_tool_calling_async(client, model, max_tokens, active_tools, execute_fn, max_tool_rounds)
        else:
            self._start_simple_stream_async(client, max_tokens, api_type)

        debug_log("=== _do_send END (async started) ===", context="Chat")

    # Future work: Undo grouping for AI edits (user can undo all edits from one turn with Ctrl+Z).
    # Previous attempt used enterUndoContext("AI Edit") / leaveUndoContext() but leaveUndoContext
    # was failing in some environments. Revisit when integrating with the async tool-calling path.

    def _start_tool_calling_async(self, client, model, max_tokens, tools, execute_tool_fn, max_tool_rounds=None):
        """Tool-calling loop: worker thread + queue, main thread drains queue with processEventsToIdle (pure Python threading, no UNO Timer)."""
        if max_tool_rounds is None:
            max_tool_rounds = DEFAULT_MAX_TOOL_ROUNDS
        debug_log("=== Tool-calling loop START (max %d rounds) ===" % max_tool_rounds, context="Chat")
        self._append_response("\nAI: ")
        q = queue.Queue()
        round_num = [0]
        job_done = [False]

        def start_worker():
            r = round_num[0]
            update_activity_state("tool_loop", round_num=r)
            debug_log("Tool loop round %d: sending %d messages to API..." % (r, len(self.session.messages)), context="Chat")
            self._set_status("Waiting for model..." if r == 0 else "Connecting (round %d)..." % (r + 1))

            def run():
                try:
                    response = client.stream_request_with_tools(
                        self.session.messages, max_tokens, tools=tools,
                        append_callback=lambda t: q.put(("chunk", t)),
                        append_thinking_callback=lambda t: q.put(("thinking", t)),
                        stop_checker=lambda: self.stop_requested,
                    )
                    if self.stop_requested:
                        q.put(("stopped",))
                    else:
                        update_activity_state("tool_loop", round_num=r)
                        q.put(("stream_done", response))
                except Exception as e:
                    debug_log("Tool loop round %d: API ERROR: %s" % (r, e), context="Chat")
                    q.put(("error", e))

            threading.Thread(target=run, daemon=True).start()

        def start_final_stream():
            update_activity_state("exhausted_rounds")
            self._set_status("Finishing...")
            self._append_response("\nAI: ")
            last_streamed = [""]

            def run_final():
                try:
                    def append_c(c):
                        q.put(("chunk", c))
                        last_streamed[0] += c

                    def append_t(t):
                        q.put(("thinking", t))

                    client.stream_chat_response(
                        self.session.messages, max_tokens, append_c, append_t,
                        stop_checker=lambda: self.stop_requested,
                    )
                    if self.stop_requested:
                        q.put(("stopped",))
                    else:
                        q.put(("stream_done", {"content": last_streamed[0]}))
                except Exception as e:
                    q.put(("error", e))

            threading.Thread(target=run_final, daemon=True).start()

        def process_stream_done(response):
            r = round_num[0]
            tool_calls = response.get("tool_calls")
            if isinstance(tool_calls, list) and len(tool_calls) == 0:
                tool_calls = None
            content = response.get("content")
            finish_reason = response.get("finish_reason")
            agent_log("chat_panel.py:tool_round", "Tool loop round response",
                      data={"round": r, "has_tool_calls": bool(tool_calls), "num_tool_calls": len(tool_calls) if tool_calls else 0}, hypothesis_id="A")
            if not tool_calls:
                agent_log("chat_panel.py:exit_no_tools", "Exiting loop: no tool_calls", data={"round": r}, hypothesis_id="A")
                if content:
                    debug_log("Tool loop: Adding assistant message to session", context="Chat")
                    self.session.add_assistant_message(content=content)
                    self._append_response("\n")
                elif finish_reason == "length":
                    self._append_response(
                        "\n[Response truncated -- the model ran out of tokens...]\n")
                elif finish_reason == "content_filter":
                    # (per LiteLLM)
                    self._append_response("\n[Content filter: response was truncated.]\n")
                else:
                    self._append_response("\n[No text from model; any tool changes were still applied.]\n")
                job_done[0] = True
                self._terminal_status = "Ready"
                self._set_status("Ready")
                return True
            self.session.add_assistant_message(content=content, tool_calls=tool_calls)
            if content:
                self._append_response("\n")
            for tc in tool_calls:
                if self.stop_requested:
                    break
                func_name = tc.get("function", {}).get("name", "unknown")
                func_args_str = tc.get("function", {}).get("arguments", "{}")
                call_id = tc.get("id", "")
                self._set_status("Running: %s" % func_name)
                update_activity_state("tool_execute", round_num=r, tool_name=func_name)
                try:
                    func_args = json.loads(func_args_str)
                except (json.JSONDecodeError, TypeError):
                    # Fallback: try Python literal eval for single-quoted JSON or Python dicts
                    try:
                        import ast
                        func_args = ast.literal_eval(func_args_str)
                        if not isinstance(func_args, dict):
                            func_args = {}
                    except Exception:
                        func_args = {}
                agent_log("chat_panel.py:tool_execute", "Executing tool", data={"tool": func_name, "round": r}, hypothesis_id="C,D,E")
                debug_log("Tool call: %s(%s)" % (func_name, func_args_str), context="Chat")
                
                # Pass a status callback so long-running tools (like image gen) can update the UI
                def tool_status_callback(msg):
                    # We can use _set_status directly because it's thread-safe (uses setText on peer)
                    # or at least it doesn't crash.
                    debug_log("tool_status_callback: %s" % msg, context="Chat")
                    self._set_status(msg)
                    
                # Check signature of execute_tool_fn to see if it accepts status_callback
                import inspect
                sig = inspect.signature(execute_tool_fn)
                
                # Fetch the current image model from the selector, if available
                image_model_override = self.image_model_selector.getText() if self.image_model_selector else None
                
                if "status_callback" in sig.parameters or "kwargs" in sig.parameters:
                    # Pass image_model_override if it's not None
                    if image_model_override:
                        func_args["image_model"] = image_model_override
                    result = execute_tool_fn(func_name, func_args, model, self.ctx, status_callback=tool_status_callback)
                else:
                    # Pass image_model_override if it's not None
                    if image_model_override:
                        func_args["image_model"] = image_model_override
                    result = execute_tool_fn(func_name, func_args, model, self.ctx)
                    
                debug_log("Tool result: %s" % result, context="Chat")
                try:
                    result_data = json.loads(result)
                    note = result_data.get("message", result_data.get("status", "done"))
                except Exception:
                    note = "done"
                self._append_response("[%s: %s]\n" % (func_name, note))
                # Prototype: when 0 replacements, show tool params in response for easier debugging
                if func_name == "apply_document_content" and (note or "").strip().startswith("Replaced 0 occurrence"):
                    params_display = func_args_str if len(func_args_str) <= 800 else func_args_str[:800] + "..."
                    self._append_response("[Debug: params %s]\n" % params_display)
                self.session.add_tool_result(call_id, result)
                
                # Yield to UI between tools
                try:
                    toolkit.processEvents()
                except Exception:
                    pass
            if not self.stop_requested:
                self._set_status("Sending results to AI...")
            round_num[0] += 1
            if round_num[0] >= max_tool_rounds:
                agent_log("chat_panel.py:exit_exhausted", "Exiting loop: exhausted max_tool_rounds", data={"rounds": max_tool_rounds}, hypothesis_id="A")
                start_final_stream()
            else:
                start_worker()
            return False

        try:
            toolkit = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx)
        except Exception as e:
            self._append_response("\n[Error: %s]\n" % str(e))
            self._terminal_status = "Error"
            self._set_status("Error")
            return

        start_worker()

        def apply_chunk(chunk_text, is_thinking=False):
            self._append_response(chunk_text)

        def on_stream_done(response):
            return process_stream_done(response)

        def on_stopped():
            self._terminal_status = "Stopped"
            self._set_status("Stopped")
            self._append_response("\n[Stopped by user]\n")

        def on_error(e):
            from core.api import format_error_message
            err_msg = format_error_message(e)
            self._append_response("\n[API error: %s]\n" % err_msg)
            self._terminal_status = "Error"
            self._set_status("Error")

        run_stream_drain_loop(
            q, toolkit, job_done, apply_chunk,
            on_stream_done=on_stream_done,
            on_stopped=on_stopped,
            on_error=on_error,
            ctx=self.ctx,
        )

    def _start_simple_stream_async(self, client, max_tokens, api_type):
        """Start simple streaming (no tools) via async helper; returns immediately."""
        debug_log("=== Simple stream START (api_type=%s) ===" % api_type, context="Chat")
        self._set_status("Waiting for model...")
        self._append_response("\nAI: ")

        last_user = ""
        doc_context = ""
        for msg in reversed(self.session.messages):
            if msg["role"] == "user" and not last_user:
                last_user = msg["content"]
            if msg["role"] == "system" and "[DOCUMENT CONTENT]" in (msg.get("content") or ""):
                doc_context = msg["content"]
        prompt = "%s\n\nUser question: %s" % (doc_context, last_user) if doc_context else last_user
        system_prompt = ""
        for msg in self.session.messages:
            if msg["role"] == "system" and "[DOCUMENT CONTENT]" not in (msg.get("content") or ""):
                system_prompt = msg["content"]
                break

        collected = []

        def apply_chunk(chunk_text, is_thinking=False):
            self._append_response(chunk_text)
            if not is_thinking:
                collected.append(chunk_text)

        def on_done():
            full_response = "".join(collected)
            self.session.add_assistant_message(content=full_response)
            self._terminal_status = "Ready"
            self._set_status("Ready")
            self._append_response("\n")
            if self.stop_requested:
                self._append_response("\n[Stopped by user]\n")

        def on_error(e):
            from core.api import format_error_message
            err_msg = format_error_message(e)
            self._append_response("[Error: %s]\n" % err_msg)
            self._terminal_status = "Error"
            self._set_status("Error")

        run_stream_completion_async(
            self.ctx, client, prompt, system_prompt, max_tokens, api_type,
            apply_chunk, on_done, on_error, on_status_fn=self._set_status,
            stop_checker=lambda: self.stop_requested,
        )

    def disposing(self, evt):
        try:
            from core.tool_bus import tool_bus
            tool_bus.unsubscribe(self._on_mcp_event)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# StopButtonListener - allows user to cancel the AI request
# ---------------------------------------------------------------------------

class StopButtonListener(unohelper.Base, XActionListener):
    """Listener for the Stop button - sets a flag in SendButtonListener to halt loops."""

    def __init__(self, send_listener):
        self.send_listener = send_listener

    def actionPerformed(self, evt):
        if self.send_listener:
            self.send_listener.stop_requested = True
            # Update status immediately
            self.send_listener._set_status("Stopping...")

    def disposing(self, evt):
        pass


# ---------------------------------------------------------------------------
# ClearButtonListener - resets the conversation
# ---------------------------------------------------------------------------

class ClearButtonListener(unohelper.Base, XActionListener):
    """Listener for the Clear button - resets conversation history."""

    def __init__(self, session, response_control, status_control):
        self.session = session
        self.response_control = response_control
        self.status_control = status_control

    def actionPerformed(self, evt):
        self.session.clear()
        if self.response_control and self.response_control.getModel():
            self.response_control.getModel().Text = ""
        if self.status_control:
            self.status_control.setText("")

    def disposing(self, evt):
        pass


# FIXME: Dynamic resizing of panel controls when sidebar is resized.
# The sidebar allocates a fixed height (from getHeightForWidth) and does not
# scroll, so a PanelResizeListener (XWindowListener) that repositions controls
# bottom-up would be the right approach.  However, the sidebar gives the panel
# window a very large initial height (1375px) before settling to the requested
# size, which causes controls to be positioned off-screen during the first
# layout pass.  Needs investigation into the sidebar's resize lifecycle.
# For now the XDL uses a compact fixed layout that works at the default size.


# ---------------------------------------------------------------------------
# ChatToolPanel, ChatPanelElement, ChatPanelFactory (sidebar plumbing)
# ---------------------------------------------------------------------------

class ChatToolPanel(unohelper.Base, XToolPanel, XSidebarPanel):
    """Holds the panel window; implements XToolPanel and XSidebarPanel."""

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
        debug_log("getHeightForWidth(width=%s)" % width, context="Chat")
        # Constrain panel to sidebar width (and parent height when available).
        if self.parent_window and self.PanelWindow and width > 0:
            parent_rect = self.parent_window.getPosSize()
            h = parent_rect.Height if parent_rect.Height > 0 else 280
            self.PanelWindow.setPosSize(0, 0, width, h, 15)
            debug_log("panel constrained to W=%s H=%s" % (width, h), context="Chat")
        # Min 280, preferred -1 (let sidebar decide), max 280 — matches working Git layout.
        return uno.createUnoStruct("com.sun.star.ui.LayoutSize", 280, -1, 280)

    def getMinimalWidth(self):
        return 180


class ChatPanelElement(unohelper.Base, XUIElement):
    """XUIElement wrapper; creates panel window in getRealInterface() via ContainerWindowProvider."""

    def __init__(self, ctx, frame, parent_window, resource_url):
        self.ctx = ctx
        self.xFrame = frame
        self.xParentWindow = parent_window
        self.ResourceURL = resource_url
        self.Frame = frame
        self.Type = TOOLPANEL
        self.toolpanel = None
        self.m_panelRootWindow = None
        self.session = None  # Created in _wireControls

    def getRealInterface(self):
        debug_log("=== getRealInterface called ===", context="Chat")
        if not self.toolpanel:
            try:
                # Ensure extension on path early so _wireControls imports work
                _ensure_extension_on_path(self.ctx)
                root_window = self._getOrCreatePanelRootWindow()
                debug_log("root_window created: %s" % (root_window is not None), context="Chat")
                self.toolpanel = ChatToolPanel(root_window, self.xParentWindow, self.ctx)
                self._wireControls(root_window)
                debug_log("getRealInterface completed successfully", context="Chat")
            except Exception as e:
                debug_log("getRealInterface ERROR: %s" % e, context="Chat")
                import traceback
                debug_log(traceback.format_exc(), context="Chat")
                raise
        return self.toolpanel

    def _getOrCreatePanelRootWindow(self):
        debug_log("_getOrCreatePanelRootWindow entered", context="Chat")
        pip = self.ctx.getValueByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation(EXTENSION_ID)
        dialog_url = base_url + "/" + XDL_PATH
        debug_log("dialog_url: %s" % dialog_url, context="Chat")
        provider = self.ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.ContainerWindowProvider", self.ctx)
        debug_log("calling createContainerWindow...", context="Chat")
        self.m_panelRootWindow = provider.createContainerWindow(
            dialog_url, "", self.xParentWindow, None)
        debug_log("createContainerWindow returned", context="Chat")
        # Sidebar does not show the panel content without this (framework does not make it visible).
        if self.m_panelRootWindow and hasattr(self.m_panelRootWindow, "setVisible"):
            self.m_panelRootWindow.setVisible(True)
        # Constrain panel only when parent already has size (layout may be 0x0 here).
        parent_rect = self.xParentWindow.getPosSize()
        if parent_rect.Width > 0 and parent_rect.Height > 0:
            self.m_panelRootWindow.setPosSize(
                0, 0, parent_rect.Width, parent_rect.Height, 15)
            debug_log("panel constrained to W=%s H=%s" % (
                parent_rect.Width, parent_rect.Height), context="Chat")
        return self.m_panelRootWindow

    def _refresh_controls_from_config(self):
        """Reload model and prompt selectors from config (e.g. after user changes Settings)."""
        root = self.m_panelRootWindow
        if not root or not hasattr(root, "getControl"):
            return
        from core.config import get_config, get_current_endpoint, populate_combobox_with_lru, get_text_model, get_image_model, populate_image_model_selector, set_config, set_image_model

        def get_optional(name):
            return get_optional_control(root, name)

        model_selector = get_optional("model_selector")
        prompt_selector = get_optional("prompt_selector")
        image_model_selector = get_optional("image_model_selector")
        
        current_model = get_text_model(self.ctx)
        extra_instructions = get_config(self.ctx, "additional_instructions", "")
        
        current_endpoint = get_current_endpoint(self.ctx)
        
        if model_selector:
            set_val = populate_combobox_with_lru(self.ctx, model_selector, current_model, "model_lru", current_endpoint, strict=True)
            if set_val != current_model:
                set_config(self.ctx, "text_model", set_val)
        if prompt_selector:
            populate_combobox_with_lru(self.ctx, prompt_selector, extra_instructions, "prompt_lru", "")
            
        # Refresh visual (image) model via shared helper; persist correction if strict replaced value
        if image_model_selector:
            current_image = get_image_model(self.ctx)
            set_image_val = populate_image_model_selector(self.ctx, image_model_selector)
            if set_image_val != current_image:
                set_image_model(self.ctx, set_image_val, update_lru=False)
        # Sync "Use Image model" checkbox from config (same write as Settings: setState first, else model.State)
        direct_image_check = get_optional("direct_image_check")
        if direct_image_check:
            try:
                direct_checked = get_config(self.ctx, "chat_direct_image", False)
                set_checkbox_state(direct_image_check, 1 if direct_checked else 0)
            except Exception:
                pass

    def _wireControls(self, root_window):
        """Attach listeners to Send and Clear buttons."""
        debug_log("_wireControls entered", context="Chat")
        if not hasattr(root_window, "getControl"):
            debug_log("_wireControls: root_window has no getControl, aborting", context="Chat")
            return

        # Get controls -- these must exist in the XDL
        send_btn = root_window.getControl("send")
        query_ctrl = root_window.getControl("query")
        response_ctrl = root_window.getControl("response")

        def get_optional(name):
            return get_optional_control(root_window, name)

        image_model_selector = get_optional("image_model_selector")
        prompt_selector = get_optional("prompt_selector")
        model_selector = get_optional("model_selector")
        model_label = get_optional("model_label")
        status_ctrl = get_optional("status")
        direct_image_check = get_optional("direct_image_check")
        aspect_ratio_selector = get_optional("aspect_ratio_selector")
        base_size_input = get_optional("base_size_input")
        base_size_label = get_optional("base_size_label")
        
        if status_ctrl:
             debug_log("_wireControls: got status control", context="Chat")
        else:
             debug_log("_wireControls: no status control in XDL (ok)", context="Chat")

        # Helper to show errors visibly in the response area
        def _show_init_error(msg):
            debug_log("_wireControls ERROR: %s" % msg, context="Chat")
            try:
                if response_ctrl and response_ctrl.getModel():
                    current = response_ctrl.getModel().Text or ""
                    response_ctrl.getModel().Text = current + "[Init error: %s]\n" % msg
            except Exception:
                pass

        # Ensure extension directory is on sys.path for cross-module imports
        _ensure_extension_on_path(self.ctx)

        try:
            # Read system prompt from config; use helper so Writer/Calc prompt matches document
            debug_log("_wireControls: importing core config...", context="Chat")
            from core.config import get_config, get_current_endpoint, get_text_model, get_image_model, populate_combobox_with_lru, populate_image_model_selector, set_image_model, set_config
            from core.constants import get_chat_system_prompt_for_document, DEFAULT_CHAT_SYSTEM_PROMPT
            from core.document import is_writer, is_calc, is_draw
            
            extra_instructions = get_config(self.ctx, "additional_instructions", "")
            current_model = get_text_model(self.ctx)
            current_endpoint = get_current_endpoint(self.ctx)
            
            # Model selector: strict so only current endpoint's models shown; persist correction if needed
            if model_selector:
                set_model_val = populate_combobox_with_lru(self.ctx, model_selector, current_model, "model_lru", current_endpoint, strict=True)
                if set_model_val != current_model:
                    set_config(self.ctx, "text_model", set_model_val)
            # Adaptive image model population via shared helper (uses strict for endpoint); persist correction if needed
            if image_model_selector:
                current_image = get_image_model(self.ctx)
                set_image_val = populate_image_model_selector(self.ctx, image_model_selector)
                if set_image_val != current_image:
                    set_image_model(self.ctx, set_image_val, update_lru=False)

            # Add real-time sync listeners to selectors
            if model_selector and hasattr(model_selector, "addItemListener"):
                class ModelSyncListener(unohelper.Base, XItemListener):
                    def __init__(self, ctx): self.ctx = ctx
                    def itemStateChanged(self, ev):
                        try:
                            txt = model_selector.getText()
                            if txt:
                                set_config(self.ctx, "text_model", txt)
                                # No LRU update here to avoid cluttering history from accidental clicks
                        except Exception: pass
                    def disposing(self, ev): pass
                model_selector.addItemListener(ModelSyncListener(self.ctx))

            if image_model_selector and hasattr(image_model_selector, "addItemListener"):
                class ImageModelSyncListener(unohelper.Base, XItemListener):
                    def __init__(self, ctx): self.ctx = ctx
                    def itemStateChanged(self, ev):
                        try:
                            txt = image_model_selector.getText()
                            if txt:
                                set_image_model(self.ctx, txt, update_lru=False)
                        except Exception: pass
                    def disposing(self, ev): pass
                image_model_selector.addItemListener(ImageModelSyncListener(self.ctx))

            # Initialize aspect ratio and base size
            if aspect_ratio_selector:
                aspect_ratio_selector.addItems(("Square", "Landscape (16:9)", "Portrait (9:16)", "Landscape (3:2)", "Portrait (2:3)"), 0)
                aspect_ratio_selector.setText(get_config(self.ctx, "image_default_aspect", "Square"))
            if base_size_input:
                populate_combobox_with_lru(self.ctx, base_size_input, str(get_config(self.ctx, "image_base_size", 512)), "image_base_size_lru", "")

            def update_base_size_label(aspect_str):
                if not base_size_label: return
                txt = "Size:"
                if "Landscape" in aspect_str: txt = "Height:"
                elif "Portrait" in aspect_str: txt = "Width:"
                if hasattr(base_size_label, "setText"):
                    base_size_label.setText(txt)
                elif hasattr(base_size_label.getModel(), "Label"):
                    base_size_label.getModel().Label = txt

            if aspect_ratio_selector:
                update_base_size_label(aspect_ratio_selector.getText())
                if hasattr(aspect_ratio_selector, "addItemListener"):
                    class AspectListener(unohelper.Base, XItemListener):
                        def itemStateChanged(self, ev):
                            try:
                                idx = getattr(ev, "Selected", -1)
                                if idx >= 0:
                                    update_base_size_label(aspect_ratio_selector.getItem(idx))
                            except Exception: pass
                        def disposing(self, ev): pass
                    aspect_ratio_selector.addItemListener(AspectListener())

            # Helper to toggle visibility
            def toggle_image_ui(is_image_mode):
                if model_label and hasattr(model_label, "setVisible"):
                    model_label.setVisible(not is_image_mode)
                if model_selector and hasattr(model_selector, "setVisible"):
                    model_selector.setVisible(not is_image_mode)
                
                if image_model_selector and hasattr(image_model_selector, "setVisible"):
                    image_model_selector.setVisible(is_image_mode)
                    
                if aspect_ratio_selector and hasattr(aspect_ratio_selector, "setVisible"):
                    aspect_ratio_selector.setVisible(is_image_mode)
                    
                if base_size_input and hasattr(base_size_input, "setVisible"):
                    base_size_input.setVisible(is_image_mode)
                if base_size_label and hasattr(base_size_label, "setVisible"):
                    base_size_label.setVisible(is_image_mode)

            # "Use Image model" checkbox
            if direct_image_check:
                try:
                    from core.config import set_config
                    direct_checked = get_config(self.ctx, "chat_direct_image", False)
                    set_checkbox_state(direct_image_check, 1 if direct_checked else 0)
                    toggle_image_ui(direct_checked)
                    if hasattr(direct_image_check, "addItemListener"):
                        class DirectImageCheckListener(unohelper.Base, XItemListener):
                            def __init__(self, ctx, toggle_cb):
                                self.ctx = ctx
                                self.toggle_cb = toggle_cb
                            def itemStateChanged(self, ev):
                                try:
                                    state = getattr(ev, "Selected", 0)
                                    is_checked = (state == 1)
                                    
                                    set_config(self.ctx, "chat_direct_image", is_checked)
                                    self.toggle_cb(is_checked)
                                except Exception as e:
                                    debug_log("Image checkbox listener error: %s" % e, context="Chat")
                            def disposing(self, ev):
                                pass
                        direct_image_check.addItemListener(DirectImageCheckListener(self.ctx, toggle_image_ui))
                except Exception as e:
                    debug_log("direct_image_check wire error: %s" % e, context="Chat")

            # Register for config changes (e.g. Settings dialog). Weakref so this panel can be
            # GC'd without unregistering; callback no-ops if panel is gone.
            from core.config import add_config_listener
            _self_ref = weakref.ref(self)
            def on_config_changed(ctx):
                panel = _self_ref()
                if panel is not None:
                    panel._refresh_controls_from_config()
            add_config_listener(on_config_changed)

            model = None
            if self.xFrame:
                try:
                    model = self.xFrame.getController().getModel()
                except Exception:
                    pass
            if model is None:
                try:
                    smgr = self.ctx.getServiceManager()
                    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
                    model = desktop.getCurrentComponent()
                except Exception:
                    pass
            if model and (is_writer(model) or is_calc(model) or is_draw(model)):
                system_prompt = get_chat_system_prompt_for_document(model, extra_instructions or "")
            else:
                system_prompt = (DEFAULT_CHAT_SYSTEM_PROMPT + "\n\n" + str(extra_instructions)) if extra_instructions else DEFAULT_CHAT_SYSTEM_PROMPT
            debug_log("_wireControls: config loaded", context="Chat")
        except Exception as e:
            import traceback
            _show_init_error("Config: %s" % e)
            debug_log(traceback.format_exc(), context="Chat")
            system_prompt = DEFAULT_SYSTEM_PROMPT_FALLBACK

        # Create session
        self.session = ChatSession(system_prompt)

        # Wire Send button
        try:
            stop_btn = root_window.getControl("stop")
            send_listener = SendButtonListener(
                self.ctx, self.xFrame,
                send_btn, stop_btn, query_ctrl, response_ctrl,
                image_model_selector, model_selector, status_ctrl, self.session,
                direct_image_checkbox=direct_image_check,
                aspect_ratio_selector=aspect_ratio_selector,
                base_size_input=base_size_input)

            # Detect and store initial document type for strict verification
            if model:
                from core.document import is_calc, is_draw, is_writer
                if is_calc(model):
                    send_listener.initial_doc_type = "Calc"
                elif is_draw(model):
                    send_listener.initial_doc_type = "Draw"
                elif is_writer(model):
                    send_listener.initial_doc_type = "Writer"
                else:
                    send_listener.initial_doc_type = "Unknown"
                debug_log("_wireControls: detected initial_doc_type=%s" % send_listener.initial_doc_type, context="Chat")

            send_btn.addActionListener(send_listener)
            debug_log("Send button wired", context="Chat")
            start_watchdog_thread(self.ctx, status_ctrl)

            if stop_btn:
                stop_btn.addActionListener(StopButtonListener(send_listener))
                debug_log("Stop button wired", context="Chat")
            # Initial state: Send enabled, Stop disabled (no AI running yet)
            send_listener._set_button_states(send_enabled=True, stop_enabled=False)
        except Exception as e:
            _show_init_error("Send/Stop button: %s" % e)

        # Show ready message
        try:
            if response_ctrl and response_ctrl.getModel():
                from core.constants import get_greeting_for_document
                greeting = get_greeting_for_document(model)
                response_ctrl.getModel().Text = "%s\n" % greeting
        except Exception:
            pass

        # Wire Clear button (may not exist in older XDL)
        try:
            clear_btn = root_window.getControl("clear")
            if clear_btn:
                clear_btn.addActionListener(ClearButtonListener(
                    self.session, response_ctrl, status_ctrl))
                debug_log("Clear button wired", context="Chat")
        except Exception:
            pass

        try:
            if status_ctrl and hasattr(status_ctrl, "setText"):
                status_ctrl.setText("Ready")
        except Exception:
            pass

        # Start MCP drain timer if server is running but timer was not started from main.
        # If timer fails (e.g. no 'com' in this context), we still drain on user interaction below.
        try:
            from main import try_ensure_mcp_timer
            try_ensure_mcp_timer(self.ctx)
        except Exception as e:
            debug_log("try_ensure_mcp_timer: %s" % e, context="Chat")

        # FIXME: Wire PanelResizeListener here once dynamic resizing is fixed.
        # See FIXME comment above the commented-out PanelResizeListener class.


class ChatPanelFactory(unohelper.Base, XUIElementFactory):
    """Factory that creates ChatPanelElement instances for the sidebar."""

    def __init__(self, ctx):
        self.ctx = ctx

    def createUIElement(self, resource_url, args):
        debug_log("createUIElement: %s" % resource_url, context="Chat")
        if "ChatPanel" not in resource_url:
            from com.sun.star.container import NoSuchElementException
            raise NoSuchElementException("Unknown resource: " + resource_url)

        frame = _get_arg(args, "Frame")
        parent_window = _get_arg(args, "ParentWindow")
        debug_log("ParentWindow: %s" % (parent_window is not None), context="Chat")
        if not parent_window:
            from com.sun.star.lang import IllegalArgumentException
            raise IllegalArgumentException("ParentWindow is required")

        return ChatPanelElement(self.ctx, frame, parent_window, resource_url)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ChatPanelFactory,
    "org.extension.localwriter.ChatPanelFactory",
    ("com.sun.star.ui.UIElementFactory",),
)

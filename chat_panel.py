# Chat with Document - Sidebar Panel implementation
# Follows the working pattern from LibreOffice's Python ToolPanel example:
# XUIElement wrapper creates panel in getRealInterface() via ContainerWindowProvider + XDL.

import os
import sys
import json
import queue
import threading
import uno
import unohelper

# Ensure extension directory is on path so core can be imported
_ext_dir = os.path.dirname(os.path.abspath(__file__))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)

from core.logging import agent_log, debug_log, update_activity_state, start_watchdog_thread
from core.async_stream import run_stream_completion_async

from com.sun.star.ui import XUIElementFactory, XUIElement, XToolPanel, XSidebarPanel
from com.sun.star.ui.UIElementType import TOOLPANEL
from com.sun.star.awt import XActionListener

# Extension ID from description.xml; XDL path inside the .oxt
EXTENSION_ID = "org.extension.localwriter"
XDL_PATH = "LocalWriterDialogs/ChatPanelDialog.xdl"

# Maximum tool-calling round-trips before giving up
MAX_TOOL_ROUNDS = 5

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
            debug_log(ctx, "Added extension path to sys.path: %s" % ext_path)
        else:
            debug_log(ctx, "Extension path already on sys.path: %s" % ext_path)
    except Exception as e:
        debug_log(ctx, "_ensure_extension_on_path ERROR: %s" % e)


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

    def __init__(self, ctx, frame, send_control, stop_control, query_control, response_control, prompt_selector, model_selector, status_control, session):
        self.ctx = ctx
        self.frame = frame
        self.send_control = send_control
        self.stop_control = stop_control
        self.query_control = query_control
        self.response_control = response_control
        self.prompt_selector = prompt_selector
        self.model_selector = model_selector
        self.status_control = status_control
        self.session = session
        self.stop_requested = False
        self._terminal_status = "Ready"
        self._send_busy = False

    def _set_status(self, text):
        """Update the status field in the sidebar (read-only TextField).
        Uses setText() (XTextComponent) to write directly to the control/peer,
        bypassing model→view notifications which can desync after document edits."""
        try:
            if self.status_control:
                self.status_control.setText(text)
            else:
                debug_log(self.ctx, "_set_status: NO CONTROL for '%s'" % text)
        except Exception as e:
            debug_log(self.ctx, "_set_status('%s') EXCEPTION: %s" % (text, e))

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
        if model and hasattr(model, "getText"):
            return model
        return None

    def _set_button_states(self, send_enabled, stop_enabled):
        """Set Send/Stop button enabled states. Per-control try/except so one failure cannot leave Send stuck disabled.
        Prefer model Enabled property (LibreOffice UNO); fallback to control.setEnable if available."""
        def set_control_enabled(control, enabled):
            if control is None:
                return
            val = bool(enabled)
            try:
                model = control.getModel()
                if model is not None and hasattr(model, "setPropertyValue"):
                    model.setPropertyValue("Enabled", val)
                    return
            except Exception as e1:
                debug_log(self.ctx, "_set_button_states (model) failed: %s" % e1)
            try:
                if hasattr(control, "setEnable"):
                    control.setEnable(val)
            except Exception as e2:
                debug_log(self.ctx, "_set_button_states (setEnable) failed: %s" % e2)
        set_control_enabled(self.send_control, send_enabled)
        set_control_enabled(self.stop_control, stop_enabled)

    def actionPerformed(self, evt):
        from core.logging import log_to_file
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
            debug_log(self.ctx, "SendButton error: %s\n%s" % (e, tb))
        finally:
            self._send_busy = False
            debug_log(self.ctx, "actionPerformed finally: resetting UI")
            self._set_status(self._terminal_status)
            self._set_button_states(send_enabled=True, stop_enabled=False)
            debug_log(self.ctx, "control returned to LibreOffice")
            update_activity_state("")  # clear phase so watchdog does not report after we return

    def _do_send(self):
        self._set_status("Starting...")
        update_activity_state("do_send")
        debug_log(self.ctx, "=== _do_send START ===")

        # Ensure extension directory is on sys.path
        _ensure_extension_on_path(self.ctx)

        try:
            debug_log(self.ctx, "_do_send: importing core modules...")
            from core.config import get_config, get_api_config, update_lru_history
            from core.api import LlmClient
            from core.document import get_document_context_for_chat
            from core.logging import log_to_file
            debug_log(self.ctx, "_do_send: core modules imported OK")
        except Exception as e:
            debug_log(self.ctx, "_do_send: core import FAILED: %s" % e)
            self._append_response("\n[Import error - core: %s]\n" % e)
            self._terminal_status = "Error"
            return

        try:
            debug_log(self.ctx, "_do_send: importing document_tools...")
            from core.document_tools import WRITER_TOOLS, execute_tool
            debug_log(self.ctx, "_do_send: document_tools imported OK (%d tools)" % len(WRITER_TOOLS))
        except Exception as e:
            debug_log(self.ctx, "_do_send: document_tools import FAILED: %s" % e)
            self._append_response("\n[Import error - document_tools: %s]\n" % e)
            self._terminal_status = "Error"
            return

        # 1. Get user query
        query_text = ""
        if self.query_control and self.query_control.getModel():
            query_text = (self.query_control.getModel().Text or "").strip()
        if not query_text:
            self._terminal_status = ""
            return

        # Clear the query field
        if self.query_control and self.query_control.getModel():
            self.query_control.getModel().Text = ""

        # Update system prompt from selector
        if self.prompt_selector:
            extra_instructions = self.prompt_selector.getText()
            from core.config import set_config
            from core.constants import DEFAULT_CHAT_SYSTEM_PROMPT
            set_config(self.ctx, "additional_instructions", extra_instructions)
            update_lru_history(self.ctx, extra_instructions, "prompt_lru")
            
            system_prompt = DEFAULT_CHAT_SYSTEM_PROMPT
            if extra_instructions:
                system_prompt += "\n\n" + str(extra_instructions)
            self.session.messages[0]["content"] = system_prompt

        # Update model from selector
        if self.model_selector:
            selected_model = self.model_selector.getText()
            if selected_model:
                from core.config import set_config
                set_config(self.ctx, "model", selected_model)
                update_lru_history(self.ctx, selected_model, "model_lru")
                debug_log(self.ctx, "_do_send: model updated to %s" % selected_model)

        # 2. Get document model
        self._set_status("Getting document...")
        debug_log(self.ctx, "_do_send: getting document model...")
        model = self._get_document_model()
        if not model:
            debug_log(self.ctx, "_do_send: no Writer document found")
            self._append_response("\n[No Writer document open.]\n")
            self._terminal_status = "Error"
            return
        debug_log(self.ctx, "_do_send: got document model OK")

        # 3. Set up config and LlmClient
        max_context = int(get_config(self.ctx, "chat_context_length", 8000))
        max_tokens = int(get_config(self.ctx, "chat_max_tokens", 16384))
        api_type = str(get_config(self.ctx, "api_type", "completions")).lower()
        debug_log(self.ctx, "_do_send: config loaded: api_type=%s, max_tokens=%d, max_context=%d" %
                    (api_type, max_tokens, max_context))

        # Determine if tool-calling is available (requires chat API)
        use_tools = (api_type == "chat")

        api_config = get_api_config(self.ctx)
        client = LlmClient(api_config, self.ctx)

        # 4. Refresh document context in session (start + end excerpts, inline selection/cursor markers)
        self._set_status("Reading document...")
        doc_text = get_document_context_for_chat(model, max_context, include_end=True, include_selection=True)
        debug_log(self.ctx, "_do_send: document context length=%d" % len(doc_text))
        agent_log("chat_panel.py:doc_context", "Document context for AI", data={"doc_length": len(doc_text), "doc_prefix_first_200": (doc_text or "")[:200], "max_context": max_context}, hypothesis_id="B")
        self.session.update_document_context(doc_text)

        # 5. Add user message to session and display
        self.session.add_user_message(query_text)
        self._append_response("\nYou: %s\n" % query_text)
        debug_log(self.ctx, "_do_send: user query='%s'" % query_text[:100])

        self._set_status("Connecting to AI (api_type=%s, tools=%s)..." % (api_type, use_tools))
        debug_log(self.ctx, "_do_send: calling AI, use_tools=%s, messages=%d" %
                    (use_tools, len(self.session.messages)))

        if use_tools:
            self._start_tool_calling_async(client, model, max_tokens, WRITER_TOOLS, execute_tool)
        else:
            self._start_simple_stream_async(client, max_tokens, api_type)

        log_to_file("=== _do_send END (async started) ===")
        debug_log(self.ctx, "=== _do_send END (async started) ===")

    # Future work: Undo grouping for AI edits (user can undo all edits from one turn with Ctrl+Z).
    # Previous attempt used enterUndoContext("AI Edit") / leaveUndoContext() but leaveUndoContext
    # was failing in some environments. Revisit when integrating with the async tool-calling path.

    def _start_tool_calling_async(self, client, model, max_tokens, tools, execute_tool_fn):
        """Tool-calling loop: worker thread + queue, main thread drains queue with processEventsToIdle (pure Python threading, no UNO Timer)."""
        from core.logging import log_to_file
        debug_log(self.ctx, "=== Tool-calling loop START (max %d rounds) ===" % MAX_TOOL_ROUNDS)
        self._append_response("\nAI: ")
        q = queue.Queue()
        round_num = [0]
        thinking_open = [False]
        job_done = [False]

        def start_worker():
            r = round_num[0]
            update_activity_state("tool_loop", round_num=r)
            debug_log(self.ctx, "Tool loop round %d: sending %d messages to API..." % (r, len(self.session.messages)))
            self._set_status("Waiting for model..." if r == 0 else "Connecting (round %d)..." % (r + 1))

            def run():
                try:
                    response = client.stream_request_with_tools(
                        self.session.messages, max_tokens, tools=tools,
                        append_callback=lambda t: q.put(("chunk", t)),
                        append_thinking_callback=lambda t: q.put(("thinking", t)),
                        stop_checker=lambda: self.stop_requested,
                        dispatch_events=False,
                    )
                    if self.stop_requested:
                        q.put(("stopped",))
                    else:
                        update_activity_state("tool_loop", round_num=r)
                        q.put(("stream_done", response))
                except Exception as e:
                    debug_log(self.ctx, "Tool loop round %d: API ERROR: %s" % (r, e))
                    q.put(("error", e))

            threading.Thread(target=run, daemon=True).start()

        def start_final_stream():
            update_activity_state("exhausted_rounds")
            self._set_status("Finishing...")
            self._append_response("\nAI: ")
            thinking_open[0] = False
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
                        dispatch_events=False,
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
                    log_to_file("Tool loop: Adding assistant message to session")
                    self.session.add_assistant_message(content=content)
                    self._append_response("\n")
                elif finish_reason == "length":
                    self._append_response(
                        "\n[Response truncated -- the model ran out of tokens...]\n")
                else:
                    self._append_response("\n[AI returned empty response]\n")
                job_done[0] = True
                self._terminal_status = "Ready"
                self._set_status("Ready")
                return
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
                debug_log(self.ctx, "Tool call: %s(%s)" % (func_name, func_args_str))
                result = execute_tool_fn(func_name, func_args, model, self.ctx)
                debug_log(self.ctx, "Tool result: %s" % result)
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
            if not self.stop_requested:
                self._set_status("Sending results to AI...")
            round_num[0] += 1
            if round_num[0] >= MAX_TOOL_ROUNDS:
                agent_log("chat_panel.py:exit_exhausted", "Exiting loop: exhausted MAX_TOOL_ROUNDS", data={"rounds": MAX_TOOL_ROUNDS}, hypothesis_id="A")
                start_final_stream()
            else:
                start_worker()

        try:
            toolkit = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx)
        except Exception as e:
            self._append_response("\n[Error: %s]\n" % str(e))
            self._terminal_status = "Error"
            self._set_status("Error")
            return

        start_worker()

        # Main-thread drain loop: queue + processEventsToIdle only (no UNO Timer)
        while not job_done[0]:
            items = []
            try:
                # Wait for at least one item or timeout
                items.append(q.get(timeout=0.05))
                # Drain all currently available items to batch updates
                try:
                    while True:
                        items.append(q.get_nowait())
                except queue.Empty:
                    pass
            except queue.Empty:
                toolkit.processEventsToIdle()
                continue

            try:
                current_chunks = []
                current_thinking = []

                def flush_buffers():
                    if current_thinking:
                        if not thinking_open[0]:
                            self._append_response("[Thinking] ")
                            thinking_open[0] = True
                        self._append_response("".join(current_thinking))
                        current_thinking.clear()
                    if current_chunks:
                        if thinking_open[0]:
                            self._append_response(" /thinking\n")
                            thinking_open[0] = False
                        self._append_response("".join(current_chunks))
                        current_chunks.clear()

                def close_thinking():
                    if thinking_open[0]:
                        self._append_response(" /thinking\n")
                        thinking_open[0] = False

                for item in items:
                    kind = item[0] if isinstance(item, tuple) else item
                    if kind == "chunk":
                        if current_thinking:
                            flush_buffers()
                        current_chunks.append(item[1])
                    elif kind == "thinking":
                        if current_chunks:
                            flush_buffers()
                        current_thinking.append(item[1])
                    elif kind == "stream_done":
                        flush_buffers()
                        close_thinking()
                        process_stream_done(item[1])
                    elif kind == "stopped":
                        flush_buffers()
                        close_thinking()
                        job_done[0] = True
                        self._terminal_status = "Stopped"
                        self._set_status("Stopped")
                        self._append_response("\n[Stopped by user]\n")
                        break
                    elif kind == "error":
                        flush_buffers()
                        close_thinking()
                        job_done[0] = True
                        self._append_response("\n[API error: %s]\n" % str(item[1]))
                        self._terminal_status = "Error"
                        self._set_status("Error")
                        break
                
                flush_buffers()

            except Exception as e:
                job_done[0] = True
                self._append_response("\n[Error: %s]\n" % str(e))
                self._terminal_status = "Error"
                self._set_status("Error")
            toolkit.processEventsToIdle()

    def _start_simple_stream_async(self, client, max_tokens, api_type):
        """Start simple streaming (no tools) via async helper; returns immediately."""
        debug_log(self.ctx, "=== Simple stream START (api_type=%s) ===" % api_type)
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
            self._append_response("[Error: %s]\n" % str(e))
            self._terminal_status = "Error"
            self._set_status("Error")

        run_stream_completion_async(
            self.ctx, client, prompt, system_prompt, max_tokens, api_type,
            apply_chunk, on_done, on_error, stop_checker=lambda: self.stop_requested,
        )

    def disposing(self, evt):
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
        debug_log(self.ctx, "getHeightForWidth(width=%s)" % width)
        # Constrain panel to sidebar width (and parent height when available).
        if self.parent_window and self.PanelWindow and width > 0:
            parent_rect = self.parent_window.getPosSize()
            h = parent_rect.Height if parent_rect.Height > 0 else 280
            self.PanelWindow.setPosSize(0, 0, width, h, 15)
            debug_log(self.ctx, "panel constrained to W=%s H=%s" % (width, h))
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
        debug_log(self.ctx, "=== getRealInterface called ===")
        if not self.toolpanel:
            try:
                # Ensure extension on path early so _wireControls imports work
                _ensure_extension_on_path(self.ctx)
                root_window = self._getOrCreatePanelRootWindow()
                debug_log(self.ctx, "root_window created: %s" % (root_window is not None))
                self.toolpanel = ChatToolPanel(root_window, self.xParentWindow, self.ctx)
                self._wireControls(root_window)
                debug_log(self.ctx, "getRealInterface completed successfully")
            except Exception as e:
                debug_log(self.ctx, "getRealInterface ERROR: %s" % e)
                import traceback
                debug_log(self.ctx, traceback.format_exc())
                raise
        return self.toolpanel

    def _getOrCreatePanelRootWindow(self):
        debug_log(self.ctx, "_getOrCreatePanelRootWindow entered")
        pip = self.ctx.getValueByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation(EXTENSION_ID)
        dialog_url = base_url + "/" + XDL_PATH
        debug_log(self.ctx, "dialog_url: %s" % dialog_url)
        provider = self.ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.ContainerWindowProvider", self.ctx)
        debug_log(self.ctx, "calling createContainerWindow...")
        self.m_panelRootWindow = provider.createContainerWindow(
            dialog_url, "", self.xParentWindow, None)
        debug_log(self.ctx, "createContainerWindow returned")
        # Sidebar does not show the panel content without this (framework does not make it visible).
        if self.m_panelRootWindow and hasattr(self.m_panelRootWindow, "setVisible"):
            self.m_panelRootWindow.setVisible(True)
        # Constrain panel only when parent already has size (layout may be 0x0 here).
        parent_rect = self.xParentWindow.getPosSize()
        if parent_rect.Width > 0 and parent_rect.Height > 0:
            self.m_panelRootWindow.setPosSize(
                0, 0, parent_rect.Width, parent_rect.Height, 15)
            debug_log(self.ctx, "panel constrained to W=%s H=%s" % (
                parent_rect.Width, parent_rect.Height))
        return self.m_panelRootWindow

    def _wireControls(self, root_window):
        """Attach listeners to Send and Clear buttons."""
        debug_log(self.ctx, "_wireControls entered")
        if not hasattr(root_window, "getControl"):
            debug_log(self.ctx, "_wireControls: root_window has no getControl, aborting")
            return

        # Get controls -- these must exist in the XDL
        send_btn = root_window.getControl("send")
        query_ctrl = root_window.getControl("query")
        response_ctrl = root_window.getControl("response")
        prompt_selector = None
        model_selector = None
        try:
            prompt_selector = root_window.getControl("prompt_selector")
        except Exception:
            pass
        try:
            model_selector = root_window.getControl("model_selector")
        except Exception:
            pass
        debug_log(self.ctx, "_wireControls: got send/query/response/prompt/model controls")

        # Status label (may not exist in older XDL)
        status_ctrl = None
        try:
            status_ctrl = root_window.getControl("status")
            debug_log(self.ctx, "_wireControls: got status control")
        except Exception:
            debug_log(self.ctx, "_wireControls: no status control in XDL (ok)")

        # Helper to show errors visibly in the response area
        def _show_init_error(msg):
            debug_log(self.ctx, "_wireControls ERROR: %s" % msg)
            try:
                if response_ctrl and response_ctrl.getModel():
                    current = response_ctrl.getModel().Text or ""
                    response_ctrl.getModel().Text = current + "[Init error: %s]\n" % msg
            except Exception:
                pass

        # Ensure extension directory is on sys.path for cross-module imports
        _ensure_extension_on_path(self.ctx)

        try:
            # Read system prompt from config
            debug_log(self.ctx, "_wireControls: importing core config...")
            from core.config import get_config, populate_combobox_with_lru
            from core.constants import DEFAULT_CHAT_SYSTEM_PROMPT
            extra_instructions = get_config(self.ctx, "additional_instructions", "")
            current_model = get_config(self.ctx, "model", "")
            
            if prompt_selector:
                populate_combobox_with_lru(self.ctx, prompt_selector, extra_instructions, "prompt_lru")
            
            if model_selector:
                populate_combobox_with_lru(self.ctx, model_selector, current_model, "model_lru")

            system_prompt = DEFAULT_CHAT_SYSTEM_PROMPT
            if extra_instructions:
                system_prompt += "\n\n" + str(extra_instructions)
            debug_log(self.ctx, "_wireControls: config loaded")
        except Exception as e:
            import traceback
            _show_init_error("Config: %s" % e)
            debug_log(self.ctx, traceback.format_exc())
            system_prompt = DEFAULT_SYSTEM_PROMPT_FALLBACK

        # Create session
        self.session = ChatSession(system_prompt)

        # Wire Send button
        try:
            stop_btn = root_window.getControl("stop")
            send_listener = SendButtonListener(
                self.ctx, self.xFrame, send_btn, stop_btn, query_ctrl, response_ctrl,
                prompt_selector, model_selector, status_ctrl, self.session)
            send_btn.addActionListener(send_listener)
            debug_log(self.ctx, "Send button wired")
            start_watchdog_thread(self.ctx, status_ctrl)

            if stop_btn:
                stop_btn.addActionListener(StopButtonListener(send_listener))
                debug_log(self.ctx, "Stop button wired")
            # Initial state: Send enabled, Stop disabled (no AI running yet)
            send_listener._set_button_states(send_enabled=True, stop_enabled=False)
        except Exception as e:
            _show_init_error("Send/Stop button: %s" % e)

        # Show ready message
        try:
            if response_ctrl and response_ctrl.getModel():
                response_ctrl.getModel().Text = "I can edit or translate your document instantly. Try me!\n"
        except Exception:
            pass

        # Wire Clear button (may not exist in older XDL)
        try:
            clear_btn = root_window.getControl("clear")
            if clear_btn:
                clear_btn.addActionListener(ClearButtonListener(
                    self.session, response_ctrl, status_ctrl))
                debug_log(self.ctx, "Clear button wired")
        except Exception:
            pass

        try:
            if status_ctrl and hasattr(status_ctrl, "setText"):
                status_ctrl.setText("Ready")
        except Exception:
            pass

        # FIXME: Wire PanelResizeListener here once dynamic resizing is fixed.
        # See FIXME comment above the commented-out PanelResizeListener class.


class ChatPanelFactory(unohelper.Base, XUIElementFactory):
    """Factory that creates ChatPanelElement instances for the sidebar."""

    def __init__(self, ctx):
        self.ctx = ctx

    def createUIElement(self, resource_url, args):
        debug_log(self.ctx, "createUIElement: %s" % resource_url)
        if "ChatPanel" not in resource_url:
            from com.sun.star.container import NoSuchElementException
            raise NoSuchElementException("Unknown resource: " + resource_url)

        frame = _get_arg(args, "Frame")
        parent_window = _get_arg(args, "ParentWindow")
        debug_log(self.ctx, "ParentWindow: %s" % (parent_window is not None))
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

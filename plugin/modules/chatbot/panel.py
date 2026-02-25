"""Chat sidebar panel for LibreOffice.

Provides the ChatSession class and the SendButtonListener that drives
the streaming tool-calling loop. The actual UNO UI element factory
and XDL wiring live in main.py (or a dedicated panel_factory module).
"""

import json
import logging
import queue
import threading

log = logging.getLogger("localwriter.chatbot.panel")

# Default max tool rounds when not in config
DEFAULT_MAX_TOOL_ROUNDS = 15


# ── Chat session ──────────────────────────────────────────────────────


class ChatSession:
    """Maintains the message history for one sidebar chat session."""

    def __init__(self, system_prompt=None):
        self.messages = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content=None, tool_calls=None):
        msg = {"role": "assistant", "content": content}
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
        """Update or insert the document context as a system message."""
        context_marker = "[DOCUMENT CONTENT]"
        context_msg = "%s\n%s\n[END DOCUMENT]" % (context_marker, doc_text)

        for i, msg in enumerate(self.messages):
            if msg["role"] == "system" and context_marker in (msg.get("content") or ""):
                self.messages[i]["content"] = context_msg
                return
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


# ── Chat tool adapter ─────────────────────────────────────────────────


class ChatToolAdapter:
    """Routes chat panel tool calls through the ToolRegistry.

    Usage:
        adapter = ChatToolAdapter(tool_registry, service_registry)
        tools = adapter.get_tools_for_doc(doc)
        result = adapter.execute_tool(tool_name, args, doc, ctx)
    """

    def __init__(self, tool_registry, service_registry):
        self.tool_registry = tool_registry
        self.service_registry = service_registry

    def get_tools_for_doc(self, doc):
        """Return OpenAI function-calling schemas for the active document."""
        try:
            doc_svc = self.service_registry.document
            if doc_svc and doc:
                doc_type = doc_svc.detect_doc_type(doc)
            else:
                doc_type = None
        except Exception:
            doc_type = None
        return self.tool_registry.get_openai_schemas(doc_type)

    def execute_tool(self, tool_name, arguments, doc, ctx,
                     status_callback=None, doc_type=None):
        """Execute a tool and return the result dict."""
        from plugin.framework.tool_context import ToolContext

        if doc_type is None:
            try:
                doc_svc = self.service_registry.document
                doc_type = doc_svc.detect_doc_type(doc) if doc else "writer"
            except Exception:
                doc_type = "writer"

        context = ToolContext(
            doc=doc,
            ctx=ctx,
            doc_type=doc_type,
            services=self.service_registry,
            caller="chatbot",
        )

        result = self.tool_registry.execute(tool_name, context, **arguments)
        return result

    def execute_tool_json(self, tool_name, arguments, doc, ctx,
                          status_callback=None, doc_type=None):
        """Execute a tool and return JSON string (legacy compat)."""
        result = self.execute_tool(
            tool_name, arguments, doc, ctx,
            status_callback=status_callback, doc_type=doc_type)
        return json.dumps(result, ensure_ascii=False, default=str)


# ── Send button listener ──────────────────────────────────────────────


class SendButtonListener:
    """Listener for the Send button — drives streaming + tool-calling loop.

    This is a simplified version that works with the framework services.
    The actual UNO XActionListener wiring happens in the panel factory.
    """

    def __init__(self, services, session, adapter):
        self._services = services
        self._session = session
        self._adapter = adapter
        self.stop_requested = False
        self._busy = False

        # UI callbacks (set by panel factory)
        self.on_status = None
        self.on_append_response = None
        self.on_set_buttons = None
        self.on_done = None

    def send(self, user_text, doc, ctx):
        """Process a user message with streaming and tool-calling."""
        if self._busy:
            return
        self._busy = True
        self.stop_requested = False

        try:
            self._do_send(user_text, doc, ctx)
        except Exception:
            log.exception("send() failed")
        finally:
            self._busy = False

    def _do_send(self, user_text, doc, ctx):
        from plugin.modules.chatbot.streaming import accumulate_delta

        config = self._services.config.proxy_for("chatbot")
        max_rounds = config.get("max_tool_rounds") or DEFAULT_MAX_TOOL_ROUNDS

        # Get the LLM provider
        try:
            provider = self._services.ai.get_provider("text")
        except RuntimeError:
            self._set_status("No LLM provider configured")
            return

        # Get tools for current doc
        tools = self._adapter.get_tools_for_doc(doc)

        # Add user message
        self._session.add_user_message(user_text)

        for _round in range(max_rounds):
            if self.stop_requested:
                self._set_status("Stopped")
                break

            # Stream response
            acc = {}
            content_parts = []

            try:
                for chunk in provider.stream(
                    self._session.messages, tools=tools
                ):
                    if self.stop_requested:
                        break
                    text = chunk.get("content", "")
                    thinking = chunk.get("thinking", "")
                    delta = chunk.get("delta", {})
                    if thinking and self.on_append_response:
                        self.on_append_response(thinking, is_thinking=True)
                    if text:
                        content_parts.append(text)
                        if self.on_append_response:
                            self.on_append_response(text, is_thinking=False)
                    if delta:
                        acc = accumulate_delta(acc, delta)
            except Exception as e:
                self._set_status("Error: %s" % e)
                break

            if self.stop_requested:
                break

            # Check for tool calls
            tool_calls = acc.get("tool_calls")
            content = "".join(content_parts)

            if not tool_calls:
                # No tool calls — conversation turn complete
                self._session.add_assistant_message(content=content)
                break

            # Process tool calls
            self._session.add_assistant_message(
                content=content or None, tool_calls=tool_calls)

            for tc in tool_calls:
                if self.stop_requested:
                    break
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}

                self._set_status("Tool: %s" % name)
                if self.on_append_response:
                    self.on_append_response(
                        "\n[Tool: %s]\n" % name, is_thinking=False)

                result = self._adapter.execute_tool(
                    name, args, doc, ctx)
                result_str = json.dumps(
                    result, ensure_ascii=False, default=str)

                self._session.add_tool_result(
                    tc.get("id", ""), result_str)

            # Continue loop for next round of tool calls

        self._set_status("Ready")
        if self.on_done:
            self.on_done()

    def _set_status(self, text):
        if self.on_status:
            try:
                self.on_status(text)
            except Exception:
                pass

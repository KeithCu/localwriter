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

# Lazy tool injection: marker the LLM outputs when it needs tools
_TOOLS_MARKER = "<<<TOOLS>>>"
_TOOLS_HINT = (
    "No tools are loaded for this turn. "
    "If you need to call tools/functions to fulfill the user's request, "
    "respond with exactly: %s\n"
    "Otherwise, answer the user normally."
) % _TOOLS_MARKER


# ── Chat session ──────────────────────────────────────────────────────


class ChatSession:
    """Maintains the message history for one sidebar chat session.

    Supports cumulative summarization: when total message size exceeds
    *max_history_chars*, older turns are compressed into a running
    summary that preserves conversation context without consuming
    the entire LLM context window.
    """

    # Threshold to trigger compression (chars across all messages)
    MAX_HISTORY_CHARS = 24000
    # Keep this many recent messages untouched
    KEEP_RECENT = 6

    def __init__(self, system_prompt=None):
        self.messages = []
        self._summary = ""  # cumulative conversation summary
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

    def maybe_compress(self):
        """Compress older messages into a summary if history is too long.

        Keeps system messages and recent turns intact. Replaces older
        user/assistant/tool messages with a summary system message.
        """
        total = sum(len(m.get("content") or "") for m in self.messages)
        if total < self.MAX_HISTORY_CHARS:
            return

        # Separate system messages from conversation messages
        system_msgs = []
        conv_msgs = []
        for msg in self.messages:
            if msg["role"] == "system":
                system_msgs.append(msg)
            else:
                conv_msgs.append(msg)

        if len(conv_msgs) <= self.KEEP_RECENT:
            return

        # Split: older messages to summarize, recent to keep
        to_compress = conv_msgs[:-self.KEEP_RECENT]
        to_keep = conv_msgs[-self.KEEP_RECENT:]

        # Build summary from older messages
        new_summary = self._build_summary(to_compress)

        # Reconstruct messages: system + summary + recent
        self.messages = list(system_msgs)
        if new_summary:
            self._summary = new_summary
            summary_marker = "[CONVERSATION SUMMARY]"
            summary_msg = "%s\n%s\n[/SUMMARY]" % (summary_marker, new_summary)
            # Remove any existing summary message
            self.messages = [
                m for m in self.messages
                if not (m["role"] == "system"
                        and "[CONVERSATION SUMMARY]" in (m.get("content") or ""))
            ]
            self.messages.append({"role": "system", "content": summary_msg})
        self.messages.extend(to_keep)

    def _build_summary(self, messages):
        """Build a concise summary from a list of conversation messages."""
        parts = []
        if self._summary:
            parts.append(self._summary)

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content") or ""
            if role == "user" and content:
                # Keep user queries in full (they're usually short)
                parts.append("User: %s" % content[:300])
            elif role == "assistant" and content:
                # Summarize assistant responses
                preview = content[:200]
                if len(content) > 200:
                    preview += "..."
                parts.append("Assistant: %s" % preview)
            elif role == "tool":
                # Just note that a tool was called
                parts.append("(tool result)")
            # Skip tool_calls details in summary

        return "\n".join(parts)

    def clear(self):
        """Reset to just the system prompt."""
        system = None
        for msg in self.messages:
            if msg["role"] == "system" and "[DOCUMENT CONTENT]" not in (msg.get("content") or ""):
                if "[CONVERSATION SUMMARY]" in (msg.get("content") or ""):
                    continue
                system = msg
                break
        self.messages = []
        self._summary = ""
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
        doc_type = self._detect_doc_type(doc)
        return self.tool_registry.get_openai_schemas(doc_type)

    def get_brokered_tools(self, doc, broker):
        """Return core tools + extras activated via the tool broker."""
        doc_type = self._detect_doc_type(doc)
        schemas = self.tool_registry.get_openai_schemas(doc_type, tier="core")
        if broker.get("extra_names"):
            schemas += self.tool_registry.get_openai_schemas_by_names(
                broker["extra_names"])
        return schemas

    def _detect_doc_type(self, doc):
        """Return the doc_type string for *doc*, or None."""
        try:
            doc_svc = self.service_registry.document
            if doc_svc and doc:
                return doc_svc.detect_doc_type(doc)
        except Exception:
            pass
        return None

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
        self.instance_id = ""  # set by panel instance selector

        # UI callbacks (set by panel factory)
        self.on_status = None
        self.on_append_response = None
        self.on_set_buttons = None
        self.on_done = None

    def send(self, user_text, doc, ctx, use_tools=True):
        """Process a user message with streaming and tool-calling."""
        if self._busy:
            return
        self._busy = True
        self.stop_requested = False

        try:
            self._do_send(user_text, doc, ctx, use_tools=use_tools)
        except Exception:
            log.exception("send() failed")
        finally:
            self._busy = False

    def _do_send(self, user_text, doc, ctx, use_tools=True):
        from plugin.modules.chatbot.streaming import chat_event_stream

        config = self._services.config.proxy_for("chatbot")
        max_rounds = config.get("max_tool_rounds") or DEFAULT_MAX_TOOL_ROUNDS
        use_broker = config.get("tool_broker") or False
        broker = {"extra_names": set()} if use_broker else None

        # Get the LLM provider (use panel instance selector or fallback)
        try:
            provider = self._services.ai.get_provider(
                "text", instance_id=self.instance_id or None)
        except RuntimeError:
            self._set_status("No LLM provider configured")
            return

        # Inject document context
        if doc:
            from plugin.modules.chatbot.context import build_context
            strategy = config.get("context_strategy") or "auto"
            doc_context = build_context(
                doc, self._services, strategy=strategy)
            if doc_context:
                self._session.update_document_context(doc_context)

        # Compress history if too long
        self._session.maybe_compress()

        # Add user message
        self._session.add_user_message(user_text)

        if use_tools == "lazy":
            needs_tools = self._lazy_probe(provider, doc, ctx)
            if needs_tools:
                self._set_status("Loading tools...")
                use_tools = True
            else:
                self._set_status("Ready")
                if self.on_done:
                    self.on_done()
                return

        # Chat mode: no tools → fast pure-text response
        active_adapter = self._adapter if use_tools else None
        active_broker = broker if use_tools else None

        for event in chat_event_stream(
            provider, self._session, active_adapter, doc, ctx,
            max_rounds=max_rounds,
            stop_checker=lambda: self.stop_requested,
            broker=active_broker,
        ):
            etype = event.get("type")
            if etype == "text":
                if self.on_append_response:
                    self.on_append_response(
                        event["content"], is_thinking=False)
            elif etype == "thinking":
                if self.on_append_response:
                    self.on_append_response(
                        event["content"], is_thinking=True)
            elif etype == "tool_call":
                if self.on_append_response:
                    self.on_append_response(
                        "\n[Tool: %s]\n" % event["name"],
                        is_thinking=False)
            elif etype == "status":
                self._set_status(event["message"])
            elif etype == "error":
                self._set_status("Error: %s" % event["message"])
                break
            elif etype == "done":
                break

        self._set_status("Ready")
        if self.on_done:
            self.on_done()

    def _lazy_probe(self, provider, doc, ctx):
        """Probe without tools; return True if the LLM needs them."""
        from plugin.modules.chatbot.streaming import chat_event_stream

        hint_msg = {"role": "system", "content": _TOOLS_HINT}
        self._session.messages.append(hint_msg)

        response_text = ""
        for event in chat_event_stream(
            provider, self._session, None, doc, ctx,
            max_rounds=1,
            stop_checker=lambda: self.stop_requested,
        ):
            etype = event.get("type")
            if etype == "text":
                response_text += event["content"]
                if _TOOLS_MARKER in response_text:
                    break
            elif etype in ("done", "error"):
                break

        # Remove hint from session
        try:
            self._session.messages.remove(hint_msg)
        except ValueError:
            pass

        if _TOOLS_MARKER in response_text:
            # Remove marker assistant response if it was added
            while (self._session.messages
                   and self._session.messages[-1]["role"] == "assistant"):
                self._session.messages.pop()
            return True

        # Chat response is fine — push to UI
        if response_text and self.on_append_response:
            self.on_append_response(response_text, is_thinking=False)
        return False

    def _set_status(self, text):
        if self.on_status:
            try:
                self.on_status(text)
            except Exception:
                pass

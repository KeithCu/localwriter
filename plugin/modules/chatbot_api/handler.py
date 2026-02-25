"""HTTP handler for the chatbot REST/SSE API.

Endpoints:
  POST /api/chat       — send message, stream SSE response
  GET  /api/chat       — get chat history
  DELETE /api/chat     — reset session
  GET  /api/providers  — list AI providers/instances
"""

import json
import logging

log = logging.getLogger("localwriter.chatbot_api.handler")


class ChatApiHandler:
    """Stateful handler that manages a ChatSession over HTTP."""

    def __init__(self, services):
        self._services = services
        self._session = None
        self._adapter = None
        self._init_session()

    def _init_session(self):
        """Create a fresh ChatSession and ChatToolAdapter."""
        from plugin.modules.chatbot.panel import ChatSession, ChatToolAdapter

        system_prompt = ""
        try:
            doc_svc = self._services.document
            doc = doc_svc.get_active_document() if doc_svc else None
            doc_type = doc_svc.detect_doc_type(doc) if doc and doc_svc else "writer"
        except Exception:
            doc_type = "writer"

        try:
            from plugin.modules.chatbot.constants import get_system_prompt
            cfg = self._services.config.proxy_for("chatbot")
            extra = cfg.get("system_prompt") or ""
            system_prompt = get_system_prompt(doc_type, extra)
        except Exception:
            pass

        self._session = ChatSession(system_prompt)

        tools = self._services.get("tools")
        if tools:
            self._adapter = ChatToolAdapter(tools, self._services)

    def _check_auth(self, handler):
        """Check Bearer token auth. Returns True if OK, sends 401 if not."""
        cfg = self._services.config.proxy_for("chatbot_api")
        token = cfg.get("auth_token") or ""
        if not token:
            return True

        auth = handler.headers.get("Authorization", "")
        if auth == "Bearer %s" % token:
            return True

        handler.send_response(401)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(
            json.dumps({"error": "Unauthorized"}).encode("utf-8"))
        return False

    def _check_auth_simple(self, body, headers, query):
        """Check auth for simple (non-raw) handlers. Returns error tuple or None."""
        cfg = self._services.config.proxy_for("chatbot_api")
        token = cfg.get("auth_token") or ""
        if not token:
            return None
        auth = (headers or {}).get("Authorization", "")
        if auth == "Bearer %s" % token:
            return None
        return (401, {"error": "Unauthorized"})

    # ── POST /api/chat — stream SSE response ──────────────────────────

    def handle_chat(self, handler):
        """Handle POST /api/chat with SSE streaming."""
        if not self._check_auth(handler):
            return

        try:
            length = int(handler.headers.get("Content-Length", 0))
            body = json.loads(handler.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            handler.send_response(400)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(
                json.dumps({"error": "Invalid JSON body"}).encode("utf-8"))
            return

        message = body.get("message", "").strip()
        if not message:
            handler.send_response(400)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(
                json.dumps({"error": "Missing 'message' field"}).encode("utf-8"))
            return

        instance_id = body.get("instance_id", "")

        # Get provider
        try:
            provider = self._services.ai.get_provider(
                "text", instance_id=instance_id or None)
        except RuntimeError as e:
            handler.send_response(503)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(
                json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Inject document context
        try:
            doc_svc = self._services.document
            doc = doc_svc.get_active_document() if doc_svc else None
            if doc:
                from plugin.modules.chatbot.context import build_context
                cfg = self._services.config.proxy_for("chatbot")
                strategy = cfg.get("context_strategy") or "auto"
                ctx_text = build_context(doc, self._services, strategy=strategy)
                if ctx_text:
                    self._session.update_document_context(ctx_text)
        except Exception:
            log.debug("Failed to inject document context", exc_info=True)

        # Compress if needed
        self._session.maybe_compress()

        # Add user message
        self._session.add_user_message(message)

        # Start SSE stream
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()

        def send_event(event_type, data):
            line = "event: %s\ndata: %s\n\n" % (
                event_type, json.dumps(data, ensure_ascii=False))
            try:
                handler.wfile.write(line.encode("utf-8"))
                handler.wfile.flush()
            except Exception:
                raise ConnectionError("Client disconnected")

        try:
            self._stream_response(
                provider, send_event, body.get("tools", True))
        except ConnectionError:
            log.debug("Client disconnected during streaming")
        except Exception:
            log.exception("Streaming failed")
            try:
                send_event("error", {"message": "Internal server error"})
            except Exception:
                pass

    def _stream_response(self, provider, send_event, use_tools):
        """Run the streaming + tool-calling loop, emitting SSE events."""
        from plugin.modules.chatbot.streaming import accumulate_delta

        config = self._services.config.proxy_for("chatbot")
        max_rounds = config.get("max_tool_rounds") or 15

        tools = None
        if use_tools and self._adapter:
            try:
                doc_svc = self._services.document
                doc = doc_svc.get_active_document() if doc_svc else None
                tools = self._adapter.get_tools_for_doc(doc)
            except Exception:
                pass

        for _round in range(max_rounds):
            acc = {}
            content_parts = []

            for chunk in provider.stream(
                    self._session.messages, tools=tools):
                text = chunk.get("content", "")
                thinking = chunk.get("thinking", "")
                delta = chunk.get("delta", {})

                if thinking:
                    send_event("thinking", {"text": thinking})
                if text:
                    content_parts.append(text)
                    send_event("text", {"text": text})
                if delta:
                    acc = accumulate_delta(acc, delta)

            tool_calls = acc.get("tool_calls")
            content = "".join(content_parts)

            if not tool_calls:
                self._session.add_assistant_message(content=content)
                send_event("done", {"content": content})
                return

            # Process tool calls
            self._session.add_assistant_message(
                content=content or None, tool_calls=tool_calls)

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}

                send_event("tool_call", {
                    "name": name, "arguments": args})

                if self._adapter:
                    from plugin.framework.uno_context import get_ctx
                    doc_svc = self._services.document
                    doc = doc_svc.get_active_document() if doc_svc else None
                    ctx = get_ctx()
                    result = self._adapter.execute_tool(
                        name, args, doc, ctx)
                    result_str = json.dumps(
                        result, ensure_ascii=False, default=str)
                    self._session.add_tool_result(
                        tc.get("id", ""), result_str)
                    send_event("tool_result", {
                        "name": name, "result": result})

        send_event("done", {"content": content})

    # ── GET /api/chat — history ───────────────────────────────────────

    def handle_history(self, body, headers, query):
        """Return the current chat history."""
        err = self._check_auth_simple(body, headers, query)
        if err:
            return err
        messages = []
        for msg in self._session.messages:
            if msg["role"] == "system":
                continue
            messages.append({
                "role": msg["role"],
                "content": msg.get("content", ""),
            })
        return (200, {"messages": messages})

    # ── DELETE /api/chat — reset ──────────────────────────────────────

    def handle_reset(self, body, headers, query):
        """Reset the chat session."""
        err = self._check_auth_simple(body, headers, query)
        if err:
            return err
        self._init_session()
        return (200, {"status": "ok"})

    # ── GET /api/providers — list instances ───────────────────────────

    def handle_providers(self, body, headers, query):
        """List available AI providers and instances."""
        err = self._check_auth_simple(body, headers, query)
        if err:
            return err
        ai = self._services.get("ai")
        if not ai:
            return (200, {"providers": []})

        providers = []
        for iid, inst in ai._instances.items():
            providers.append({
                "id": iid,
                "name": inst.name,
                "module": inst.module_name,
                "capabilities": sorted(inst.capabilities),
            })
        return (200, {"providers": providers})

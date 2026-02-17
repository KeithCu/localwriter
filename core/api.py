"""
LLM API client for LocalWriter.
Takes a config dict (from core.config.get_api_config) and UNO ctx.
"""
import json
import ssl
import urllib.request

# accumulate_delta is required for tool-calling: it merges streaming deltas into message_snapshot so full tool_calls (with function.arguments) are available.
from .streaming_deltas import accumulate_delta

from core.logging import debug_log, update_activity_state, init_logging


def format_error_message(e):
    """Map common exceptions to user-friendly advice."""
    import socket
    import urllib.error

    msg = str(e)
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 401:
            return "Invalid API Key. Please check your settings."
        if e.code == 403:
            return "API access Forbidden. Your key may lack permissions for this model."
        if e.code == 404:
            return "Endpoint not found (404). Check your URL and Model name."
        if e.code >= 500:
            return "Server error (%d). The AI provider is having issues." % e.code
        return "HTTP Error %d: %s" % (e.code, e.reason)

    if isinstance(e, urllib.error.URLError):
        reason = str(e.reason)
        if "Connection refused" in reason or "111" in reason:
            return "Connection Refused. Is your local AI server (Ollama/LM Studio) running?"
        if "getaddrinfo failed" in reason:
            return "DNS Error. Could not resolve the endpoint URL."
        return "Connection Error: %s" % reason

    if isinstance(e, socket.timeout) or "timed out" in msg.lower():
        return "Request Timed Out. Try increasing 'Request Timeout' in Settings."

    return msg


def format_error_for_display(e):
    """Return user-friendly error string for display in cells or dialogs."""
    return "Error: %s" % format_error_message(e)


def _get_ssl_context():
    """Create an SSL context that doesn't verify certificates."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def _extract_thinking_from_delta(chunk_delta):
    """Extract reasoning/thinking text from a stream delta for display in UI."""
    # Try direct fields first
    for field in ["reasoning_content", "thought", "thinking"]:
        thinking = chunk_delta.get(field)
        if isinstance(thinking, str) and thinking:
            return thinking
    
    # Try reasoning_details array
    details = chunk_delta.get("reasoning_details")
    if isinstance(details, list):
        parts = []
        for item in details:
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type in ("reasoning.text", "thought", "reasoning"):
                    parts.append(item.get("text") or "")
                elif item_type == "reasoning.summary":
                    parts.append(item.get("summary") or "")
        if parts:
            return "".join(parts)
    
    return ""


def _normalize_message_content(raw):
    """Return a single string from API message content (string or list of parts)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text") or "")
                elif "text" in item:
                    parts.append(item.get("text") or "")
        return "".join(parts) if parts else None
    return str(raw)


def _is_openai_compatible(config):
    endpoint = config.get("endpoint", "")
    return config.get("openai_compatibility", False) or (
        "api.openai.com" in endpoint.lower()
    )


class LlmClient:
    """LLM API client. Takes config dict from get_api_config(ctx) and UNO ctx."""

    def __init__(self, config, ctx):
        self.config = config
        self.ctx = ctx

    def _endpoint(self):
        return self.config.get("endpoint", "http://127.0.0.1:5000")

    def _api_path(self):
        return "/api" if self.config.get("is_openwebui") else "/v1"

    def _headers(self):
        h = {"Content-Type": "application/json"}
        api_key = self.config.get("api_key", "")
        if api_key:
            h["Authorization"] = "Bearer %s" % api_key
        return h

    def _timeout(self):
        return self.config.get("request_timeout", 120)

    def make_api_request(self, prompt, system_prompt="", max_tokens=70, api_type=None):
        """Build a streaming completion/chat request."""
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = 70

        endpoint = self._endpoint()
        api_path = self._api_path()
        if api_type is None:
            api_type = self.config.get("api_type", "completions")
        api_type = "chat" if api_type == "chat" else "completions"
        model = self.config.get("model", "")
        temperature = self.config.get("temperature", 0.5)
        seed_val = self.config.get("seed", "")

        init_logging(self.ctx)
        debug_log("=== API Request Debug ===", context="API")
        debug_log("Endpoint: %s" % endpoint, context="API")
        debug_log("API Type: %s" % api_type, context="API")
        debug_log("Model: %s" % model, context="API")
        debug_log("Max Tokens: %s" % max_tokens, context="API")

        if api_type == "chat":
            url = endpoint + api_path + "/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            data = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "stream": True,
            }
        else:
            url = endpoint + api_path + "/completions"
            full_prompt = prompt
            if system_prompt:
                full_prompt = (
                    "SYSTEM PROMPT\n%s\nEND SYSTEM PROMPT\n%s"
                    % (system_prompt, prompt)
                )
            data = {
                "prompt": full_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "stream": True,
            }
            if not _is_openai_compatible(self.config) or seed_val:
                try:
                    data["seed"] = int(seed_val) if seed_val else 10
                except (TypeError, ValueError):
                    data["seed"] = 10

        if model:
            data["model"] = model

        json_data = json.dumps(data).encode("utf-8")
        debug_log("Request data: %s" % json.dumps(data, indent=2), context="API")
        request = urllib.request.Request(
            url, data=json_data, headers=self._headers()
        )
        request.get_method = lambda: "POST"
        return request

    def extract_content_from_response(self, chunk, api_type="completions"):
        """Extract text content and optional thinking from API response chunk."""
        choices = chunk.get("choices", [])
        choice = choices[0] if choices else {}
        delta = choice.get("delta", {})

        finish_reason = choice.get("finish_reason") if choice else None
        if not finish_reason:
            finish_reason = chunk.get("finish_reason")
        if not finish_reason and choices:
            for c in choices:
                if isinstance(c, dict) and c.get("finish_reason"):
                    finish_reason = c.get("finish_reason")
                    break

        if api_type == "chat":
            content = (delta.get("content") or "") if delta else ""
        else:
            content = (choice.get("text") or "") if choice else ""

        thinking = _extract_thinking_from_delta(delta) if delta else ""
        if not thinking:
            thinking = _extract_thinking_from_delta(chunk)

        return content, finish_reason, thinking, delta

    def make_chat_request(self, messages, max_tokens=512, tools=None, stream=False):
        """Build a chat completions request from a full messages array."""
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = 512

        endpoint = self._endpoint()
        api_path = self._api_path()
        url = endpoint + api_path + "/chat/completions"
        model_name = self.config.get("model", "")
        temperature = self.config.get("temperature", 0.5)

        data = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "stream": stream,
        }
        if model_name:
            data["model"] = model_name
        data["reasoning"] = {"effort": "low", "enabled": True}
        if tools:
            data["tools"] = tools
            data["tool_choice"] = "auto"
            data["parallel_tool_calls"] = False

        json_data = json.dumps(data).encode("utf-8")
        init_logging(self.ctx)
        debug_log(
            "=== Chat Request (tools=%s, stream=%s) ===" % (bool(tools), stream),
            context="API",
        )
        debug_log("URL: %s" % url, context="API")
        debug_log("Messages: %s" % json.dumps(messages, indent=2), context="API")
        request = urllib.request.Request(
            url, data=json_data, headers=self._headers()
        )
        request.get_method = lambda: "POST"
        return request

    def stream_completion(
        self,
        prompt,
        system_prompt,
        max_tokens,
        api_type,
        append_callback,
        append_thinking_callback=None,
        stop_checker=None,
        dispatch_events=True,
    ):
        """Stream a completion/chat response via callbacks."""
        request = self.make_api_request(
            prompt, system_prompt, max_tokens, api_type=api_type
        )
        self.stream_request(
            request,
            api_type,
            append_callback,
            append_thinking_callback,
            stop_checker=stop_checker,
            dispatch_events=dispatch_events,
        )

    def stream_request(
        self,
        request,
        api_type,
        append_callback,
        append_thinking_callback=None,
        stop_checker=None,
        dispatch_events=True,
    ):
        """Stream a completion/chat response and append chunks via callbacks."""
        ssl_context = _get_ssl_context()
        timeout = self._timeout()

        init_logging(self.ctx)
        debug_log("=== Starting stream request ===", context="API")
        debug_log("Request URL: %s" % request.full_url, context="API")
        try:
            with urllib.request.urlopen(
                request, context=ssl_context, timeout=timeout
            ) as response:
                for line in response:
                    if stop_checker and stop_checker():
                        debug_log("stream_request: Stop requested by user.", context="API")
                        break

                    try:
                        if line.strip() and line.startswith(b"data: "):
                            payload = (
                                line[len(b"data: ") :].decode("utf-8").strip()
                            )
                            if payload == "[DONE]":
                                debug_log("stream_request: [DONE] received", context="API")
                                break
                            try:
                                chunk = json.loads(payload)
                            except json.JSONDecodeError:
                                continue
                            # Grok/xAI sends a final chunk with empty choices
                            choices = chunk.get("choices", [])
                            if not choices:
                                break
                            content, finish_reason, thinking, _ = (
                                self.extract_content_from_response(
                                    chunk, api_type
                                )
                            )
                            if thinking and append_thinking_callback:
                                append_thinking_callback(thinking)
                            if content:
                                append_callback(content)

                            if finish_reason:
                                break
                    except Exception as e:
                        debug_log("Error processing line: %s" % str(e), context="API")
                        raise
        except Exception as e:
            err_msg = format_error_message(e)
            debug_log("ERROR in stream_request: %s -> %s" % (e, err_msg), context="API")
            raise Exception(err_msg)

    def stream_chat_response(
        self,
        messages,
        max_tokens,
        append_callback,
        append_thinking_callback=None,
        stop_checker=None,
        dispatch_events=True,
    ):
        """Stream a final chat response (no tools) using the messages array."""
        request = self.make_chat_request(
            messages, max_tokens, tools=None, stream=True
        )
        self.stream_request(
            request,
            "chat",
            append_callback,
            append_thinking_callback,
            stop_checker=stop_checker,
            dispatch_events=dispatch_events,
        )

    def request_with_tools(self, messages, max_tokens=512, tools=None):
        """Non-streaming chat request. Returns parsed response dict."""
        request = self.make_chat_request(
            messages, max_tokens, tools=tools, stream=False
        )
        ssl_context = _get_ssl_context()
        timeout = self._timeout()

        try:
            with urllib.request.urlopen(
                request, context=ssl_context, timeout=timeout
            ) as response:
                body = response.read().decode("utf-8")
                result = json.loads(body)
        except Exception as e:
            err_msg = format_error_message(e)
            debug_log("request_with_tools ERROR: %s -> %s" % (e, err_msg), context="API")
            raise Exception(err_msg)

        debug_log("=== Tool response: %s" % json.dumps(result, indent=2), context="API")

        choice = result.get("choices", [{}])[0] if result.get("choices") else {}
        message = choice.get("message") or result.get("message") or {}
        finish_reason = choice.get("finish_reason") or result.get("done_reason")

        raw_content = message.get("content")
        content = _normalize_message_content(raw_content)

        return {
            "role": "assistant",
            "content": content,
            "tool_calls": message.get("tool_calls"),
            "finish_reason": finish_reason,
        }

    def stream_request_with_tools(
        self,
        messages,
        max_tokens=512,
        tools=None,
        append_callback=None,
        append_thinking_callback=None,
        stop_checker=None,
        dispatch_events=True,
    ):
        """Streaming chat request with tools. Returns same shape as request_with_tools."""
        init_logging(self.ctx)
        debug_log("stream_request_with_tools: building request (%d messages)..." % len(messages), context="API")
        request = self.make_chat_request(
            messages, max_tokens, tools=tools, stream=True
        )
        ssl_context = _get_ssl_context()
        timeout = self._timeout()

        message_snapshot = {}
        last_finish_reason = None
        last_chunk = None

        append_callback = append_callback or (lambda t: None)
        append_thinking_callback = append_thinking_callback or (lambda t: None)

        debug_log("stream_request_with_tools: Opening URL: %s" % request.full_url, context="API")
        update_activity_state("stream_request_with_tools")
        try:
            with urllib.request.urlopen(
                request, context=ssl_context, timeout=timeout
            ) as response:
                first_line_logged = False
                for line in response:
                    if stop_checker and stop_checker():
                        debug_log("stream_request_with_tools: Stop requested by user.", context="API")
                        last_finish_reason = "stop"
                        break

                    line_str = line.strip()
                    if not line_str or not line_str.startswith(b"data:"):
                        continue
                    # Payload is everything after "data:" (with or without space)
                    idx = line_str.find(b":") + 1
                    payload = line_str[idx:].decode("utf-8").strip()
                    if payload == "[DONE]":
                        debug_log("stream_request_with_tools: [DONE] received", context="API")
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    last_chunk = chunk

                    if not first_line_logged:
                        first_line_logged = True
                        update_activity_state("stream_first_chunk")

                    # Grok/xAI sends a final chunk with empty choices + usage
                    # after the finish_reason chunk; treat it as end-of-stream
                    choices = chunk.get("choices", [])
                    if not choices and (
                        message_snapshot.get("content")
                        or message_snapshot.get("tool_calls")
                    ):
                        last_finish_reason = last_finish_reason or "stop"
                        break

                    content, finish_reason, thinking, delta = (
                        self.extract_content_from_response(chunk, "chat")
                    )

                    if thinking:
                        append_thinking_callback(thinking)
                    if content:
                        append_callback(content)

                    if delta:
                        accumulate_delta(message_snapshot, delta)

                    last_finish_reason = finish_reason
                    if last_finish_reason:
                        break

                update_activity_state("stream_loop_exited")
                debug_log("stream_request_with_tools: stream ended", context="API")
                # Infer finish_reason if the stream ended without an explicit one
                if not last_finish_reason:
                    if message_snapshot.get("tool_calls"):
                        last_finish_reason = "tool_calls"
                    else:
                        last_finish_reason = "stop"
        except Exception as e:
            err_msg = format_error_message(e)
            debug_log("stream_request_with_tools ERROR: %s -> %s" % (e, err_msg), context="API")
            raise Exception(err_msg)

        raw_content = message_snapshot.get("content")
        content = _normalize_message_content(raw_content)
        tool_calls = message_snapshot.get("tool_calls")

        return {
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
            "finish_reason": last_finish_reason,
        }

    def chat_completion_sync(self, messages, max_tokens=512):
        """
        Synchronous chat completion (no streaming, no tools).
        Returns the assistant message content string.
        """
        result = self.request_with_tools(
            messages, max_tokens=max_tokens, tools=None
        )
        return result.get("content") or ""

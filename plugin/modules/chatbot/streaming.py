"""Streaming helpers for the chatbot module.

Provides:
- chat_event_stream: unified NDJSON event generator for tool-calling loop
- accumulate_delta: merge SSE chunk deltas into a complete message
- run_stream_drain_loop: main-thread drain loop for streaming responses
- run_stream_async: async wrapper that runs streaming on a worker thread
"""

import json
import queue
import threading
import logging

log = logging.getLogger("localwriter.chatbot.streaming")


# ── Unified NDJSON event stream ──────────────────────────────────────


def chat_event_stream(provider, session, adapter, doc, ctx,
                      max_rounds=15, stop_checker=None, broker=None):
    """Generator yielding NDJSON event dicts for a chat response.

    Runs the full streaming + tool-calling loop. Each yielded dict has
    a ``type`` key. Consumers iterate and dispatch on type.

    Event types::

        {"type": "text", "content": "..."}
        {"type": "thinking", "content": "..."}
        {"type": "tool_call", "name": "...", "arguments": {...}, "id": "..."}
        {"type": "tool_result", "name": "...", "content": ..., "id": "..."}
        {"type": "status", "message": "..."}
        {"type": "done", "content": "..."}
        {"type": "error", "message": "..."}

    Args:
        provider: LlmProvider instance.
        session: ChatSession (messages are mutated in place).
        adapter: ChatToolAdapter (or None to disable tools).
        doc: UNO document (or None).
        ctx: UNO component context (or None).
        max_rounds: max tool-calling iterations.
        stop_checker: callable returning True to abort.
        broker: mutable dict ``{"extra_names": set()}`` to enable
                two-tier tool delivery, or None for classic mode.
    """
    tools = None
    if adapter:
        try:
            if broker is not None:
                tools = adapter.get_brokered_tools(doc, broker)
                log.info("Broker mode: %d core+extra tools", len(tools) if tools else 0)
            else:
                tools = adapter.get_tools_for_doc(doc)
                log.info("Classic mode: %d tools", len(tools) if tools else 0)
        except Exception:
            pass

    tools_count = len(tools) if tools else 0
    if tools_count:
        yield {"type": "status", "message": "Sending %d tools..." % tools_count}

    for _round in range(max_rounds):
        if stop_checker and stop_checker():
            return

        acc = {}
        content_parts = []

        try:
            for chunk in provider.stream(
                    session.messages, tools=tools):
                if stop_checker and stop_checker():
                    return
                text = chunk.get("content", "")
                thinking = chunk.get("thinking", "")
                delta = chunk.get("delta", {})
                if thinking:
                    yield {"type": "thinking", "content": thinking}
                if text:
                    content_parts.append(text)
                    yield {"type": "text", "content": text}
                if delta:
                    acc = accumulate_delta(acc, delta)
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        if stop_checker and stop_checker():
            return

        tool_calls = acc.get("tool_calls")
        content = "".join(content_parts)

        if not tool_calls:
            session.add_assistant_message(content=content)
            yield {"type": "done", "content": content}
            return

        # Process tool calls
        session.add_assistant_message(
            content=content or None, tool_calls=tool_calls)

        for tc in tool_calls:
            if stop_checker and stop_checker():
                return
            fn = tc.get("function", {})
            name = fn.get("name", "")
            tc_id = tc.get("id", "")
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}

            yield {"type": "tool_call", "name": name,
                   "arguments": args, "id": tc_id}
            yield {"type": "status", "message": "Tool: %s" % name}

            if adapter:
                result = adapter.execute_tool(name, args, doc, ctx)
                result_str = json.dumps(
                    result, ensure_ascii=False, default=str)
                session.add_tool_result(tc_id, result_str)
                yield {"type": "tool_result", "name": name,
                       "content": result, "id": tc_id}

                # Broker: activate requested tools for next round
                if (broker is not None and name == "request_tools"
                        and result.get("status") == "ok"):
                    enabled = result.get("enabled", [])
                    if enabled:
                        broker["extra_names"].update(enabled)
                        try:
                            tools = adapter.get_brokered_tools(doc, broker)
                        except Exception:
                            pass
                        yield {"type": "status",
                               "message": "Enabling %d additional tools..."
                               % len(enabled)}

    # Exhausted max rounds
    yield {"type": "done", "content": "".join(content_parts)}


# ── Delta accumulation ────────────────────────────────────────────────
# Adapted from openai-python (Apache 2.0) src/openai/lib/streaming/_deltas.py


def accumulate_delta(acc, delta):
    """Merge a streaming chunk delta into an accumulated message.

    Required for tool-calling: builds the full assistant message from SSE
    chunks. Content and tool_calls (with partial function.arguments) are
    merged by index; strings are concatenated.
    """
    for key, delta_value in delta.items():
        if key not in acc:
            acc[key] = delta_value
            continue

        acc_value = acc[key]
        if acc_value is None:
            acc[key] = delta_value
            continue

        if key == "index" or key == "type":
            acc[key] = delta_value
            continue

        if isinstance(acc_value, str) and isinstance(delta_value, str):
            acc_value += delta_value
        elif isinstance(acc_value, (int, float)) and isinstance(
            delta_value, (int, float)
        ):
            acc_value += delta_value
        elif isinstance(acc_value, dict) and isinstance(delta_value, dict):
            acc_value = accumulate_delta(acc_value, delta_value)
        elif isinstance(acc_value, list) and isinstance(delta_value, list):
            if all(isinstance(x, (str, int, float)) for x in acc_value):
                acc_value.extend(delta_value)
                acc[key] = acc_value
                continue

            for delta_entry in delta_value:
                if not isinstance(delta_entry, dict):
                    raise TypeError(
                        "Unexpected list delta entry: %s" % delta_entry)
                index = delta_entry.get("index")
                if index is None or not isinstance(index, int):
                    raise RuntimeError(
                        "Expected list delta entry to have int 'index': %s"
                        % delta_entry)
                try:
                    acc_entry = acc_value[index]
                except IndexError:
                    acc_value.insert(index, delta_entry)
                else:
                    if isinstance(acc_entry, dict):
                        acc_value[index] = accumulate_delta(
                            acc_entry, delta_entry)

        acc[key] = acc_value

    return acc


# ── Main-thread drain loop ───────────────────────────────────────────


def run_stream_drain_loop(
    q, toolkit, job_done, apply_chunk_fn,
    on_stream_done, on_stopped, on_error, on_status_fn=None,
):
    """Main-thread drain loop for streaming responses.

    Batches items from queue, maintains thinking/chunk buffers,
    calls apply_chunk_fn for content. Processes VCL events between
    iterations to keep the UI responsive.

    on_stream_done(response) returns True if finished, False if more
    items will be pushed (e.g. next tool round).
    """
    thinking_open = [False]

    while not job_done[0]:
        items = []
        try:
            items.append(q.get(timeout=0.1))
            try:
                while True:
                    items.append(q.get_nowait())
            except queue.Empty:
                pass
        except queue.Empty:
            toolkit.processEventsToIdle()
            continue

        try:
            current_content = []
            current_thinking = []

            def flush_buffers():
                if current_thinking:
                    if not thinking_open[0]:
                        apply_chunk_fn("[Thinking] ", is_thinking=True)
                        thinking_open[0] = True
                    apply_chunk_fn("".join(current_thinking), is_thinking=True)
                    current_thinking.clear()
                if current_content:
                    if thinking_open[0]:
                        apply_chunk_fn(" /thinking\n", is_thinking=True)
                        thinking_open[0] = False
                    apply_chunk_fn("".join(current_content), is_thinking=False)
                    current_content.clear()

            def close_thinking():
                if thinking_open[0]:
                    apply_chunk_fn(" /thinking\n", is_thinking=True)
                    thinking_open[0] = False

            for item in items:
                kind = item[0] if isinstance(item, tuple) else item
                response = item[1] if len(item) > 1 else None
                if kind == "chunk":
                    if current_thinking:
                        flush_buffers()
                    current_content.append(item[1])
                elif kind == "thinking":
                    if current_content:
                        flush_buffers()
                    current_thinking.append(item[1])
                elif kind == "stream_done":
                    flush_buffers()
                    close_thinking()
                    if on_stream_done(response):
                        job_done[0] = True
                    break
                elif kind == "stopped":
                    flush_buffers()
                    close_thinking()
                    try:
                        on_stopped()
                    except Exception:
                        log.exception("on_stopped failed")
                    job_done[0] = True
                    break
                elif kind == "error":
                    flush_buffers()
                    close_thinking()
                    try:
                        on_error(response)
                    except Exception:
                        log.exception("on_error failed")
                    job_done[0] = True
                    break
                elif kind == "status":
                    if on_status_fn:
                        try:
                            on_status_fn(item[1])
                        except Exception:
                            pass

            flush_buffers()

        except Exception as e:
            job_done[0] = True
            try:
                on_error(e)
            except Exception:
                log.exception("on_error failed")

        toolkit.processEventsToIdle()


# ── Async stream wrapper ──────────────────────────────────────────────


def run_stream_async(
    ctx, provider, messages, tools,
    apply_chunk_fn, on_done_fn, on_error_fn,
    on_status_fn=None, stop_checker=None, **kwargs,
):
    """Run provider.stream() on a worker thread, drain via main-thread loop.

    apply_chunk_fn(text, is_thinking) and on_done_fn() / on_error_fn(exc)
    are called on the main thread. Blocks until stream finishes.
    """
    q = queue.Queue()
    job_done = [False]

    def worker():
        try:
            acc = {}
            for chunk in provider.stream(messages, tools=tools, **kwargs):
                if stop_checker and stop_checker():
                    q.put(("stopped",))
                    return
                content = chunk.get("content", "")
                thinking = chunk.get("thinking", "")
                delta = chunk.get("delta", {})
                if thinking:
                    q.put(("thinking", thinking))
                if content:
                    q.put(("chunk", content))
                if delta:
                    acc = accumulate_delta(acc, delta)
            q.put(("stream_done", acc))
        except Exception as e:
            q.put(("error", e))

    try:
        import uno
        toolkit = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
    except Exception as e:
        on_error_fn(e)
        return

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    def on_stream_done(response):
        on_done_fn()
        return True

    run_stream_drain_loop(
        q, toolkit, job_done, apply_chunk_fn,
        on_stream_done=on_stream_done,
        on_stopped=on_done_fn,
        on_error=on_error_fn,
        on_status_fn=on_status_fn,
    )

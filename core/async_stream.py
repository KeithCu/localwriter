"""
Async stream completion: run blocking stream_completion on a worker thread,
drain chunks via a queue and a main-thread loop with processEventsToIdle (pure Python, no UNO Timer).
Shared drain loop used by both simple streaming and tool-calling (chat_panel).
"""
import queue
import threading

from core.logging import debug_log


def run_stream_drain_loop(
    q,
    toolkit,
    job_done,
    apply_chunk_fn,
    on_stream_done,
    on_stopped,
    on_error,
):
    """
    Main-thread drain loop: batch items from queue, maintain thinking/chunk buffers,
    call apply_chunk_fn for content. on_stream_done(response) returns True if job is
    finished, False if more items will be pushed (e.g. next tool round). on_stopped()
    and on_error(exception) are called when stopped or error; job_done is set and loop exits.
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
                    except Exception as e:
                        debug_log("run_stream_drain_loop: on_stopped failed: %s" % e, context="API")
                    job_done[0] = True
                    break
                elif kind == "error":
                    flush_buffers()
                    close_thinking()
                    try:
                        on_error(response)
                    except Exception as e:
                        debug_log("run_stream_drain_loop: on_error failed: %s" % e, context="API")
                    job_done[0] = True
                    break

            flush_buffers()

        except Exception as e:
            job_done[0] = True
            try:
                on_error(e)
            except Exception as e2:
                debug_log("run_stream_drain_loop: on_error failed: %s" % e2, context="API")

        toolkit.processEventsToIdle()


def run_stream_completion_async(
    ctx,
    client,
    prompt,
    system_prompt,
    max_tokens,
    api_type,
    apply_chunk_fn,
    on_done_fn,
    on_error_fn,
    stop_checker=None,
):
    """
    Run client.stream_completion on a worker thread; drain (chunk, thinking) via a
    queue and a main-thread loop with processEventsToIdle. apply_chunk_fn(chunk_text, is_thinking)
    and on_done_fn() / on_error_fn(exception) are called on the main thread.
    Blocks until stream finishes (pure Python queue, no UNO Timer).
    """
    q = queue.Queue()
    job_done = [False]

    def worker():
        try:
            client.stream_completion(
                prompt,
                system_prompt,
                max_tokens,
                api_type,
                append_callback=lambda t: q.put(("chunk", t)),
                append_thinking_callback=lambda t: q.put(("thinking", t)),
                stop_checker=stop_checker,
                dispatch_events=False,
            )
            if stop_checker and stop_checker():
                q.put(("stopped",))
            else:
                q.put(("stream_done", None))
        except Exception as e:
            q.put(("error", e))

    try:
        toolkit = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
    except Exception as e:
        on_error_fn(e)
        return

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    def on_stream_done(_response):
        on_done_fn()
        return True

    run_stream_drain_loop(
        q, toolkit, job_done, apply_chunk_fn,
        on_stream_done=on_stream_done,
        on_stopped=on_done_fn,
        on_error=on_error_fn,
    )


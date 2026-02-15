"""
Async stream completion: run blocking stream_completion on a worker thread,
drain chunks via a queue and a main-thread loop with processEventsToIdle (pure Python, no UNO Timer).
"""
import queue
import threading


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
    thinking_open = [False]

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
                q.put(("stream_done",))
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

    # Main-thread drain loop: queue + processEventsToIdle only (no UNO Timer)
    while not job_done[0]:
        try:
            item = q.get(timeout=0.05)
        except queue.Empty:
            toolkit.processEventsToIdle()
            continue
        try:
            kind = item[0] if isinstance(item, tuple) else item
            if kind == "chunk":
                if thinking_open[0]:
                    apply_chunk_fn(" /thinking\n", is_thinking=True)
                    thinking_open[0] = False
                apply_chunk_fn(item[1], is_thinking=False)
            elif kind == "thinking":
                if not thinking_open[0]:
                    apply_chunk_fn("[Thinking] ", is_thinking=True)
                    thinking_open[0] = True
                apply_chunk_fn(item[1], is_thinking=True)
            elif kind == "stream_done":
                if thinking_open[0]:
                    apply_chunk_fn(" /thinking\n", is_thinking=True)
                    thinking_open[0] = False
                job_done[0] = True
                on_done_fn()
            elif kind == "stopped":
                if thinking_open[0]:
                    apply_chunk_fn(" /thinking\n", is_thinking=True)
                job_done[0] = True
                on_done_fn()
            elif kind == "error":
                if thinking_open[0]:
                    apply_chunk_fn(" /thinking\n", is_thinking=True)
                job_done[0] = True
                on_error_fn(item[1])
        except Exception as e:
            job_done[0] = True
            on_error_fn(e)
        toolkit.processEventsToIdle()

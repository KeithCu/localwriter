"""
Async stream completion: run blocking stream_completion on a worker thread,
drain chunks via a queue and a main-thread loop with processEventsToIdle (pure Python, no UNO Timer).
"""
import os
import queue
import threading
import time


def test_timer_runs_on_main_thread(ctx):
    """
    Verify whether the LibreOffice Timer's fired() callback runs on the main thread.
    Call this from within LibreOffice (e.g. temporary menu action, or from Python
    console with a bootstrap ctx) and check the result.
    Example: from core.async_stream import test_timer_runs_on_main_thread; test_timer_runs_on_main_thread(ctx)
    """
    import unohelper
    from com.sun.star.util import XTimerListener

    creator_thread = threading.current_thread()
    fired_thread = [None]
    uno_ok = [False]
    timer_ref = [None]

    try:
        smgr = ctx.getServiceManager()
        timer = smgr.createInstanceWithContext("com.sun.star.util.Timer", ctx)
        timer_ref[0] = timer
    except Exception as e:
        return {"error": str(e), "creator": str(creator_thread)}

    class TimerListener(unohelper.Base, XTimerListener):
        def fired(self, ev):
            fired_thread[0] = threading.current_thread()
            try:
                ctx.getServiceManager()
                uno_ok[0] = True
            except Exception:
                uno_ok[0] = False
            try:
                if timer_ref[0]:
                    timer_ref[0].stop()
            except Exception:
                pass

        def disposing(self, ev):
            pass

    listener = TimerListener()
    try:
        timer.addTimerListener(listener)
    except Exception as e:
        return {"error": "addTimerListener: %s" % e, "creator": str(creator_thread)}
    timer.setDelay(500)
    timer.start()
    for _ in range(20):
        if fired_thread[0] is not None:
            break
        time.sleep(0.1)
    try:
        timer.stop()
    except Exception:
        pass

    same = (fired_thread[0] is creator_thread) if fired_thread[0] else None
    result = {
        "creator_thread": str(creator_thread),
        "creator_name": getattr(creator_thread, "name", None),
        "fired_thread": str(fired_thread[0]) if fired_thread[0] else None,
        "fired_name": getattr(fired_thread[0], "name", None) if fired_thread[0] else None,
        "same_thread": same,
        "uno_ok_from_fired": uno_ok[0],
    }
    # Write result to a known path so we can check after running the test
    try:
        log_path = os.path.join(os.path.expanduser("~"), "localwriter_timer_test.log")
        with open(log_path, "w", encoding="utf-8") as f:
            for k, v in result.items():
                f.write("%s: %s\n" % (k, v))
    except Exception:
        pass
    try:
        from core.logging import debug_log
        debug_log(ctx, "Timer test result: same_thread=%s uno_ok_from_fired=%s" % (result.get("same_thread"), result.get("uno_ok_from_fired")))
    except Exception:
        pass
    return result


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

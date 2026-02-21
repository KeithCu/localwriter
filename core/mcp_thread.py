# Main-thread queue pattern for MCP adapted from the LibreOffice MCP Extension
# (in-repo: libreoffice-mcp-extension/). Their ai_interface runs UNO on the
# main thread; this module provides the same contract for LocalWriter. Thanks
# to that project; check libreoffice-mcp-extension/ when maintaining this module.
"""
MCP main-thread executor: work is queued from HTTP handler threads and drained
on the UNO main thread (via UNO Timer in main.py). All UNO calls must run on
the main thread.
"""
import queue
import threading

_mcp_queue = queue.Queue()


class _Future:
    def __init__(self):
        self._event = threading.Event()
        self._result = None
        self._exc = None

    def set_result(self, v):
        self._result = v
        self._event.set()

    def set_exception(self, e):
        self._exc = e
        self._event.set()

    def result(self, timeout=30.0):
        if not self._event.wait(timeout):
            raise TimeoutError("UNO main-thread call timed out")
        if self._exc:
            raise self._exc
        return self._result


def execute_on_main_thread(func, *args, timeout=30.0):
    future = _Future()
    _mcp_queue.put((func, args, future))
    return future.result(timeout=timeout)


def drain_mcp_queue(max_per_tick=5):
    """Drain pending MCP requests. Called on the main thread."""
    for _ in range(max_per_tick):
        try:
            func, args, future = _mcp_queue.get_nowait()
        except queue.Empty:
            break
        try:
            future.set_result(func(*args))
        except Exception as e:
            future.set_exception(e)

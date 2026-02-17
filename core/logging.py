"""Simple file logging for LocalWriter. Single debug log + optional agent log; paths set via init_logging(ctx)."""
import os
import json
import time
import threading

# Globals set by init_logging(ctx); used by debug_log and agent_log so ctx is not passed at write time.
_debug_log_path = None
_agent_log_path = None
_enable_agent_log = False
_init_lock = threading.Lock()

# Watchdog: shared state (main thread updates, watchdog reads)
_activity_state = {"phase": "", "round_num": -1, "tool_name": None, "last_activity": 0.0}
_activity_lock = threading.Lock()
_watchdog_started = False
_watchdog_interval_sec = 15
_watchdog_threshold_sec = 30

DEBUG_LOG_FILENAME = "localwriter_debug.log"
AGENT_LOG_FILENAME = "localwriter_agent.log"
FALLBACK_DEBUG = os.path.join(os.path.expanduser("~"), "localwriter_debug.log")
FALLBACK_AGENT = os.path.join(os.path.expanduser("~"), "localwriter_agent.log")


def init_logging(ctx):
    """Set global log paths and enable_agent_log from ctx. Idempotent; safe to call from any entry point."""
    global _debug_log_path, _agent_log_path, _enable_agent_log
    with _init_lock:
        if _debug_log_path is not None:
            return
        _debug_log_path = FALLBACK_DEBUG
        _agent_log_path = FALLBACK_AGENT
        _enable_agent_log = False
        try:
            from core import config
            udir = config.user_config_dir(ctx)
            if udir:
                _debug_log_path = os.path.join(udir, DEBUG_LOG_FILENAME)
                _agent_log_path = os.path.join(udir, AGENT_LOG_FILENAME)
                _enable_agent_log = config.as_bool(config.get_config(ctx, "enable_agent_log", False))
        except Exception:
            pass


def _get_debug_path():
    return _debug_log_path if _debug_log_path else FALLBACK_DEBUG


def _get_agent_path():
    return _agent_log_path if _agent_log_path else FALLBACK_AGENT


def debug_log(msg, context=None):
    """Write one line to the unified debug log. Uses global path (set by init_logging). No ctx needed."""
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        ms = int((time.time() % 1) * 1000)
        prefix = "[%s] " % context if context else ""
        line = "%s.%03d | %s%s\n" % (now, ms, prefix, msg)
    except Exception:
        line = msg + "\n"
    path = _get_debug_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def agent_log(location, message, data=None, hypothesis_id=None, run_id=None):
    """Write one NDJSON line to agent log if enable_agent_log is True. Uses global path."""
    if not _enable_agent_log:
        return
    payload = {"location": location, "message": message, "timestamp": int(time.time() * 1000)}
    if data is not None:
        payload["data"] = data
    if hypothesis_id is not None:
        payload["hypothesisId"] = hypothesis_id
    if run_id is not None:
        payload["runId"] = run_id
    line = json.dumps(payload) + "\n"
    path = _get_agent_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def update_activity_state(phase, round_num=None, tool_name=None):
    """Update shared activity state (call from main thread at phase boundaries).
    Pass phase='' when returning control to LibreOffice so the watchdog stops checking."""
    with _activity_lock:
        _activity_state["phase"] = phase
        _activity_state["last_activity"] = time.monotonic()
        if round_num is not None:
            _activity_state["round_num"] = round_num
        if tool_name is not None:
            _activity_state["tool_name"] = tool_name


def _watchdog_loop(status_control):
    """Daemon thread: if no activity for threshold, log and set status to Hung: ..."""
    while True:
        time.sleep(_watchdog_interval_sec)
        with _activity_lock:
            phase = _activity_state["phase"]
            round_num = _activity_state["round_num"]
            tool_name = _activity_state["tool_name"]
            last = _activity_state["last_activity"]
        if not phase:
            continue
        elapsed = time.monotonic() - last
        if elapsed < _watchdog_threshold_sec:
            continue
        msg = "WATCHDOG: no activity for %ds; phase=%s round=%s tool=%s" % (
            int(elapsed), phase, round_num, tool_name if tool_name else "")
        debug_log(msg, context="Chat")
        if status_control:
            try:
                hung_text = "Hung: %s round %s" % (phase, round_num)
                if tool_name:
                    hung_text += " %s" % tool_name
                status_control.setText(hung_text)
            except Exception:
                pass  # UNO from background thread may be unsafe; ignore


def start_watchdog_thread(ctx, status_control=None):
    """Start the hang-detection watchdog (idempotent). Pass status_control to set Hung: ... in UI."""
    global _watchdog_started
    with _activity_lock:
        if _watchdog_started:
            return
        _watchdog_started = True
    t = threading.Thread(target=_watchdog_loop, args=(status_control,), daemon=True)
    t.start()

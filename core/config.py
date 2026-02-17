"""
Configuration logic for LocalWriter.
Reads/writes localwriter.json in LibreOffice's user config directory.
"""
import os
import json
import uno


CONFIG_FILENAME = "localwriter.json"


def _config_path(ctx):
    """Return the absolute path to localwriter.json."""
    sm = ctx.getServiceManager()
    path_settings = sm.createInstanceWithContext(
        "com.sun.star.util.PathSettings", ctx)
    user_config_path = getattr(path_settings, "UserConfig", "")
    if user_config_path and str(user_config_path).startswith("file://"):
        user_config_path = str(uno.fileUrlToSystemPath(user_config_path))
    return os.path.join(user_config_path, CONFIG_FILENAME)


def user_config_dir(ctx):
    """Return LibreOffice user config directory, or None if unavailable."""
    if ctx is None:
        return None
    try:
        p = _config_path(ctx)
        return os.path.dirname(p) if p else None
    except Exception:
        return None


def get_config(ctx, key, default):
    """Get a config value by key. Returns default if missing or on error."""
    config_file_path = _config_path(ctx)
    if not os.path.exists(config_file_path):
        return default
    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return default
    return config_data.get(key, default)


def set_config(ctx, key, value):
    """Set a config key to value. Creates file if needed."""
    config_file_path = _config_path(ctx)
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except (IOError, json.JSONDecodeError):
            config_data = {}
    else:
        config_data = {}
    config_data[key] = value
    try:
        with open(config_file_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        print("Error writing to %s: %s" % (config_file_path, e))


def as_bool(value):
    """Parse a value as boolean (handles str, int, float)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def populate_combobox_with_lru(ctx, ctrl, current_val, lru_key):
    """Helper to populate a combobox with values from an LRU list in config.
    Ensures current_val is at the top/selected."""
    lru = get_config(ctx, lru_key, [])
    if not isinstance(lru, list):
        lru = []
    
    curr_val_str = str(current_val).strip()
    to_show = list(lru)
    if curr_val_str and curr_val_str not in to_show:
        to_show.insert(0, curr_val_str)
    
    if to_show:
        ctrl.addItems(tuple(to_show), 0)
        if curr_val_str:
            ctrl.setText(curr_val_str)


def update_lru_history(ctx, val, lru_key, max_items=10):
    """Helper to update an LRU list in config."""
    val_str = str(val).strip()
    if not val_str:
        return
    
    lru = get_config(ctx, lru_key, [])
    if not isinstance(lru, list):
        lru = []
    
    if val_str in lru:
        lru.remove(val_str)
    lru.insert(0, val_str)
    set_config(ctx, lru_key, lru[:max_items])


def get_api_config(ctx):
    """Build API config dict from ctx for LlmClient. Pass to LlmClient(config, ctx)."""
    endpoint = str(get_config(ctx, "endpoint", "http://127.0.0.1:5000")).rstrip("/")
    is_openwebui = (
        as_bool(get_config(ctx, "is_openwebui", False))
        or "open-webui" in endpoint.lower()
        or "openwebui" in endpoint.lower()
    )
    return {
        "endpoint": endpoint,
        "api_key": str(get_config(ctx, "api_key", "")),
        "model": str(get_config(ctx, "model", "")),
        "api_type": str(get_config(ctx, "api_type", "completions")).lower(),
        "is_openwebui": is_openwebui,
        "openai_compatibility": as_bool(get_config(ctx, "openai_compatibility", False)),
        "temperature": _safe_float(get_config(ctx, "temperature", 0.5), 0.5),
        "seed": get_config(ctx, "seed", ""),
        "request_timeout": _safe_int(get_config(ctx, "request_timeout", 120), 120),
        "chat_max_tool_rounds": _safe_int(get_config(ctx, "chat_max_tool_rounds", 5), 5),
    }

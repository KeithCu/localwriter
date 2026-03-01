"""DictConfigProxy — dict-backed config proxy for YAML instances.

Mimics the ModuleConfigProxy interface (get/set) so that providers
created from YAML instance definitions work unchanged.
"""

import json
import logging

log = logging.getLogger("localwriter.ai")


def load_instances_json(cfg, key="instances"):
    """Parse the instances JSON list from config. Returns list or None."""
    raw = cfg.get(key, "[]")
    if not raw or raw == "[]":
        return None
    try:
        if isinstance(raw, str):
            items = json.loads(raw)
        else:
            items = raw
        if isinstance(items, list) and items:
            return items
    except (json.JSONDecodeError, TypeError):
        log.warning("Invalid instances JSON in config: %s", key)
    return None


class DictConfigProxy:
    """Wraps a flat dict to look like a ModuleConfigProxy."""

    __slots__ = ("_data",)

    def __init__(self, data=None):
        self._data = dict(data) if data else {}

    def get(self, key, default=None):
        """Read a value from the dict."""
        val = self._data.get(key)
        return val if val is not None else default

    def set(self, key, value):
        """Write a value to the dict."""
        self._data[key] = value

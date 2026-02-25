"""DictConfigProxy — dict-backed config proxy for YAML instances.

Mimics the ModuleConfigProxy interface (get/set) so that providers
created from YAML instance definitions work unchanged.
"""


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

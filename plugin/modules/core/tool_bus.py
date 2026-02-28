import threading


class EventBus:
    """
    Internal event bus to allow background threads (like the MCP server)
    to notify the UI (main thread) about activity.
    """

    def __init__(self):
        self._listeners = []
        self._lock = threading.Lock()

    def subscribe(self, listener):
        """Add a listener callback: func(event_type, data_dict)"""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener):
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def broadcast(self, event_type, data):
        """Broadcast an event to all subscribers."""
        with self._lock:
            # Copy list to allow listeners to unsubscribe during callback
            targets = list(self._listeners)

        for listener in targets:
            try:
                listener(event_type, data)
            except Exception:
                # Silently ignore errors in listeners
                pass


# Global instance
tool_bus = EventBus()

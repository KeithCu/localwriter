"""Per-invocation context passed to every tool execution."""


class ToolContext:
    """Immutable-ish context for a single tool invocation.

    Attributes:
        doc:       UNO document model.
        ctx:       UNO component context.
        doc_type:  Detected document type ("writer", "calc", "draw").
        services:  ServiceRegistry — access to all services.
        caller:    Who triggered the call ("chatbot", "mcp", "menu").
        status_callback: Optional callback for status updates (Writer tools).
        append_thinking_callback: Optional callback for thinking text (Writer tools).
        stop_checker: Optional callable () -> bool; if present and returns True, tool should stop.
    """

    __slots__ = ("doc", "ctx", "doc_type", "services", "caller", "status_callback", "append_thinking_callback", "stop_checker")

    def __init__(self, doc, ctx, doc_type, services, caller="", status_callback=None, append_thinking_callback=None, stop_checker=None):
        self.doc = doc
        self.ctx = ctx
        self.doc_type = doc_type
        self.services = services
        self.caller = caller
        self.status_callback = status_callback
        self.append_thinking_callback = append_thinking_callback
        self.stop_checker = stop_checker

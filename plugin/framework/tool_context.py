"""Per-invocation context passed to every tool execution."""


class ToolContext:
    """Immutable-ish context for a single tool invocation.

    Attributes:
        doc:       UNO document model.
        ctx:       UNO component context.
        doc_type:  Detected document type ("writer", "calc", "draw").
        services:  ServiceRegistry — access to all services.
        caller:    Who triggered the call ("chatbot", "mcp", "menu").
    """

    __slots__ = ("doc", "ctx", "doc_type", "services", "caller")

    def __init__(self, doc, ctx, doc_type, services, caller=""):
        self.doc = doc
        self.ctx = ctx
        self.doc_type = doc_type
        self.services = services
        self.caller = caller

"""Base class for all tools."""

from abc import ABC, abstractmethod


_READ_PREFIXES = ("get_", "read_", "list_", "find_", "search_", "count_")


class ToolBase(ABC):
    """Abstract base for every tool exposed to LLM agents and MCP clients.

    Subclasses must set ``name``, ``description``, ``parameters`` and
    implement ``execute``.

    Attributes:
        name:        Unique tool identifier (e.g. "get_document_outline").
        description: Human-readable description shown to LLMs.
        parameters:  JSON Schema dict (MCP ``inputSchema`` format).
        doc_types:   List of supported doc types (["writer"], ["calc"],
                     ["draw"], or None for all types).
        tier:        "core" = always sent to the LLM, "extended" = on demand
                     via the tool broker.  Default "extended".
        intent:      Broker group: "navigate", "edit", "review", or "media".
                     Used by request_tools(intent=...) to load tool groups.
        is_mutation:  Whether the tool mutates the document.  ``None``
                     means auto-detect from name prefix.
        long_running: Hint that the tool may take a while (e.g. image gen).
    """

    name: str = None
    description: str = ""
    parameters: dict = None
    doc_types: list = None
    tier: str = "extended"
    intent: str = None
    is_mutation: bool = None
    long_running: bool = False

    def detects_mutation(self):
        """Return True if the tool mutates the document."""
        if self.is_mutation is not None:
            return self.is_mutation
        if self.name:
            return not self.name.startswith(_READ_PREFIXES)
        return True

    def validate(self, **kwargs):
        """Validate arguments against ``parameters`` schema.

        Returns:
            (ok: bool, error_message: str | None)
        """
        schema = self.parameters or {}
        required = schema.get("required", [])
        for key in required:
            if key not in kwargs:
                return False, f"Missing required parameter: {key}"
        props = schema.get("properties", {})
        for key in kwargs:
            if props and key not in props:
                return False, f"Unknown parameter: {key}"
        return True, None

    @abstractmethod
    def execute(self, ctx, **kwargs):
        """Execute the tool.

        Args:
            ctx:    ToolContext with doc, services, caller info.
            **kwargs: Tool arguments (already validated).

        Returns:
            dict with at least ``{"status": "ok"|"error", ...}``.
        """

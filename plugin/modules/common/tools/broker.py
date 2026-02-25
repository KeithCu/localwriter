"""Tool broker meta-tools.

Two-tier tool delivery: the LLM receives only *core* tools plus these
two meta-tools.  It can call ``list_available_tools`` to browse the
full catalogue, then ``request_tools`` to activate the ones it needs.
"""

from plugin.framework.tool_base import ToolBase


class ListAvailableTools(ToolBase):
    """List tools available for activation via the tool broker."""

    name = "list_available_tools"
    description = (
        "List additional tools that can be activated for this document. "
        "Returns name, description, and intent group for each tool. "
        "Intents: navigate, edit, review, media. "
        "Call request_tools(intent=...) to enable a whole group, "
        "or request_tools(names=[...]) for specific tools."
    )
    parameters = {
        "type": "object",
        "properties": {},
    }
    doc_types = None
    tier = "core"

    def execute(self, ctx, **kwargs):
        registry = ctx.services.get("tools")
        if not registry:
            return {"status": "error", "error": "Tool registry unavailable"}
        summaries = registry.get_tool_summaries(
            doc_type=ctx.doc_type, tier="extended")
        return {"status": "ok", "tools": summaries}


class RequestTools(ToolBase):
    """Activate additional tools by name."""

    name = "request_tools"
    description = (
        "Activate additional tools by intent group or by name. "
        "intent: 'navigate', 'edit', 'review', or 'media' to load "
        "a whole group at once. names: list of specific tool names."
    )
    parameters = {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["navigate", "edit", "review", "media"],
                "description": "Activate all tools in this intent group.",
            },
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of specific tool names to activate.",
            },
        },
    }
    doc_types = None
    tier = "core"
    is_mutation = False

    def execute(self, ctx, **kwargs):
        intent = kwargs.get("intent")
        names = kwargs.get("names", [])
        registry = ctx.services.get("tools")
        if not registry:
            return {"status": "error", "error": "Tool registry unavailable"}

        if intent:
            names = list(names) + registry.get_tool_names_by_intent(
                doc_type=ctx.doc_type, intent=intent)

        enabled = []
        unknown = []
        for n in names:
            tool = registry.get(n)
            if tool:
                enabled.append(n)
            else:
                unknown.append(n)

        return {"status": "ok", "enabled": enabled, "unknown": unknown}

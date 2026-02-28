"""Base class for all services."""

from abc import ABC


class ServiceBase(ABC):
    """Abstract base for services registered in the ServiceRegistry.

    Services provide horizontal capabilities (document manipulation,
    config access, LLM streaming, etc.) that modules and tools consume.

    Attributes:
        name: Unique service identifier (e.g. "document", "config").
    """

    name: str = None

    def initialize(self, ctx):
        """Called once during bootstrap with the UNO component context.

        Override to perform setup that requires UNO (desktop access,
        service manager, etc.).

        Args:
            ctx: UNO component context (com.sun.star.uno.XComponentContext).
        """

    def shutdown(self):
        """Called on extension unload. Override to clean up."""

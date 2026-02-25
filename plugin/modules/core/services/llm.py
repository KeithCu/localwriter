"""LlmService — interface and router for LLM backends.

This service defines the contract that LLM backend modules (ai_openai,
ai_ollama, etc.) must implement. It routes calls to the active provider
based on config.

Since the introduction of AiService, LlmService acts as a thin shim
that delegates to AiService for backward compatibility.
"""

import logging
from abc import ABC, abstractmethod

from plugin.framework.service_base import ServiceBase

log = logging.getLogger("localwriter.llm")


class LlmProvider(ABC):
    """Interface that backend modules implement and register."""

    name: str = None

    @abstractmethod
    def stream(self, messages, tools=None, **kwargs):
        """Stream a chat completion.

        Args:
            messages: List of message dicts (OpenAI format).
            tools:    Optional list of tool schemas (OpenAI format).
            **kwargs: Extra params (temperature, max_tokens, etc.)

        Yields:
            Chunks (format depends on implementation, but should include
            delta content and tool calls).
        """

    @abstractmethod
    def complete(self, messages, tools=None, **kwargs):
        """Non-streaming completion. Returns full response dict."""

    def supports_tools(self):
        """Whether this provider supports tool calling."""
        return True

    def supports_vision(self):
        """Whether this provider supports image inputs."""
        return False


class LlmService(ServiceBase):
    """Shim that delegates to AiService for backward compatibility.

    Backend modules now register via AiService. Legacy callers that use
    ``services.llm.get_provider()`` or ``services.llm.stream()`` still work.
    """

    name = "llm"

    def __init__(self):
        self._ai = None
        self._config = None

    def set_config(self, config):
        self._config = config

    def set_ai_service(self, ai_service):
        """Wire the backing AiService (called during bootstrap)."""
        self._ai = ai_service

    def register_provider(self, name, provider):
        """Legacy registration — now a no-op (AI modules register via AiService)."""
        log.debug("LlmService.register_provider(%s) — delegated to AiService", name)

    def get_provider(self, name=None):
        """Get a provider by name, or the active one from config."""
        if self._ai:
            try:
                return self._ai.get_provider(capability="text",
                                             instance_id=name)
            except RuntimeError:
                return None
        return None

    def get_active_provider(self):
        """Get the active text provider (public convenience method)."""
        return self._get_active_provider()

    @property
    def available_providers(self):
        if self._ai:
            return [i.name for i in self._ai.list_instances("text")]
        return []

    def stream(self, messages, tools=None, **kwargs):
        """Stream via the active provider."""
        provider = self._get_active_provider()
        return provider.stream(messages, tools=tools, **kwargs)

    def complete(self, messages, tools=None, **kwargs):
        """Complete via the active provider."""
        provider = self._get_active_provider()
        return provider.complete(messages, tools=tools, **kwargs)

    def supports_tools(self):
        provider = self.get_provider()
        return provider.supports_tools() if provider else False

    # ── Internal ──────────────────────────────────────────────────────

    def _get_active_provider(self):
        if self._ai:
            return self._ai.get_provider("text")
        raise RuntimeError("No AI service configured")

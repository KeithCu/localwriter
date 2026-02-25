"""Ollama LLM provider.

Extends the OpenAI-compatible provider with Ollama-specific defaults.
Ollama exposes an OpenAI-compatible API at /v1/chat/completions since v0.1.14.
"""

import logging

from plugin.modules.ai_openai.provider import OpenAICompatProvider

log = logging.getLogger("localwriter.ai_ollama")


class OllamaProvider(OpenAICompatProvider):
    """Ollama-specific provider.

    Inherits everything from OpenAICompatProvider — Ollama's OpenAI
    compatibility layer uses the same /v1/chat/completions endpoint.
    """

    name = "ai_ollama"

    def _endpoint(self):
        return self._config.get("endpoint") or "http://localhost:11434"

    def _timeout(self):
        # Ollama may need longer for initial model loading
        return self._config.get("request_timeout") or 300

    def supports_tools(self):
        # Most Ollama models support tool calling
        return True

    def supports_vision(self):
        # Some Ollama models support vision (llava, etc.)
        return False

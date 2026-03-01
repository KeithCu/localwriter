"""Provider ABCs — contracts for LLM and image backends.

Backend modules (ai_openai, ai_ollama, ai_horde) implement these
interfaces and register with AiService.
"""

from abc import ABC, abstractmethod


class LlmProvider(ABC):
    """Interface that LLM backend modules implement and register."""

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

    def check(self):
        """Fast connectivity check — is the backend reachable?

        Returns:
            (bool, str): (reachable, error_message).
            Default: always OK (backward compat).
        """
        return (True, "")

    def warmup(self):
        """Pre-load the model. Called at startup or on instance switch.
        By default: no-op (provider is considered ready)."""
        pass

    def is_ready(self):
        """True if the provider is ready to receive requests."""
        return True

    def get_status(self):
        """Return status dict: {"ready": bool, "message": str, "model": str}"""
        return {"ready": True, "message": "Ready", "model": ""}


class ImageProvider(ABC):
    """Interface that image backend modules implement."""

    name: str = None

    @abstractmethod
    def generate(self, prompt, **kwargs):
        """Generate an image from a text prompt.

        Args:
            prompt: Text description of the image.
            **kwargs: width, height, model, strength, etc.

        Returns:
            (file_paths: list[str], error: str | None)
            file_paths is a list of generated image paths.
            error is None on success.
        """

    def check(self):
        """Fast connectivity check — is the backend reachable?

        Returns:
            (bool, str): (reachable, error_message).
            Default: always OK (backward compat).
        """
        return (True, "")

    def supports_editing(self):
        """Whether this provider supports image editing (img2img)."""
        return False

"""ImageService — interface and router for image generation backends.

Same pattern as LlmService: defines the contract, backend modules
(horde, endpoint, etc.) register providers.

Since the introduction of AiService, ImageService acts as a thin shim
that delegates to AiService for backward compatibility.
"""

import logging
from abc import ABC, abstractmethod

from plugin.framework.service_base import ServiceBase

log = logging.getLogger("localwriter.image")


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

    def supports_editing(self):
        """Whether this provider supports image editing (img2img)."""
        return False


class ImageService(ServiceBase):
    """Shim that delegates to AiService for backward compatibility."""

    name = "image"

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
        log.debug("ImageService.register_provider(%s) — delegated to AiService",
                  name)

    def get_provider(self, name=None):
        if self._ai:
            try:
                return self._ai.get_provider(capability="image",
                                             instance_id=name)
            except RuntimeError:
                return None
        return None

    @property
    def available_providers(self):
        if self._ai:
            return [i.name for i in self._ai.list_instances("image")]
        return []

    def generate(self, prompt, provider_name=None, **kwargs):
        """Generate an image via the specified or active provider.

        Returns:
            (file_paths: list[str], error: str | None)
        """
        if self._ai:
            try:
                provider = self._ai.get_provider(
                    capability="image", instance_id=provider_name)
            except RuntimeError as e:
                return [], str(e)
            return provider.generate(prompt, **kwargs)
        return [], "No AI service configured"

"""Dummy AI provider for testing — Homer Simpson mode."""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.ai_dummy")


class DummyModule(ModuleBase):
    """Registers a dummy LLM provider when enabled."""

    def initialize(self, services):
        self._services = services
        cfg = services.config.proxy_for(self.name)
        if not cfg.get("enabled"):
            return

        from plugin.modules.ai_dummy.provider import HomerProvider
        from plugin.modules.ai.service import AiInstance

        provider = HomerProvider(cfg)
        self._provider = provider
        services.ai.register_instance("ai.dummy:homer", AiInstance(
            name="Homer Simpson",
            module_name=self.name,
            provider=provider,
            capabilities={"text"},
        ))
        log.info("Homer Simpson provider registered (D'oh!)")

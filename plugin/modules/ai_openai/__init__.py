"""OpenAI-compatible LLM backend module."""

import json
import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.ai_openai")


class OpenAICompatModule(ModuleBase):
    """Registers OpenAI-compatible LLM + image provider instances."""

    def initialize(self, services):
        from plugin.modules.ai_openai.provider import OpenAICompatProvider
        from plugin.modules.ai.service import AiInstance
        from plugin.modules.ai.dict_config_proxy import DictConfigProxy
        cfg = services.config.proxy_for(self.name)
        ai = services.ai
        self._providers = []

        # Load JSON instances from config
        instances = self._load_instances(cfg)

        if instances:
            # Multi-instance from Options UI
            for inst_def in instances:
                proxy = DictConfigProxy(inst_def)
                provider = OpenAICompatProvider(proxy)
                self._providers.append(provider)
                inst_name = inst_def.get("name", "default")
                instance_id = "%s:%s" % (self.name, inst_name)
                ai.register_instance(instance_id, AiInstance(
                    name=inst_name,
                    module_name=self.name,
                    provider=provider,
                    capabilities={"text", "tools"},
                ))
        else:
            # Single instance from default_* config — only if endpoint set
            endpoint = cfg.get("default_endpoint", "")
            if endpoint:
                proxy = DictConfigProxy({
                    "endpoint": endpoint,
                    "model": cfg.get("default_model", ""),
                    "temperature": cfg.get("temperature", 0.7),
                    "max_tokens": cfg.get("max_tokens", 4096),
                    "request_timeout": cfg.get("request_timeout", 120),
                })
                provider = OpenAICompatProvider(proxy)
                self._providers.append(provider)
                ai.register_instance(self.name, AiInstance(
                    name="OpenAI Compatible",
                    module_name=self.name,
                    provider=provider,
                    capabilities={"text", "tools"},
                ))

        # Image provider — only if endpoint configured
        default_endpoint = cfg.get("default_endpoint", "")
        if default_endpoint:
            from plugin.modules.ai_openai.image_provider import (
                EndpointImageProvider)
            img_proxy = DictConfigProxy({
                "endpoint": default_endpoint,
            })
            img_provider = EndpointImageProvider(img_proxy)
            self._providers.append(img_provider)
            ai.register_instance("endpoint", AiInstance(
                name="Endpoint (image)",
                module_name=self.name,
                provider=img_provider,
                capabilities={"image"},
            ))

    def shutdown(self):
        for provider in getattr(self, "_providers", []):
            if hasattr(provider, "close"):
                provider.close()

    @staticmethod
    def _load_instances(cfg):
        """Parse the instances JSON from config. Returns list or None."""
        raw = cfg.get("instances", "[]")
        if not raw or raw == "[]":
            return None
        try:
            items = json.loads(raw)
            if isinstance(items, list) and items:
                return items
        except (json.JSONDecodeError, TypeError):
            log.warning("Invalid instances JSON in config")
        return None


def get_model_options(services):
    """Options provider for the OpenAI-compatible model select widgets."""
    options = [{"value": "", "label": "(none)"}]
    ai = services.get("ai")
    if ai:
        catalog = ai.get_model_catalog(
            providers=["openai", "openrouter", "together", "mistral"])
        for m in sorted(catalog.get("text", []),
                        key=lambda x: x.get("priority", 0), reverse=True):
            options.append({
                "value": m["id"],
                "label": m.get("display_name", m["id"]),
            })
    return options

"""Ollama local LLM backend module."""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.ai_ollama")


class OllamaModule(ModuleBase):
    """Registers Ollama LLM provider instances."""

    def initialize(self, services):
        from plugin.modules.ai_ollama.provider import OllamaProvider
        from plugin.modules.ai.service import AiInstance
        from plugin.modules.ai.dict_config_proxy import (
            DictConfigProxy, load_instances_json)
        cfg = services.config.proxy_for(self.name)
        ai = services.ai
        self._providers = []

        instances = load_instances_json(cfg)

        if instances:
            for inst_def in instances:
                proxy = DictConfigProxy(inst_def)
                provider = OllamaProvider(proxy)
                self._providers.append(provider)
                inst_name = inst_def.get("name", "default")
                instance_id = "%s:%s" % (self.name, inst_name)
                ai.register_instance(instance_id, AiInstance(
                    name=inst_name,
                    module_name=self.name,
                    provider=provider,
                    capabilities={"text", "tools"},
                ))

    def shutdown(self):
        for provider in getattr(self, "_providers", []):
            if hasattr(provider, "close"):
                provider.close()



def get_model_options(services):
    """Options provider for the Ollama model select widgets."""
    options = [{"value": "", "label": "(none)"}]
    ai = services.get("ai")
    if ai:
        catalog = ai.get_model_catalog(providers=["ollama"])
        for m in sorted(catalog.get("text", []),
                        key=lambda x: x.get("priority", 0), reverse=True):
            options.append({
                "value": m["id"],
                "label": m.get("display_name", m["id"]),
            })
    return options

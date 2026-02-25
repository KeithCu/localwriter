"""OpenAI-compatible LLM backend module."""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.ai_openai")


class OpenAICompatModule(ModuleBase):
    """Registers OpenAI-compatible LLM + image provider instances."""

    def initialize(self, services):
        from plugin.modules.ai_openai.provider import OpenAICompatProvider
        from plugin.modules.ai.service import AiInstance
        from plugin.modules.ai.dict_config_proxy import (
            DictConfigProxy, load_instances_json)
        cfg = services.config.proxy_for(self.name)
        ai = services.ai
        self._providers = []

        # Load JSON instances from config
        instances = load_instances_json(cfg)

        for inst_def in (instances or []):
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
            # Register a separate image provider if endpoint supports it
            if inst_def.get("image"):
                from plugin.modules.ai_openai.image_provider import (
                    EndpointImageProvider)
                img_provider = EndpointImageProvider(proxy)
                img_id = "%s:%s:image" % (self.name, inst_name)
                ai.register_instance(img_id, AiInstance(
                    name=inst_name + " (image)",
                    module_name=self.name,
                    provider=img_provider,
                    capabilities={"image"},
                ))

    def shutdown(self):
        for provider in getattr(self, "_providers", []):
            if hasattr(provider, "close"):
                provider.close()



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

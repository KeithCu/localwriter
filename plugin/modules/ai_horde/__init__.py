"""AI Horde image generation backend module."""

import json
import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.ai_horde")


def get_model_options(services):
    """Options provider for horde model select widgets."""
    # Built-in horde models
    options = [
        {"value": "stable_diffusion", "label": "Stable Diffusion"},
        {"value": "stable_diffusion_xl", "label": "SDXL"},
    ]
    # Add image models from the catalog (custom + default)
    ai = services.get("ai")
    if ai:
        seen = {o["value"] for o in options}
        catalog = ai.get_model_catalog()
        for m in catalog.get("image", []):
            if m["id"] not in seen:
                options.append({
                    "value": m["id"],
                    "label": m.get("display_name", m["id"]),
                })
                seen.add(m["id"])
    return options


class HordeModule(ModuleBase):
    """Registers AI Horde image provider instances."""

    def initialize(self, services):
        from plugin.modules.ai_horde.provider import HordeProvider
        from plugin.modules.ai.service import AiInstance
        from plugin.modules.ai.dict_config_proxy import DictConfigProxy
        cfg = services.config.proxy_for(self.name)
        ai = services.ai
        self._providers = []

        instances = self._load_instances(cfg)

        if instances:
            for inst_def in instances:
                proxy = DictConfigProxy(inst_def)
                provider = HordeProvider(proxy)
                self._providers.append(provider)
                inst_name = inst_def.get("name", "default")
                instance_id = "%s:%s" % (self.name, inst_name)
                ai.register_instance(instance_id, AiInstance(
                    name=inst_name,
                    module_name=self.name,
                    provider=provider,
                    capabilities={"image"},
                ))

    @staticmethod
    def _load_instances(cfg):
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

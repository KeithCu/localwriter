"""AI module — unified AI provider registry and model catalog."""

from plugin.framework.module_base import ModuleBase


class Module(ModuleBase):

    def initialize(self, services):
        from plugin.modules.ai.service import AiService

        ai = AiService()
        ai.set_config(services.config)
        services.register(ai)

        # Wire shims so legacy callers (services.llm / services.image) work
        llm_svc = services.get("llm")
        if llm_svc:
            llm_svc.set_ai_service(ai)
        image_svc = services.get("image")
        if image_svc:
            image_svc.set_ai_service(ai)

# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2024 John Balis
# Copyright (c) 2026 KeithCu (modifications and relicensing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""AI module — unified AI provider registry and model catalog."""

import logging
from plugin.framework.module_base import ModuleBase

log = logging.getLogger("writeragent.ai")


class Module(ModuleBase):

    def initialize(self, services):
        from plugin.modules.ai.service import AiService, AiInstance
        ai = AiService()
        ai.set_config(services.config)
        services.register(ai)
        self._services = services
        self._providers = []

        cfg = services.config.proxy_for("ai")

        # 1. OpenAI-compatible Provider
        from .providers.openai import OpenAICompatProvider, EndpointImageProvider
        openai_provider = OpenAICompatProvider(cfg)
        self._providers.append(openai_provider)
        ai.register_instance("openai", AiInstance(
            name="OpenAI Endpoint", module_name="ai", provider=openai_provider,
            capabilities={"text", "tools"}
        ))
        
        # OpenAI Image Provider
        openai_img_provider = EndpointImageProvider(cfg)
        ai.register_instance("openai_image", AiInstance(
            name="OpenAI Image", module_name="ai", provider=openai_img_provider,
            capabilities={"image"}
        ))

        # 2. Ollama Provider
        from .providers.ollama import OllamaProvider
        ollama_provider = OllamaProvider(cfg)
        self._providers.append(ollama_provider)
        ai.register_instance("ollama", AiInstance(
            name="Ollama", module_name="ai", provider=ollama_provider,
            capabilities={"text", "tools"}
        ))

        # 3. AI Horde Provider
        from .providers.horde import HordeProvider
        horde_provider = HordeProvider(cfg)
        self._providers.append(horde_provider)
        ai.register_instance("horde", AiInstance(
            name="AI Horde", module_name="ai", provider=horde_provider,
            capabilities={"image"}
        ))

    def shutdown(self):
        for provider in getattr(self, "_providers", []):
            if hasattr(provider, "close"):
                provider.close()


def get_openai_model_options(services):
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


def get_ollama_model_options(services):
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

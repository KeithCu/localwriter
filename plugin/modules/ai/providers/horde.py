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
"""AI Horde image generation provider.

Wraps the AiHordeClient to implement the ImageProvider ABC.
AI Horde is a free, crowdsourced image generation service.
"""

import logging

from plugin.modules.ai.provider_base import ImageProvider

log = logging.getLogger("writeragent.ai_horde")


class _HordeInformer:
    """Minimal informer bridge for AiHordeClient callbacks."""

    def __init__(self):
        self.last_error = ""
        self._status_callback = None

    def update_status(self, text, progress):
        msg = "Horde: %s (%s%%)" % (text, progress)
        log.info(msg)
        if self._status_callback:
            try:
                self._status_callback(msg)
            except Exception:
                pass

    def show_error(self, msg, **kwargs):
        log.error("Horde Error: %s", msg)
        self.last_error = msg

    def set_finished(self):
        pass

    def get_generated_image_url_status(self):
        return ["", 0, ""]

    def set_generated_image_url_status(self, *args):
        pass

    def get_toolkit(self):
        return None


class HordeProvider(ImageProvider):
    """AI Horde image generation via crowdsourced workers."""

    name = "ai_horde"

    def __init__(self, config_proxy):
        self._config = config_proxy
        self._client = None
        self._informer = _HordeInformer()

    def _get_client(self):
        if self._client is None:
            from plugin.contrib.aihordeclient import AiHordeClient

            self._client = AiHordeClient(
                client_version="1.0.0",
                url_version_update="",
                client_help_url="",
                client_download_url="",
                settings={},
                client_name="WriterAgent_Horde_Client",
                informer=self._informer,
            )
        return self._client

    def generate(self, prompt, **kwargs):
        """Generate an image via AI Horde.

        Returns:
            (file_paths: list[str], error: str | None)
        """
        api_key = self._config.get("horde_api_key") or "0000000000"
        model = kwargs.get("model") or self._config.get("horde_model") or "stable_diffusion"
        width = kwargs.get("width", 512)
        height = kwargs.get("height", 512)
        max_wait = kwargs.get("max_wait") or self._config.get("max_wait") or 5

        if kwargs.get("status_callback"):
            self._informer._status_callback = kwargs["status_callback"]

        options = {
            "prompt": prompt,
            "image_width": width,
            "image_height": height,
            "model": model,
            "api_key": api_key,
            "max_wait_minutes": max_wait,
            "steps": kwargs.get("steps", 30),
            "seed": kwargs.get("seed", ""),
            "nsfw": self._config.get("nsfw") or False,
            "censor_nsfw": not (self._config.get("nsfw") or False),
        }

        # img2img support
        source_image = kwargs.get("source_image")
        if source_image:
            options["source_image"] = source_image
            options["mode"] = "MODE_IMG2IMG"
            options["init_strength"] = kwargs.get("strength", 0.6)

        client = self._get_client()
        paths = []
        self._informer.last_error = ""

        try:
            paths = client.generate_image(options)
        except Exception:
            log.exception("AI Horde generation failed")

        error = self._informer.last_error if not paths else None
        return paths, error

    def supports_editing(self):
        return True

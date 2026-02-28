"""OpenAI-compatible image generation provider.

Uses the same endpoint/API key as the chat provider to call
/v1/images/generations (works with OpenAI, Together AI, etc.)
or modalities=["image"] for OpenRouter.
"""

import base64
import json
import logging
import re
import tempfile

from plugin.modules.ai.provider_base import ImageProvider

log = logging.getLogger("localwriter.ai_openai.image")


class EndpointImageProvider(ImageProvider):
    """Image generation via the configured OpenAI-compatible endpoint."""

    name = "endpoint"

    def __init__(self, config_proxy):
        self._config = config_proxy

    def generate(self, prompt, width=1024, height=1024, model=None, **kwargs):
        """Generate an image via /v1/images/generations.

        Returns:
            (file_paths: list[str], error: str | None)
        """
        from plugin.modules.ai.providers.openai import (
            OpenAICompatProvider, _format_http_error, _unverified_ssl)

        # Create a temporary provider instance for HTTP connection
        provider = OpenAICompatProvider(self._config)
        try:
            model_name = model or self._config.get("model") or ""
            body = {
                "prompt": prompt,
                "n": 1,
                "size": "%dx%d" % (width, height),
                "response_format": "url",
            }
            if model_name:
                body["model"] = model_name

            data = json.dumps(body).encode("utf-8")
            path = provider._api_path() + "/images/generations"
            headers = provider._headers()

            conn = provider._get_conn()
            try:
                conn.request("POST", path, body=data, headers=headers)
                resp = conn.getresponse()
            except Exception:
                provider.close()
                conn = provider._get_conn()
                conn.request("POST", path, body=data, headers=headers)
                resp = conn.getresponse()

            if resp.status != 200:
                err_body = resp.read().decode("utf-8", errors="replace")
                return [], _format_http_error(resp.status, resp.reason,
                                              err_body)

            result = json.loads(resp.read().decode("utf-8"))

            for img in (result.get("data") or []):
                b64 = img.get("b64_json")
                if b64:
                    return self._save_b64(b64), None
                url = img.get("url")
                if url:
                    if "data:image" in url:
                        match = re.search(
                            r'base64,([A-Za-z0-9+/=]+)', url)
                        if match:
                            return self._save_b64(match.group(1)), None
                    return self._save_url(url), None

            return [], "No image data in response"
        except Exception as e:
            log.exception("Image generation failed")
            return [], str(e)
        finally:
            provider.close()

    @staticmethod
    def _save_b64(b64_data):
        with tempfile.NamedTemporaryFile(
                delete=False, suffix=".png") as tmp:
            tmp.write(base64.b64decode(b64_data))
            return [tmp.name]

    @staticmethod
    def _save_url(url):
        from plugin.framework.http import sync_request
        with tempfile.NamedTemporaryFile(
                delete=False, suffix=".webp") as tmp:
            tmp.write(sync_request(url, parse_json=False))
            return [tmp.name]

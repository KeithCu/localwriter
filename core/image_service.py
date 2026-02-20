"""Unified Image Generation Service for LocalWriter."""
import json
import logging
import time
import tempfile
import urllib.request
import urllib.parse
from pathlib import Path
from core.api import LlmClient
from core.aihordeclient import AiHordeClient

logger = logging.getLogger(__name__)

class ImageProvider:
    def generate(self, prompt, **kwargs):
        raise NotImplementedError()

class EndpointImageProvider(ImageProvider):
    """Uses the endpoint URL and API key from Settings (same as chat). Model from image_model or text model."""

    def __init__(self, api_config, ctx):
        self.client = LlmClient(api_config, ctx)
        self.model = api_config.get("model", "openai/gpt-4o-mini")

    def generate(self, prompt, width=512, height=512, model=None, **kwargs):
        """Request image via the configured endpoint (modalities=['image'] where supported)."""
        model = model or self.model
        messages = [{"role": "user", "content": prompt}]

        logger.info("Requesting image via endpoint: %s", model)

        method, path, body, headers = self.client.make_chat_request(messages, max_tokens=1000)
        body_dict = json.loads(body)
        body_dict["modalities"] = ["image"]
        if "max_tokens" in kwargs:
            body_dict["max_tokens"] = kwargs["max_tokens"]

        response = self.client.request_with_tools(messages, body_override=json.dumps(body_dict))

        # Parse response: OpenRouter etc. may put image in message.images[].image_url.url
        images = response.get("images") or []
        if images:
            import re
            import base64
            img = images[0]
            url = None
            if isinstance(img, dict):
                if "image_url" in img and isinstance(img["image_url"], dict):
                    url = img["image_url"].get("url")
                elif "image_url" in img and isinstance(img["image_url"], str):
                    url = img["image_url"]
            if url and "data:image" in url:
                match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', url)
                if match:
                    data = match.group(1)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(base64.b64decode(data))
                        return [tmp.name]
            if url and url.startswith("http"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".webp") as tmp:
                    urllib.request.urlretrieve(url, tmp.name)
                    return [tmp.name]

        # Fallback: image in content string (some endpoints)
        content = response.get("content") or ""
        if "data:image" in content:
            import re
            import base64
            match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', content)
            if match:
                data = match.group(1)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(base64.b64decode(data))
                    return [tmp.name]
        if content and content.strip().startswith("http"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webp") as tmp:
                urllib.request.urlretrieve(content.strip(), tmp.name)
                return [tmp.name]

        return []

class AIHordeImageProvider(ImageProvider):
    def __init__(self, config, ctx):
        self.ctx = ctx
        self.config = config
        self.api_key = config.get("aihorde_api_key", "0000000000")
        # We need a minimal "informer" to bridge AIHordeClient's callbacks
        class SimpleInformer:
            def __init__(self, callback_context, ctx):
                self.outer_ctx = callback_context
                self.toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)

            def update_status(self, text, progress): 
                msg = f"Horde: {text} ({progress}%)"
                logger.info(msg)
                if self.outer_ctx.get("status_callback"):
                    try:
                        self.outer_ctx["status_callback"](msg)
                    except Exception:
                        pass

            def show_error(self, msg, **kwargs): 
                logger.error(f"Horde Error: {msg}")
                if self.outer_ctx.get("status_callback"):
                    try:
                        self.outer_ctx["status_callback"](f"Error: {msg}")
                    except Exception:
                        pass

            def set_finished(self): pass
            def get_generated_image_url_status(self): return ["", 0, ""]
            def set_generated_image_url_status(self, *args): pass

            def get_toolkit(self):
                return self.toolkit

        # Pass context dict so we can inject callback later if needed, 
        # or just pass it in constructor if we rebuild every time.
        # But here we are in __init__, so we store the dict.
        self.callback_context = {"status_callback": None}
        
        self.client = AiHordeClient(
            client_version="1.0.0",
            url_version_update="",
            client_help_url="",
            client_download_url="",
            settings=config,
            client_name="LocalWriter_Horde_Client",
            informer=SimpleInformer(self.callback_context, self.ctx)
        )
        # We need to manually inject the toolkit because SimpleInformer.__init__ 
        # expects an object with ServiceManager if we passed ctx directly.
        # Actually SimpleInformer above takes outer_ctx which is expected to be the UNO component context.
        # Let's fix SimpleInformer to take (ctx, callback_dict).
        
    def generate(self, prompt, width=512, height=512, model="stable_diffusion", source_image=None, status_callback=None, **kwargs):
        # Update the callback in the context shared with the informer
        if status_callback:
            self.callback_context["status_callback"] = status_callback
            
        options = {
            "prompt": prompt,
            "image_width": width,
            "image_height": height,
            "model": model,
            "api_key": self.api_key,
            "max_wait_minutes": kwargs.get("max_wait", 5),
            "prompt_strength": kwargs.get("strength", 0.6), # LOSHD uses 1 - init_strength
            "steps": kwargs.get("steps", 30),
            "seed": kwargs.get("seed", ""),
            "nsfw": kwargs.get("nsfw", False),
            "censor_nsfw": kwargs.get("censor_nsfw", True),
        }
        if source_image:
            options["source_image"] = source_image
            options["mode"] = "MODE_IMG2IMG" # AIHordeClient constant
            options["init_strength"] = kwargs.get("strength", 0.6)

        # AiHordeClient.generate_image is blocking and handles polling internally
        paths = self.client.generate_image(options)
        return paths

class ImageService:
    def __init__(self, ctx, config):
        self.ctx = ctx
        self.config = config
        self.providers = {}

    def get_provider(self, name):
        # Legacy: treat "openrouter" as "endpoint" so old configs keep working
        if name == "openrouter":
            name = "endpoint"
        if name == "aihorde":
            return AIHordeImageProvider(self.config, self.ctx)
        if name == "endpoint":
            from core.config import get_api_config, get_text_model
            api_config = get_api_config(self.ctx).copy()
            api_config["model"] = (self.config.get("image_model") or "").strip() or get_text_model(self.ctx)
            return EndpointImageProvider(api_config, self.ctx)
        return None

    def generate_image(self, prompt, provider_name=None, status_callback=None, **kwargs):
        if not provider_name:
            provider_name = self.config.get("image_provider", "aihorde")
            
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")
            
        # Merge configuration defaults with kwargs
        defaults = {
            "width": self.config.get("image_width", 512),
            "height": self.config.get("image_height", 512),
            "strength": self.config.get("image_cfg_scale", 7.5),
            "steps": self.config.get("image_steps", 30),
            "nsfw": self.config.get("image_nsfw", False),
            "censor_nsfw": self.config.get("image_censor_nsfw", True),
            "nsfw": self.config.get("image_nsfw", False),
            "censor_nsfw": self.config.get("image_censor_nsfw", True),
            "max_wait": self.config.get("image_max_wait", 5),
        }
        
        # Provider-specific defaults
        if provider_name == "aihorde":
            defaults["model"] = self.config.get("aihorde_model", "stable_diffusion")

        # Special case: prompt translation
        if self.config.get("image_translate_prompt", True):
            # We could add translation logic here if needed, 
            # or let the provider handle it. LOSHD has it.
            pass
            
        for k, v in defaults.items():
            if k not in kwargs:
                kwargs[k] = v

        # Optional: translate prompt to English when image_translate_prompt is True and source language is set
        if self.config.get("image_translate_prompt", True):
            src_lang = (self.config.get("image_translate_from") or "").strip()
            if src_lang:
                try:
                    from core.translation_tool import opustm_hf_translate
                    prompt = opustm_hf_translate(prompt, src_lang, "English")
                except Exception as e:
                    logger.warning("Prompt translation failed, using original: %s", e)

        return provider.generate(prompt, status_callback=status_callback, **kwargs)

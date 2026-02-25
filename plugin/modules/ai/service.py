"""AiService — unified AI provider registry with capability-based routing.

Replaces the separate LlmService/ImageService routers with a single
service that manages N provider instances, each annotated with capabilities.
Supports multi-instance registration (YAML config) and a merged model catalog.
"""

import json
import logging

from plugin.framework.service_base import ServiceBase
from plugin.lib.default_models import (
    DEFAULT_MODELS, merge_catalogs, resolve_model_id,
)

log = logging.getLogger("localwriter.ai")


class AiInstance:
    """One AI provider instance with metadata."""

    __slots__ = ("name", "module_name", "provider", "capabilities")

    def __init__(self, name, module_name, provider, capabilities=None):
        self.name = name
        self.module_name = module_name
        self.provider = provider
        self.capabilities = set(capabilities or ())


class AiService(ServiceBase):
    """Unified AI provider registry with capability-based routing.

    Instance ID convention:
      - Single instance (flat config): ``"ai_openai"`` (= module name)
      - Multi-instance (YAML):         ``"ai_openai:OpenAI Pro"``
    """

    name = "ai"

    def __init__(self):
        self._instances = {}       # instance_id -> AiInstance
        self._global_models = []   # flat list of model dicts from YAML
        self._config = None
        self._active = {}          # volatile: capability -> instance_id

    def set_config(self, config):
        self._config = config
        self._load_global_models()

    # -- Instance registration -------------------------------------------------

    def register_instance(self, instance_id, ai_instance):
        """Register an AI provider instance."""
        self._instances[instance_id] = ai_instance
        log.info("AI instance registered: %s (caps=%s)",
                 instance_id, ",".join(sorted(ai_instance.capabilities)))

    def unregister_instance(self, instance_id):
        """Remove an AI provider instance."""
        self._instances.pop(instance_id, None)

    # -- Instance lookup -------------------------------------------------------

    def get_instance(self, capability=None, instance_id=None):
        """Get an AiInstance by explicit ID or active selection.

        Args:
            capability: Required capability ("text", "image", "tools", ...).
            instance_id: Explicit instance ID. If None, uses config selection.

        Returns:
            AiInstance or None.
        """
        if instance_id:
            inst = self._instances.get(instance_id)
            if inst and (capability is None or capability in inst.capabilities):
                return inst
            return None

        # Active selection from config
        active_id = self._get_active_instance_id(capability)
        if active_id:
            inst = self._instances.get(active_id)
            if inst and (capability is None or capability in inst.capabilities):
                return inst

        # Fallback: first instance with the requested capability
        if capability:
            for inst in self._instances.values():
                if capability in inst.capabilities:
                    return inst
        elif self._instances:
            return next(iter(self._instances.values()))

        return None

    def get_provider(self, capability=None, instance_id=None):
        """Get the provider object for a capability.

        Raises RuntimeError if no suitable provider is found.
        """
        inst = self.get_instance(capability=capability, instance_id=instance_id)
        if inst is None:
            available = ", ".join(self._instances.keys()) or "(none)"
            raise RuntimeError(
                "No AI provider for capability '%s'. Available: %s"
                % (capability, available)
            )
        return inst.provider

    def list_instances(self, capability=None):
        """List all instances, optionally filtered by capability."""
        if capability is None:
            return list(self._instances.values())
        return [i for i in self._instances.values()
                if capability in i.capabilities]

    def providers_for(self, capability):
        """Return [(instance_id, AiInstance)] for a capability."""
        return [(iid, inst) for iid, inst in self._instances.items()
                if capability in inst.capabilities]

    # -- Convenience delegates -------------------------------------------------

    def stream(self, messages, tools=None, **kwargs):
        """Stream via the active text provider."""
        return self.get_provider("text").stream(messages, tools=tools, **kwargs)

    def complete(self, messages, tools=None, **kwargs):
        """Complete via the active text provider."""
        return self.get_provider("text").complete(messages, tools=tools, **kwargs)

    def generate_image(self, prompt, **kwargs):
        """Generate an image via the active image provider."""
        return self.get_provider("image").generate(prompt, **kwargs)

    # -- Model catalog ---------------------------------------------------------

    def _load_global_models(self):
        """Load the global YAML models file from ai.models_file config."""
        if not self._config:
            return
        from plugin.modules.ai.yaml_loader import load_ai_config
        yaml_path = self._config.get("ai.models_file", caller_module=None) or ""
        yaml_data = load_ai_config(yaml_path)
        if yaml_data and yaml_data.get("models"):
            self._global_models = yaml_data["models"]
            log.info("Global model catalog loaded: %d models",
                     len(self._global_models))

    def _load_custom_models(self):
        """Load custom models from ai.custom_models config (JSON list).

        Converts the ``providers`` comma-separated field into an ``ids``
        dict so the model is only visible to the listed providers.
        """
        if not self._config:
            return []
        raw = self._config.get("ai.custom_models", caller_module=None) or "[]"
        if not raw or raw == "[]":
            return []
        try:
            items = json.loads(raw)
            if not isinstance(items, list):
                return []
            result = []
            for m in items:
                if not isinstance(m, dict) or not m.get("id"):
                    continue
                providers_str = m.pop("providers", "")
                if providers_str:
                    providers = [p.strip() for p in
                                 providers_str.split(",") if p.strip()]
                    if providers:
                        m["ids"] = {p: m["id"] for p in providers}
                result.append(m)
            return result
        except (json.JSONDecodeError, TypeError):
            log.warning("Invalid custom_models JSON in config")
        return []

    def get_model_catalog(self, providers=None):
        """Return the merged model catalog filtered by providers.

        Merges DEFAULT_MODELS + global YAML + custom models, then filters
        by the requested provider keys.

        Args:
            providers: list of provider keys (e.g. ``["openai", "openrouter"]``),
                       or None for all models.

        Returns:
            ``{"text": [model_dicts], "image": [model_dicts]}``
            Each model dict has a resolved ``"id"`` for the matching provider.
        """
        # Build flat catalog: defaults + YAML + custom
        catalog = list(DEFAULT_MODELS)
        if self._global_models:
            merge_catalogs(catalog, self._global_models)
        custom = self._load_custom_models()
        if custom:
            merge_catalogs(catalog, custom)

        # Filter and split by capability
        result = {"text": [], "image": []}
        seen = {"text": set(), "image": set()}

        for model in catalog:
            # Resolve ID for the provider filter
            resolved_id = None
            if providers:
                for p in providers:
                    resolved_id = resolve_model_id(model, p)
                    if resolved_id:
                        break
                if not resolved_id:
                    continue
            else:
                resolved_id = model.get("id")
                if not resolved_id:
                    ids = model.get("ids")
                    if ids:
                        resolved_id = next(iter(ids.values()))
                if not resolved_id:
                    continue

            # Split by capabilities
            caps = [c.strip() for c in
                    model.get("capability", "text").split(",") if c.strip()]
            for cap in caps:
                if cap in result and resolved_id not in seen[cap]:
                    entry = dict(model)
                    entry["id"] = resolved_id
                    result[cap].append(entry)
                    seen[cap].add(resolved_id)

        return result

    # -- Active selection ------------------------------------------------------

    def set_active_instance(self, capability, instance_id):
        """Set volatile active instance for a capability (not persisted)."""
        cap = "image" if capability in ("image",) else "text"
        self._active[cap] = instance_id
        log.info("Active %s instance set to: %s", cap, instance_id or "(auto)")

    def get_active_instance(self, capability):
        """Return the volatile active instance ID, or None if not set."""
        cap = "image" if capability in ("image",) else "text"
        return self._active.get(cap)

    def get_instance_status(self, instance_id):
        """Return status dict for a specific instance."""
        inst = self._instances.get(instance_id)
        if inst is None:
            return {"ready": False, "message": "Unknown instance", "model": ""}
        return inst.provider.get_status()

    def get_active_status(self, capability):
        """Return status dict for the active instance of a capability."""
        inst = self.get_instance(capability=capability)
        if inst is None:
            return {"ready": False, "message": "No provider", "model": ""}
        return inst.provider.get_status()

    def _get_active_instance_id(self, capability):
        """Return the active instance: volatile first, then config default."""
        cap = "image" if capability in ("image",) else "text"
        # Volatile override (from sidebar)
        val = self._active.get(cap)
        if val is not None:
            return val
        # Fall back to config default
        if not self._config:
            return ""
        if cap == "image":
            key = "ai.default_image_instance"
        else:
            key = "ai.default_text_instance"
        return self._config.get(key, caller_module=None) or ""


def _instance_label(inst):
    """Format instance label as '[Provider] Name (model)'."""
    provider = inst.module_name.rsplit(".", 1)[-1] if inst.module_name else "?"
    name = inst.name or inst.module_name or "?"
    model = ""
    try:
        cfg = getattr(inst.provider, "_config", None)
        if cfg:
            model = cfg.get("model") or ""
    except Exception:
        pass
    if model:
        # Shorten long model ids: keep last segment after /
        short = model.rsplit("/", 1)[-1] if "/" in model else model
        return "[%s] %s (%s)" % (provider, name, short)
    return "[%s] %s" % (provider, name)


def get_text_instance_options(services):
    """Options provider for the ai.default_text_instance config select widget."""
    ai = services.get("ai")
    if not ai:
        return []
    options = [{"value": "", "label": "(auto)"}]
    for iid, inst in ai._instances.items():
        if "text" in inst.capabilities:
            options.append({"value": iid, "label": _instance_label(inst)})
    return options


def get_image_instance_options(services):
    """Options provider for the ai.default_image_instance config select widget."""
    ai = services.get("ai")
    if not ai:
        return []
    options = [{"value": "", "label": "(auto)"}]
    for iid, inst in ai._instances.items():
        if "image" in inst.capabilities:
            options.append({"value": iid, "label": _instance_label(inst)})
    return options

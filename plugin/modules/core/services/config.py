"""ConfigService — namespaced config via LO's native configuration registry.

Uses the XCS/XCU schema files generated at build time.  Each module's config
lives in the LO registry under ``/org.localwriter.<module>.<Group>/<Group>``.

Access control:
  - Read own keys: always OK
  - Read other module's public keys: OK
  - Read other module's private keys: ConfigAccessError
  - Write own keys: OK
  - Write other module's keys: ConfigAccessError
"""

import logging
import os

from plugin.framework.service_base import ServiceBase
from plugin.framework.uno_context import get_ctx

log = logging.getLogger("localwriter.config")


class ConfigAccessError(Exception):
    """Raised when a module tries to access a private config key."""


class ConfigService(ServiceBase):
    name = "config"

    def __init__(self):
        self._defaults = {}   # "module.key" -> default_value
        self._manifest = {}   # "module.key" -> field schema
        self._events = None   # EventBus, set after init

    def initialize(self, ctx):
        # ctx is no longer stored — we use get_ctx() for fresh context
        pass

    def set_events(self, events):
        """Wire the event bus (called during bootstrap after events service)."""
        self._events = events

    def set_manifest(self, manifest):
        """Load config schemas from the merged manifest.

        Args:
            manifest: dict of {module_name: module_dict} from _manifest.py.
        """
        self._module_names = set(manifest.keys())

        for mod_name, mod_data in manifest.items():
            for field_name, schema in mod_data.get("config", {}).items():
                full_key = f"{mod_name}.{field_name}"
                self._defaults[full_key] = schema.get("default")
                self._manifest[full_key] = schema

        self._apply_env_overrides()

    def register_default(self, key, default):
        """Register a single default value."""
        self._defaults[key] = default

    # ── Read/Write ────────────────────────────────────────────────────

    def get(self, key, caller_module=None):
        """Get a config value from the LO registry, fallback to defaults."""
        self._check_read_access(key, caller_module)
        val = self._registry_read(key)
        if val is not None:
            return val
        return self._defaults.get(key)

    def get_dict(self):
        """Return all config values as a flat dict (no access control)."""
        result = dict(self._defaults)
        for key in self._defaults:
            val = self._registry_read(key)
            if val is not None:
                result[key] = val
        return result

    def set(self, key, value, caller_module=None):
        """Set a config value in the LO registry and emit config:changed."""
        self._check_write_access(key, caller_module)
        old_value = self.get(key)
        self._registry_write(key, value)

        if self._events and value != old_value:
            self._events.emit(
                "config:changed", key=key, value=value, old_value=old_value
            )

    def set_batch(self, changes, old_values=None):
        """Write all values and emit a config:changed event.

        Args:
            changes: dict of {full_key: new_value}.
            old_values: optional dict of {full_key: old_value} for diff detection.
                        If not provided, no diff filtering is done.

        Always writes all values (LO registry requires explicit commit).
        Emits ``config:changed`` with diffs if old_values provided.
        """
        # Group by nodepath for batch commit
        by_node = {}
        for key, new_value in changes.items():
            nodepath, field_name = self._registry_nodepath(key)
            by_node.setdefault(nodepath, []).append(
                (field_name, key, new_value))

        for nodepath, fields in by_node.items():
            self._registry_write_node(nodepath, fields)

        # Compute diffs for event
        diffs = []
        if old_values:
            for key, new_value in changes.items():
                old_value = old_values.get(key)
                if new_value != old_value:
                    diffs.append({
                        "key": key,
                        "value": new_value,
                        "old_value": old_value,
                    })

        if diffs:
            if self._events:
                self._events.emit("config:changed", changes=diffs)
            log.info("Config batch: %d change(s)", len(diffs))

        return diffs

    def remove(self, key, caller_module=None):
        """Reset a config key to its default by writing the default value."""
        self._check_write_access(key, caller_module)
        default = self._defaults.get(key)
        if default is not None:
            self._registry_write(key, default)

    # ── Access control ────────────────────────────────────────────────

    def _check_read_access(self, key, caller_module):
        if caller_module is None:
            return
        if "." not in key:
            return
        module, _ = self._parse_key(key)
        if module == caller_module:
            return
        schema = self._manifest.get(key, {})
        if not schema.get("public", False):
            raise ConfigAccessError(
                f"Module '{caller_module}' cannot read private config '{key}'"
            )

    def _check_write_access(self, key, caller_module):
        if caller_module is None:
            return
        if "." not in key:
            return
        module, _ = self._parse_key(key)
        if module != caller_module:
            raise ConfigAccessError(
                f"Module '{caller_module}' cannot write to '{key}'"
            )

    # ── Environment overrides ────────────────────────────────────────

    def _apply_env_overrides(self):
        """Apply config overrides from LOCALWRITER_SET_CONFIG env var.

        Format: "key=value,key=value,..."
        Values are coerced to the type declared in the module schema.
        Overrides are written to the LO registry.
        """
        raw = os.environ.get("LOCALWRITER_SET_CONFIG", "").strip()
        if not raw:
            return

        count = 0
        for pair in raw.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, raw_value = pair.split("=", 1)
            key = key.strip()
            raw_value = raw_value.strip()

            value = self._coerce_value(key, raw_value)
            self._registry_write(key, value)
            count += 1
            log.info("Config override: %s = %r", key, value)

        if count:
            log.info("Applied %d config override(s) from LOCALWRITER_SET_CONFIG",
                     count)

    def _coerce_value(self, key, raw):
        """Coerce a string value to the type declared in the manifest schema."""
        schema = self._manifest.get(key, {})
        declared_type = schema.get("type", "string")

        if declared_type == "boolean":
            return raw.lower() in ("true", "1", "yes", "on")
        if declared_type == "int":
            try:
                return int(raw)
            except ValueError:
                return raw
        if declared_type == "float":
            try:
                return float(raw)
            except ValueError:
                return raw
        return raw

    # ── Key parsing ────────────────────────────────────────────────────

    def _parse_key(self, key):
        """Split a full key into (module_name, field_name).

        Uses longest-prefix match against known module names so that
        "tunnel.ngrok.authtoken" correctly splits to ("tunnel.ngrok", "authtoken").
        Falls back to simple first-dot split if no module names are known.
        """
        if hasattr(self, "_module_names") and self._module_names:
            # Try longest match first
            parts = key.split(".")
            for i in range(len(parts) - 1, 0, -1):
                candidate = ".".join(parts[:i])
                if candidate in self._module_names:
                    return candidate, ".".join(parts[i:])
        # Fallback: simple split
        return key.split(".", 1)

    # ── LO Registry I/O ──────────────────────────────────────────────

    def _registry_nodepath(self, key):
        """Convert "module.field" to (nodepath, field_name) for LO registry."""
        module_name, field_name = self._parse_key(key)
        safe = module_name.replace(".", "_")
        nodepath = f"/org.localwriter.{safe}.{safe}/{safe}"
        return nodepath, field_name

    def _registry_read(self, key):
        """Read a single value from the LO configuration registry."""
        ctx = get_ctx()
        if not ctx or "." not in key:
            return None
        try:
            from com.sun.star.beans import PropertyValue
            nodepath, field_name = self._registry_nodepath(key)
            provider = ctx.ServiceManager.createInstanceWithContext(
                "com.sun.star.configuration.ConfigurationProvider", ctx)
            args = (PropertyValue("nodepath", 0, nodepath, 0),)
            access = provider.createInstanceWithArguments(
                "com.sun.star.configuration.ConfigurationAccess", args)
            val = access.getPropertyValue(field_name)
            schema = self._manifest.get(key, {})
            result = self._coerce_registry_value(val, schema)
            log.debug("Registry read: %s = %r (path=%s)", key, result, nodepath)
            return result
        except Exception:
            log.debug("Registry read failed: %s (path=%s/%s)",
                      key, *self._registry_nodepath(key))
            return None

    def _registry_write(self, key, value):
        """Write a single value to the LO configuration registry."""
        ctx = get_ctx()
        if not ctx or "." not in key:
            return
        try:
            nodepath, field_name = self._registry_nodepath(key)
            self._registry_write_node(nodepath, [(field_name, key, value)])
        except Exception:
            log.exception("Failed to write registry: %s = %r", key, value)

    def _registry_write_node(self, nodepath, fields):
        """Write multiple fields to a single registry node with one commit.

        Args:
            nodepath: LO registry node path
            fields: list of (field_name, full_key, value) tuples
        """
        ctx = get_ctx()
        if not ctx:
            return
        try:
            from com.sun.star.beans import PropertyValue
            provider = ctx.ServiceManager.createInstanceWithContext(
                "com.sun.star.configuration.ConfigurationProvider", ctx)
            args = (PropertyValue("nodepath", 0, nodepath, 0),)
            update = provider.createInstanceWithArguments(
                "com.sun.star.configuration.ConfigurationUpdateAccess", args)
            for field_name, full_key, value in fields:
                update.setPropertyValue(field_name, value)
                log.debug("Registry set: %s = %r (path=%s)", full_key, value, nodepath)
            update.commitChanges()
            log.debug("Registry commit: %s (%d fields)", nodepath, len(fields))
        except Exception:
            log.exception("Failed to write registry node: %s", nodepath)

    def _coerce_registry_value(self, val, schema):
        """Coerce LO registry value to the expected Python type."""
        if val is None:
            return None
        declared_type = schema.get("type", "string")
        try:
            if declared_type == "boolean":
                return bool(val)
            if declared_type == "int":
                return int(val)
            if declared_type == "float":
                return float(val)
            return str(val)
        except (ValueError, TypeError):
            return val

    # ── Module proxy factory ──────────────────────────────────────────

    def proxy_for(self, module_name):
        """Create a ModuleConfigProxy scoped to *module_name*."""
        return ModuleConfigProxy(self, module_name)


class ModuleConfigProxy:
    """Scoped config access for a single module.

    When ``get("port")`` is called (no dot), it auto-prefixes with the
    module name -> ``"mcp.port"``.

    Cross-module reads require the full key: ``get("ai_openai.endpoint")``.
    """

    __slots__ = ("_config", "_module")

    def __init__(self, config_service, module_name):
        self._config = config_service
        self._module = module_name

    def get(self, key, default=None):
        if "." not in key:
            key = f"{self._module}.{key}"
        try:
            val = self._config.get(key, caller_module=self._module)
            return val if val is not None else default
        except ConfigAccessError:
            raise
        except Exception:
            return default

    def set(self, key, value):
        if "." not in key:
            key = f"{self._module}.{key}"
        self._config.set(key, value, caller_module=self._module)

    def remove(self, key):
        if "." not in key:
            key = f"{self._module}.{key}"
        self._config.remove(key, caller_module=self._module)

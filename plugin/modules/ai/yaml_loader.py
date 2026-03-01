"""YAML model catalog loader.

Loads a YAML file that overrides or extends the built-in model catalog
(default_models.py). Instances/accounts are managed via the LO Options
UI (list_detail widget), not via YAML.

Returns None on any error (graceful fallback to built-in catalog).

Supports two formats:

**New flat format** (preferred)::

    models:
      - id: "my-finetuned"
        display_name: "My Fine-tuned Model"
        capability: text
        context_length: 32000
        ids:
          openrouter: "my-org/my-finetuned"

**Old grouped format** (backward-compatible)::

    models:
      text:
        - id: "my-finetuned"
          display_name: "My Fine-tuned Model"
          context_length: 32000
      image:
        - id: "dall-e-3"
          display_name: "DALL-E 3"
"""

import logging
import os

log = logging.getLogger("localwriter.yaml_loader")


def load_ai_config(yaml_path):
    """Load an AI model catalog YAML file.

    Args:
        yaml_path: Path to the YAML file. May be empty/None.

    Returns:
        {"models": [flat_list]} or None on error/empty.
    """
    if not yaml_path or not isinstance(yaml_path, str):
        return None

    yaml_path = os.path.expanduser(yaml_path.strip())
    if not yaml_path or not os.path.isfile(yaml_path):
        if yaml_path:
            log.debug("Models file not found: %s", yaml_path)
        return None

    try:
        import yaml
    except ImportError:
        log.warning("PyYAML not available — cannot load models file")
        return None

    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        log.exception("Failed to parse models file: %s", yaml_path)
        return None

    if not isinstance(data, dict):
        log.warning("Models file is not a dict: %s", yaml_path)
        return None

    models = data.get("models")
    if models is None:
        log.debug("Models file has no 'models' key: %s", yaml_path)
        return None

    if isinstance(models, list):
        # New flat format — validate entries
        result = [m for m in models
                  if isinstance(m, dict) and (m.get("id") or m.get("ids"))]
        if not result:
            log.debug("Models file list is empty after validation: %s",
                      yaml_path)
            return None
        log.info("Loaded models file (flat): %s (%d models)",
                 yaml_path, len(result))
        return {"models": result}

    if isinstance(models, dict):
        # Old grouped format — convert to flat list
        result = []
        for cap, entries in models.items():
            if not isinstance(entries, list):
                continue
            for m in entries:
                if isinstance(m, dict) and m.get("id"):
                    entry = dict(m)
                    entry.setdefault("capability", cap)
                    result.append(entry)
        if not result:
            log.debug("Models file dict is empty after conversion: %s",
                      yaml_path)
            return None
        log.info("Loaded models file (grouped): %s (%d models)",
                 yaml_path, len(result))
        return {"models": result}

    log.warning("Models file 'models' is neither list nor dict: %s",
                yaml_path)
    return None

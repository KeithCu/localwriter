import json
from plugin.framework.logging import debug_log

def _err(message):
    return json.dumps({"status": "error", "message": message})

def tool_list_styles(model, ctx, args):
    """List available styles in the document."""
    family = args.get("family", "ParagraphStyles")
    try:
        families = model.getStyleFamilies()
        if not families.hasByName(family):
            available = list(families.getElementNames())
            return json.dumps({"status": "error",
                               "message": "Unknown style family: %s" % family,
                               "available_families": available})
        style_family = families.getByName(family)
        styles = []
        for name in style_family.getElementNames():
            style = style_family.getByName(name)
            entry = {
                "name": name,
                "is_user_defined": style.isUserDefined(),
                "is_in_use": style.isInUse(),
            }
            try:
                entry["parent_style"] = style.getPropertyValue("ParentStyle")
            except Exception:
                pass
            styles.append(entry)
        return json.dumps({"status": "ok", "family": family,
                           "styles": styles, "count": len(styles)})
    except Exception as e:
        debug_log("tool_list_styles error: %s" % e, context="Chat")
        return _err(str(e))

def tool_get_style_info(model, ctx, args):
    """Get detailed properties of a named style."""
    style_name = args.get("style_name", "")
    family = args.get("family", "ParagraphStyles")
    if not style_name:
        return _err("style_name is required")
    try:
        families = model.getStyleFamilies()
        if not families.hasByName(family):
            return _err("Unknown style family: %s" % family)
        style_family = families.getByName(family)
        if not style_family.hasByName(style_name):
            return json.dumps({"status": "error",
                               "message": "Style '%s' not found in %s" % (style_name, family)})
        style = style_family.getByName(style_name)
        info = {
            "name": style_name,
            "family": family,
            "is_user_defined": style.isUserDefined(),
            "is_in_use": style.isInUse(),
        }
        props_to_read = {
            "ParagraphStyles": [
                "ParentStyle", "FollowStyle",
                "CharFontName", "CharHeight", "CharWeight",
                "ParaAdjust", "ParaTopMargin", "ParaBottomMargin",
            ],
            "CharacterStyles": [
                "ParentStyle", "CharFontName", "CharHeight",
                "CharWeight", "CharPosture", "CharColor",
            ],
        }
        for prop_name in props_to_read.get(family, []):
            try:
                info[prop_name] = style.getPropertyValue(prop_name)
            except Exception:
                pass
        return json.dumps({"status": "ok", **info})
    except Exception as e:
        debug_log("tool_get_style_info error: %s" % e, context="Chat")
        return _err(str(e))

STYLES_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_styles",
            "description": (
                "List available styles in the document. Call this before applying styles "
                "with apply_document_content to discover exact style names (they may be "
                "localized). family defaults to ParagraphStyles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "family": {
                        "type": "string",
                        "description": "Style family to list.",
                        "enum": ["ParagraphStyles", "CharacterStyles",
                                 "PageStyles", "FrameStyles", "NumberingStyles"],
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_style_info",
            "description": "Get detailed properties of a specific style (font, size, margins, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "style_name": {
                        "type": "string",
                        "description": "Name of the style to inspect.",
                    },
                    "family": {
                        "type": "string",
                        "description": "Style family. Default: ParagraphStyles.",
                        "enum": ["ParagraphStyles", "CharacterStyles",
                                 "PageStyles", "FrameStyles", "NumberingStyles"],
                    },
                },
                "required": ["style_name"],
                "additionalProperties": False,
            },
        },
    },
]

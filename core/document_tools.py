# document_tools.py — Writer document manipulation tools for AI chat sidebar.
# Provides JSON tool schemas (WRITER_TOOLS) and executor functions for the
# OpenAI-compatible tool-calling protocol.
# Exposed tool list is markdown-centric: get_markdown, apply_markdown only.

import json

from core.logging import agent_log

from .format_support import FORMAT_TOOLS, tool_get_document_content, tool_apply_document_content, tool_find_text


# ---------------------------------------------------------------------------
# Tool list exposed to the AI (markdown-centric + media)
# ---------------------------------------------------------------------------

IMAGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image from a text prompt and insert it into the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The visual description of the image to generate."},
                    "width": {"type": "integer", "description": "Width in pixels (default 512)."},
                    "height": {"type": "integer", "description": "Height in pixels (default 512)."},
                    "provider": {"type": "string", "description": "Image provider: aihorde, or endpoint (use Settings endpoint URL for images)."}
                },
                "required": ["prompt"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_image",
            "description": "Edit the selected image using a text prompt (Img2Img). If no image is selected, it will fail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The visual description of the desired image version."},
                    "strength": {"type": "number", "description": "How much to change the image (0.0=none, 1.0=full). Default 0.6."},
                    "provider": {"type": "string", "description": "Image provider: aihorde, or endpoint (use Settings endpoint URL for images)."}
                },
                "required": ["prompt"],
                "additionalProperties": False
            }
        }
    }
]

WRITER_TOOLS = list(FORMAT_TOOLS) + IMAGE_TOOLS


# ---------------------------------------------------------------------------
# NOT CURRENTLY USED — Legacy tool schemas and executors. Not in WRITER_TOOLS;
# TOOL_DISPATCH entries for these are commented out below. Kept for possible future use.
# ---------------------------------------------------------------------------

def _tool_error(message):
    """Helper to create error response."""
    return json.dumps({"status": "error", "message": message})


def tool_replace_text(model, ctx, args):
    """Replace one or all occurrences. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    all_matches = args.get("all_matches", False)
    case_sensitive = args.get("case_sensitive", True)
    if all_matches:
        rd = model.createReplaceDescriptor()
        rd.SearchString = args["search"]
        rd.ReplaceString = args["replacement"]
        rd.SearchCaseSensitive = case_sensitive
        rd.SearchRegularExpression = False
        count = model.replaceAll(rd)
        return json.dumps({"status": "ok", "message": "Replaced %d occurrence(s)." % count})
    else:
        sd = model.createSearchDescriptor()
        sd.SearchString = args["search"]
        sd.SearchRegularExpression = False
        sd.SearchCaseSensitive = case_sensitive
        found = model.findFirst(sd)
        if found:
            found.setString(args["replacement"])
            return json.dumps({"status": "ok", "message": "Replaced 1 occurrence."})
        return json.dumps({"status": "not_found", "message": "Text not found in document."})


def tool_insert_text(model, ctx, args):
    """Insert text at beginning or end. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    text_obj = model.getText()
    position = args["position"]
    insert_str = args["text"]
    cursor = text_obj.createTextCursor()
    if position == "beginning":
        cursor.gotoStart(False)
    elif position == "end":
        cursor.gotoEnd(False)
    else:
        return _tool_error("Unknown position: %s" % position)
    text_obj.insertString(cursor, insert_str, False)
    return json.dumps({"status": "ok", "message": "Inserted text at %s." % position})


def tool_get_selection(model, ctx, args):
    """Return currently selected text. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    try:
        sel = model.getCurrentController().getSelection()
        if sel and sel.getCount() > 0:
            selected = sel.getByIndex(0).getString()
            return json.dumps({"status": "ok", "text": selected})
    except Exception as e:
        return _tool_error(str(e))
    return json.dumps({"status": "ok", "text": ""})


def tool_replace_selection(model, ctx, args):
    """Replace selected text. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    try:
        sel = model.getCurrentController().getSelection()
        if sel and sel.getCount() > 0:
            rng = sel.getByIndex(0)
            old_len = len(rng.getString())
            rng.setString(args["new_text"])
            return json.dumps({"status": "ok", "message": "Replaced selection (%d chars)." % old_len})
    except Exception as e:
        return _tool_error(str(e))
    return json.dumps({"status": "no_selection", "message": "No text is selected."})


def tool_format_text(model, ctx, args):
    """Find text and apply character formatting. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    sd = model.createSearchDescriptor()
    sd.SearchString = args["search"]
    sd.SearchRegularExpression = False
    sd.SearchCaseSensitive = True
    found = model.findFirst(sd)
    if not found:
        return json.dumps({"status": "not_found", "message": "Text not found in document."})
    applied = []
    if "bold" in args:
        found.setPropertyValue("CharWeight", 150.0 if args["bold"] else 100.0)
        applied.append("bold" if args["bold"] else "unbold")
    if "italic" in args:
        from com.sun.star.awt.FontSlant import ITALIC, NONE as SLANT_NONE
        found.setPropertyValue("CharPosture", ITALIC if args["italic"] else SLANT_NONE)
        applied.append("italic" if args["italic"] else "unitalic")
    if "underline" in args:
        found.setPropertyValue("CharUnderline", 1 if args["underline"] else 0)
        applied.append("underline" if args["underline"] else "no underline")
    if "strikethrough" in args:
        found.setPropertyValue("CharStrikeout", 1 if args["strikethrough"] else 0)
        applied.append("strikethrough" if args["strikethrough"] else "no strikethrough")
    if "font_size" in args:
        found.setPropertyValue("CharHeight", float(args["font_size"]))
        applied.append("size %spt" % args["font_size"])
    if "font_color" in args:
        hex_color = str(args["font_color"]).lstrip("#")
        color_int = int(hex_color, 16)
        found.setPropertyValue("CharColor", color_int)
        applied.append("color #%s" % hex_color)
    if not applied:
        return json.dumps({"status": "ok", "message": "Text found but no formatting properties specified."})
    return json.dumps({"status": "ok", "message": "Applied %s to '%s'." % (", ".join(applied), args["search"])})


def tool_set_paragraph_style(model, ctx, args):
    """Set paragraph style. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    style_name = args["style_name"]
    all_matches = args.get("all_matches", False)
    search_text = args["search"]
    text_obj = model.getText()
    enum = text_obj.createEnumeration()
    count = 0
    while enum.hasMoreElements():
        para = enum.nextElement()
        if not hasattr(para, "getString"):
            continue
        if search_text in para.getString():
            try:
                para.setPropertyValue("ParaStyleName", style_name)
                count += 1
            except Exception as e:
                return _tool_error("Style '%s' not found or error: %s" % (style_name, e))
            if not all_matches:
                break
    if count == 0:
        return json.dumps({"status": "not_found", "message": "No paragraph containing '%s' found." % search_text})
    return json.dumps({"status": "ok", "message": "Applied '%s' to %d paragraph(s)." % (style_name, count)})


def tool_get_document_text(model, ctx, args):
    """Get full document text. NOT CURRENTLY USED (not in WRITER_TOOLS)."""
    text_obj = model.getText()
    cursor = text_obj.createTextCursor()
    cursor.gotoStart(False)
    cursor.gotoEnd(True)
    full_text = cursor.getString()
    max_chars = args.get("max_chars")
    if max_chars and len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "\n\n[... truncated ...]"
    return json.dumps({"status": "ok", "text": full_text, "length": len(full_text)})


def tool_generate_image(model, ctx, args, status_callback=None):
    """Generate an image and insert it."""
    from core.image_service import ImageService
    from core.image_tools import insert_image
    from core.config import get_config_dict, as_bool, get_text_model, update_lru_history

    config = get_config_dict(ctx)
    service = ImageService(ctx, config)

    prompt = args.get("prompt")
    provider = args.get("provider", config.get("image_provider", "aihorde"))
    width = args.get("width", config.get("image_width", 512))
    height = args.get("height", config.get("image_height", 512))
    add_to_gallery = as_bool(config.get("image_auto_gallery", True))
    add_frame = as_bool(config.get("image_insert_frame", False))

    # Remove prompt from args to avoid "multiple values" error (it's passed positionally)
    args_copy = args.copy()
    if "prompt" in args_copy:
        del args_copy["prompt"]

    try:
        paths = service.generate_image(prompt, provider_name=provider, width=width, height=height, status_callback=status_callback, **args_copy)
        if not paths:
            return _tool_error("Generation failed: No image returned.")
        if provider in ("endpoint", "openrouter"):
            image_model_used = (config.get("image_model") or "").strip() or get_text_model(ctx)
            if image_model_used:
                update_lru_history(ctx, image_model_used, "image_model_lru")
        insert_image(ctx, model, paths[0], width, height, title=prompt, description=f"Generated by {provider}",
                     add_to_gallery=add_to_gallery, add_frame=add_frame)
        return json.dumps({"status": "ok", "message": f"Image generated and inserted from {provider}."})
    except Exception as e:
        return _tool_error(str(e))


def tool_edit_image(model, ctx, args, status_callback=None):
    """Edit the selected image using Img2Img. Replaces selection in place when possible."""
    from core.image_service import ImageService
    from core.image_tools import get_selected_image_base64, insert_image, replace_image_in_place
    from core.config import get_config_dict, as_bool, get_text_model, update_lru_history

    source_b64 = get_selected_image_base64(model, ctx=ctx)
    if not source_b64:
        return _tool_error("No image selected. Please select an image in the document first.")

    config = get_config_dict(ctx)
    service = ImageService(ctx, config)

    prompt = args.get("prompt")
    provider = args.get("provider", config.get("image_provider", "aihorde"))
    add_to_gallery = as_bool(config.get("image_auto_gallery", True))
    add_frame = as_bool(config.get("image_insert_frame", False))
    
    # Remove prompt from args to avoid "multiple values" error
    args_copy = args.copy()
    if "prompt" in args_copy:
        del args_copy["prompt"]

    try:
        paths = service.generate_image(prompt, provider_name=provider, source_image=source_b64, status_callback=status_callback, **args_copy)
        if not paths:
            return _tool_error("Editing failed: No image returned.")
        if provider in ("endpoint", "openrouter"):
            image_model_used = (config.get("image_model") or "").strip() or get_text_model(ctx)
            if image_model_used:
                update_lru_history(ctx, image_model_used, "image_model_lru")
        replaced = replace_image_in_place(ctx, model, paths[0], 512, 512, title=prompt,
                                          description=f"Edited by {provider}",
                                          add_to_gallery=add_to_gallery, add_frame=add_frame)
        if not replaced:
            insert_image(ctx, model, paths[0], 512, 512, title=prompt, description=f"Edited by {provider}",
                         add_to_gallery=add_to_gallery, add_frame=add_frame)
        return json.dumps({"status": "ok", "message": f"Image edited and inserted from {provider}."})
    except Exception as e:
        return _tool_error(str(e))


# ---------------------------------------------------------------------------
# Tool dispatch table (only tools currently exposed to the AI)
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    "get_document_content": tool_get_document_content,
    "apply_document_content": tool_apply_document_content,
    "find_text": tool_find_text,
    "generate_image": tool_generate_image,
    "edit_image": tool_edit_image,
    # Unused (not in WRITER_TOOLS); uncomment to re-enable:
    # "get_selection": tool_get_selection,
    # "replace_text": tool_replace_text,
    # "insert_text": tool_insert_text,
    # "replace_selection": tool_replace_selection,
    # "format_text": tool_format_text,
    # "set_paragraph_style": tool_set_paragraph_style,
    # "get_document_text": tool_get_document_text,
}


def _truncate_for_log(obj, max_len=200):
    """Return a copy safe for logging: long strings truncated, dicts/lists traversed."""
    if isinstance(obj, str):
        return obj if len(obj) <= max_len else obj[:max_len] + "...[truncated]"
    if isinstance(obj, dict):
        return {k: _truncate_for_log(v, max_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate_for_log(x, max_len) for x in obj]
    return obj


def execute_tool(tool_name, arguments, doc, ctx, status_callback=None):
    """Execute a tool by name. Returns JSON result string."""
    func = TOOL_DISPATCH.get(tool_name)
    if not func:
        return json.dumps({"status": "error", "message": "Unknown tool: %s" % tool_name})
    try:
        agent_log("document_tools.py:execute_tool", "Tool call", data={"tool": tool_name, "arguments": _truncate_for_log(arguments or {})}, hypothesis_id="C,E")
        # Inspect function signature to see if it accepts status_callback, 
        # or just pass it in kwargs if the functions accept **kwargs.
        # But our functions have specific signatures (model, ctx, args).
        # We'll update the relevant ones to accept **kwargs or specific status_callback.
        # For now, let's try passing it as a keyword argument if the function handles it,
        # otherwise we might need to wrap or update all signatures.
        # Given the plan, we updated tool_generate_image.
        # Let's update the call to support passing status_callback.
        
        import inspect
        sig = inspect.signature(func)
        if "status_callback" in sig.parameters or "kwargs" in sig.parameters:
             result = func(doc, ctx, arguments, status_callback=status_callback)
        else:
             result = func(doc, ctx, arguments)
             
        agent_log("document_tools.py:execute_tool", "Tool result", data={"tool": tool_name, "result_snippet": (result or "")[:120]}, hypothesis_id="C,E")
        return result
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

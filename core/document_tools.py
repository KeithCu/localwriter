# core/document_tools.py — Writer document manipulation tools for AI chat sidebar.
# Provides JSON tool schemas (WRITER_TOOLS) and executor for the
# OpenAI-compatible tool-calling protocol.

import json
import inspect

from core.logging import agent_log
from .format_support import FORMAT_TOOLS, tool_get_document_content, tool_apply_document_content, tool_find_text
from core.writer_ops import (
    WRITER_OPS_TOOLS,
    tool_get_document_outline,
    tool_get_heading_content,
    tool_read_paragraphs,
    tool_get_document_stats,
    tool_list_styles,
    tool_get_style_info,
    tool_list_comments,
    tool_insert_at_paragraph,
    tool_add_comment,
    tool_delete_comment,
    tool_set_track_changes,
    tool_get_tracked_changes,
    tool_accept_all_changes,
    tool_reject_all_changes,
    tool_list_tables,
    tool_read_table,
    tool_write_table_cell
)
from core.document import (
    get_document_length,
    is_writer,
    is_calc,
    is_draw,
    DocumentCache
)


# ---------------------------------------------------------------------------
# Image tools
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

SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Perform an autonomous web search using an AI sub-agent. The sub-agent will search the web, visit pages to read their content, and return a synthesized answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string", 
                        "description": "The information to search for or the question to answer."
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Why you are requesting this information."
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    }
]

WRITER_TOOLS = list(FORMAT_TOOLS) + WRITER_OPS_TOOLS + IMAGE_TOOLS + SEARCH_TOOLS


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_generate_image(model, ctx, args, status_callback=None):
    """Generate an image and insert it."""
    from core.image_service import ImageService
    from core.image_tools import insert_image
    from core.config import get_config_dict, as_bool, get_text_model, update_lru_history

    config = get_config_dict(ctx)
    service = ImageService(ctx, config)

    prompt = args.get("prompt")
    provider = args.get("provider", config.get("image_provider", "aihorde"))

    base_size = args.get("base_size", config.get("image_base_size", 512))
    try:
        base_size = int(base_size)
    except (ValueError, TypeError):
        base_size = 512

    aspect = args.get("aspect_ratio", config.get("image_default_aspect", "square"))
    if aspect == "landscape_16_9":
        w, h = int(base_size * 16 / 9), base_size
    elif aspect == "portrait_9_16":
        w, h = base_size, int(base_size * 16 / 9)
    elif aspect == "landscape_3_2":
        w, h = int(base_size * 1.5), base_size
    elif aspect == "portrait_2_3":
        w, h = base_size, int(base_size * 1.5)
    else:
        w, h = base_size, base_size

    w = (w // 64) * 64
    h = (h // 64) * 64

    width = args.get("width", w)
    height = args.get("height", h)
    add_to_gallery = as_bool(config.get("image_auto_gallery", True))
    add_frame = as_bool(config.get("image_insert_frame", False))

    args_copy = {k: v for k, v in args.items() if k != "prompt"}
    image_model_override = args.get("image_model")

    try:
        result = service.generate_image(prompt, provider_name=provider, width=width,
                                        height=height, status_callback=status_callback,
                                        model=image_model_override, **args_copy)
        if isinstance(result, tuple) and len(result) == 2:
            paths, error_msg = result
            if not paths:
                return json.dumps({"status": "error", "message": error_msg or "Generation failed: No image returned."})
        else:
            paths = result
            if not paths:
                return json.dumps({"status": "error", "message": "Generation failed: No image returned."})
        if provider in ("endpoint", "openrouter"):
            image_model_used = (image_model_override or config.get("image_model") or "").strip() or get_text_model(ctx)
            if image_model_used:
                endpoint = str(config.get("endpoint", "")).strip()
                update_lru_history(ctx, image_model_used, "image_model_lru", endpoint)
        insert_image(ctx, model, paths[0], width, height, title=prompt,
                     description="Generated by %s" % provider,
                     add_to_gallery=add_to_gallery, add_frame=add_frame)
        return json.dumps({"status": "ok", "message": "Image generated and inserted from %s." % provider})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def tool_edit_image(model, ctx, args, status_callback=None):
    """Edit the selected image using Img2Img. Replaces selection in place when possible."""
    from core.image_service import ImageService
    from core.image_tools import get_selected_image_base64, insert_image, replace_image_in_place
    from core.config import get_config_dict, as_bool, get_text_model, update_lru_history

    source_b64 = get_selected_image_base64(model, ctx=ctx)
    if not source_b64:
        return json.dumps({"status": "error", "message": "No image selected. Please select an image in the document first."})

    config = get_config_dict(ctx)
    service = ImageService(ctx, config)

    prompt = args.get("prompt")
    provider = args.get("provider", config.get("image_provider", "aihorde"))
    add_to_gallery = as_bool(config.get("image_auto_gallery", True))
    add_frame = as_bool(config.get("image_insert_frame", False))

    args_copy = {k: v for k, v in args.items() if k != "prompt"}

    try:
        result = service.generate_image(prompt, provider_name=provider,
                                        source_image=source_b64,
                                        status_callback=status_callback, **args_copy)
        if isinstance(result, tuple) and len(result) == 2:
            paths, error_msg = result
            if not paths:
                return json.dumps({"status": "error", "message": error_msg or "Editing failed: No image returned."})
        else:
            paths = result
            if not paths:
                return json.dumps({"status": "error", "message": "Editing failed: No image returned."})
        if provider in ("endpoint", "openrouter"):
            image_model_used = (config.get("image_model") or "").strip() or get_text_model(ctx)
            if image_model_used:
                endpoint = str(config.get("endpoint", "")).strip()
                update_lru_history(ctx, image_model_used, "image_model_lru", endpoint)
        replaced = replace_image_in_place(ctx, model, paths[0], 512, 512, title=prompt,
                                          description="Edited by %s" % provider,
                                          add_to_gallery=add_to_gallery, add_frame=add_frame)
        if not replaced:
            insert_image(ctx, model, paths[0], 512, 512, title=prompt,
                         description="Edited by %s" % provider,
                         add_to_gallery=add_to_gallery, add_frame=add_frame)
        return json.dumps({"status": "ok", "message": "Image edited and inserted from %s." % provider})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def tool_search_web(model, ctx, args, status_callback=None, append_thinking_callback=None):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
    from core.config import get_api_config
    from core.api import LlmClient
    from core.smol_model import LocalWriterSmolModel
    from core.smolagents_vendor.agents import ToolCallingAgent
    from core.smolagents_vendor.default_tools import DuckDuckGoSearchTool, VisitWebpageTool

    query = args.get("query", "")
    if not query:
        return json.dumps({"status": "error", "message": "Query is required for web search."})

    try:
        if status_callback:
            status_callback("Sub-agent starting web search: " + query)

        config = get_api_config(ctx)
        max_tokens = int(config.get("chat_max_tokens", 2048))
        search_timeout = int(config.get("search_web_timeout", 120))  # seconds, default 2 min

        smol_model = LocalWriterSmolModel(LlmClient(config, ctx), max_tokens=max_tokens)
        agent = ToolCallingAgent(
            tools=[DuckDuckGoSearchTool(), VisitWebpageTool()],
            model=smol_model,
        )
        task = f"Please find the answer to this query by searching the web and reading pages if needed: {query}"

        def run_agent_stream():
            if not append_thinking_callback:
                return agent.run(task)
                
            final_ans = None
            from core.smolagents_vendor.memory import ActionStep, FinalAnswerStep
            for step in agent.run(task, stream=True):
                if isinstance(step, ActionStep):
                    msg = f"Step {step.step_number}:\n"
                    if step.model_output:
                        msg += f"{step.model_output.strip()}\n"
                    elif getattr(step, "model_output_message", None) and step.model_output_message.content:
                        msg += f"{str(step.model_output_message.content).strip()}\n"
                    
                    if step.tool_calls:
                        for tc in step.tool_calls:
                            msg += f"Running tool: {tc.name} with {tc.arguments}\n"
                    
                    if step.observations:
                        msg += f"Observation: {str(step.observations).strip()}\n"
                        
                    append_thinking_callback(msg + "\n")
                elif isinstance(step, FinalAnswerStep):
                    final_ans = step.output
            return final_ans

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_agent_stream)
            try:
                answer = future.result(timeout=search_timeout)
            except FuturesTimeoutError:
                return json.dumps({
                    "status": "error",
                    "message": f"Web search timed out after {search_timeout} seconds. Try a narrower query or increase search_web_timeout in config.",
                })

        return json.dumps({"status": "ok", "result": str(answer)})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Web search failed: {str(e)}"})

# ---------------------------------------------------------------------------
# Tool dispatch table
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    "get_document_content": tool_get_document_content,
    "apply_document_content": tool_apply_document_content,
    "find_text": tool_find_text,
    # Styles
    "get_document_outline": tool_get_document_outline,
    "get_heading_content": tool_get_heading_content,
    "read_paragraphs": tool_read_paragraphs,
    "insert_at_paragraph": tool_insert_at_paragraph,
    "get_document_stats": tool_get_document_stats,
    "list_styles": tool_list_styles,
    "get_style_info": tool_get_style_info,
    # Comments
    "list_comments": tool_list_comments,
    "add_comment": tool_add_comment,
    "delete_comment": tool_delete_comment,
    # Track changes
    "set_track_changes": tool_set_track_changes,
    "get_tracked_changes": tool_get_tracked_changes,
    "accept_all_changes": tool_accept_all_changes,
    "reject_all_changes": tool_reject_all_changes,
    # Tables
    "list_tables": tool_list_tables,
    "read_table": tool_read_table,
    "write_table_cell": tool_write_table_cell,
    # Images
    "generate_image": tool_generate_image,
    "edit_image": tool_edit_image,
    # Search
    "search_web": tool_search_web,
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


def execute_tool(tool_name, arguments, doc, ctx, status_callback=None, append_thinking_callback=None):
    """Execute a tool by name. Returns JSON result string."""
    # If the tool is a writer operation, it might mutate the document.
    # Invalidate cache if it's not a 'get' or 'read' or 'list' tool.
    is_mutation = not (tool_name.startswith("get_") or tool_name.startswith("read_") or tool_name.startswith("list_"))
    if is_mutation:
        DocumentCache.invalidate(doc)

    func = TOOL_DISPATCH.get(tool_name)
    if not func:
        return json.dumps({"status": "error", "message": "Unknown tool: %s" % tool_name})
    try:
        agent_log("document_tools.py:execute_tool", "Tool call",
                  data={"tool": tool_name, "arguments": _truncate_for_log(arguments or {})},
                  hypothesis_id="C,E")
        sig = inspect.signature(func)
        kwargs = {}
        if "status_callback" in sig.parameters or "kwargs" in sig.parameters:
            kwargs["status_callback"] = status_callback
        if "append_thinking_callback" in sig.parameters or "kwargs" in sig.parameters:
            kwargs["append_thinking_callback"] = append_thinking_callback
            
        result = func(doc, ctx, arguments, **kwargs)
        agent_log("document_tools.py:execute_tool", "Tool result",
                  data={"tool": tool_name, "result_snippet": (result or "")[:120]},
                  hypothesis_id="C,E")
        return result
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

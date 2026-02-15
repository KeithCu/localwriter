"""
Pure LLM query logic for LocalWriter — no UNO dependencies.
Handles API request building, SSE streaming, and response parsing
for Ollama, LM Studio, text-generation-webui, OpenAI, and OpenWebUI.
"""

import json
import ssl
import urllib.request


def as_bool(value):
    """Convert various types to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(value, (int, float)):
        return value != 0
    return False


def is_openai_compatible(endpoint, compatibility_flag):
    """Check if endpoint is OpenAI-compatible based on flag or domain."""
    return as_bool(compatibility_flag) or ("api.openai.com" in str(endpoint).lower())


def build_api_request(prompt, endpoint, api_key="", api_type="completions",
                      model="", is_openwebui=False, openai_compatible=False,
                      system_prompt="", max_tokens=70, log_fn=None):
    """
    Build a streaming completion/chat request for local or OpenAI-compatible endpoints.
    Returns a urllib.request.Request object.
    """
    if log_fn is None:
        log_fn = lambda msg: None

    try:
        max_tokens = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens = 70

    endpoint = str(endpoint).rstrip("/")
    api_key = str(api_key)
    api_type = "chat" if str(api_type).lower() == "chat" else "completions"
    model = str(model)

    log_fn(f"=== API Request Debug ===")
    log_fn(f"Endpoint: {endpoint}")
    log_fn(f"API Type: {api_type}")
    log_fn(f"Model: {model}")
    log_fn(f"Max Tokens: {max_tokens}")

    headers = {
        'Content-Type': 'application/json'
    }

    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    # Detect OpenWebUI endpoints (they use /api/ instead of /v1/)
    is_owui = as_bool(is_openwebui) or "open-webui" in endpoint.lower() or "openwebui" in endpoint.lower()
    api_path = "/api" if is_owui else "/v1"

    log_fn(f"Is OpenWebUI: {is_owui}")
    log_fn(f"API Path: {api_path}")

    if api_type == "chat":
        url = endpoint + api_path + "/chat/completions"
        log_fn(f"Full URL: {url}")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        data = {
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': 1,
            'top_p': 0.9,
            'stream': True
        }
    else:
        url = endpoint + api_path + "/completions"
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"SYSTEM PROMPT\n{system_prompt}\nEND SYSTEM PROMPT\n{prompt}"
        data = {
            'prompt': full_prompt,
            'max_tokens': max_tokens,
            'temperature': 1,
            'top_p': 0.9,
            'stream': True
        }
        if not is_openai_compatible(endpoint, openai_compatible):
            data['seed'] = 10

    if model:
        data["model"] = model

    json_data = json.dumps(data).encode('utf-8')
    log_fn(f"Request data: {json.dumps(data, indent=2)}")
    safe_headers = {k: ("***" if k == "Authorization" else v) for k, v in headers.items()}
    log_fn(f"Headers: {safe_headers}")

    request = urllib.request.Request(url, data=json_data, headers=headers)
    request.get_method = lambda: 'POST'
    return request


def extract_content(chunk, api_type="completions"):
    """
    Extract text content from API response chunk based on API type.
    Returns (content_text, finish_reason).
    """
    if api_type == "chat":
        if "choices" in chunk and len(chunk["choices"]) > 0:
            delta = chunk["choices"][0].get("delta", {})
            return delta.get("content", ""), chunk["choices"][0].get("finish_reason")
    else:
        if "choices" in chunk and len(chunk["choices"]) > 0:
            return chunk["choices"][0].get("text", ""), chunk["choices"][0].get("finish_reason")

    return "", None


def make_ssl_context(disable_verification=False):
    """Create SSL context, optionally disabling verification."""
    if as_bool(disable_verification):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    return ssl.create_default_context()


def stream_response(request, api_type, ssl_context, append_callback,
                    on_idle=None, log_fn=None):
    """
    Stream a completion/chat response and call append_callback with each text chunk.
    on_idle is called after each chunk to allow UI updates (e.g. toolkit.processEventsToIdle).
    """
    if log_fn is None:
        log_fn = lambda msg: None
    if on_idle is None:
        on_idle = lambda: None

    log_fn(f"=== Starting stream request ===")
    log_fn(f"Request URL: {request.full_url}")
    log_fn(f"Request method: {request.get_method()}")

    try:
        with urllib.request.urlopen(request, context=ssl_context) as response:
            log_fn(f"Response status: {response.status}")
            log_fn(f"Response headers: {response.headers}")

            for line in response:
                try:
                    if line.strip() and line.startswith(b"data: "):
                        payload = line[len(b"data: "):].decode("utf-8").strip()
                        if payload == "[DONE]":
                            break
                        chunk = json.loads(payload)
                        content, finish_reason = extract_content(chunk, api_type)
                        if content:
                            append_callback(content)
                            on_idle()
                        if finish_reason:
                            break
                except Exception as e:
                    log_fn(f"Error processing line: {str(e)}")
                    append_callback(str(e))
                    on_idle()
    except Exception as e:
        log_fn(f"ERROR in stream_response: {str(e)}")
        append_callback(f"ERROR: {str(e)}")
        on_idle()

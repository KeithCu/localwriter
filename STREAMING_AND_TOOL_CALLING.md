# Streaming and Tool Calling: How the APIs Work

This document explains how OpenAI-compatible chat APIs handle **streaming** and **tool calling**, and how **reasoning/thinking** appears in streams. It is aimed at developers who need to implement or debug clients (e.g. LocalWriter’s chat sidebar).

References: OpenAI [Streaming](https://platform.openai.com/docs/api-reference/streaming), [Tool calling](https://platform.openai.com/docs/guides/function-calling); OpenRouter [Streaming](https://openrouter.ai/docs/api-reference/streaming), [Reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

---

## 1. Chat completions: non-streaming

**Request:** `POST /v1/chat/completions` with `stream: false` (or omitted).

**Response:** One JSON object:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris.",
        "tool_calls": null
      },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30 }
}
```

- **Content:** `choices[0].message.content` (string, can be `null` if the model only made tool calls).
- **Tool calls:** `choices[0].message.tool_calls` — array of `{ id, type: "function", function: { name, arguments } }`. `arguments` is a **single JSON string** the client must parse.
- **Finish reason:** `choices[0].finish_reason` — e.g. `"stop"`, `"length"`, `"tool_calls"`.

With tools, the client sends back `tool` messages with `tool_call_id` and `content`, then calls the API again with the extended `messages` array. That loop is “tool-calling”; the API is still one request / one response per round.

---

## 2. Chat completions: streaming (no tools)

**Request:** Same URL, `stream: true`.

**Response:** HTTP body is **Server-Sent Events (SSE)**. Each event is a line starting with `data: `. The payload is JSON. Last event is usually `data: [DONE]`.

**Chunk shape (content-only):**

```json
{
  "id": "chatcmpl-...",
  "choices": [
    {
      "index": 0,
      "delta": { "content": "The ", "role": "assistant" },
      "finish_reason": null
    }
  ]
}
```

Later chunks may have only new content:

```json
{ "choices": [{ "delta": { "content": "capital" }, "finish_reason": null }] }
```

Final chunk:

```json
{ "choices": [{ "delta": {}, "finish_reason": "stop" }] }
```

**Client behavior:**

- Read line by line; skip empty lines and comments (e.g. OpenRouter sends `: OPENROUTER PROCESSING`).
- If line is `data: [DONE]`, stop.
- Otherwise parse `data: <json>`. From `choices[0].delta` take:
  - `content` — append to the displayed reply.
  - `finish_reason` — when non-null, stream is done (and may be `stop`, `length`, etc.).

The **delta** only contains what **changed** in this chunk; the client accumulates content itself.

---

## 3. Tool calling: non-streaming

**Request:** `POST /v1/chat/completions`, `stream: false`, body includes:

- `messages`: e.g. `[ { "role": "user", "content": "..." }, ... ]`
- `tools`: array of tool definitions (`type: "function"`, `function: { name, description, parameters }`).
- `tool_choice`: `"auto"` (or a specific tool).

**Response:** Same as in section 1, but `choices[0].message` may contain:

- `content`: optional text before/with the tool call.
- `tool_calls`: array of:
  - `id`: string (e.g. `"call_abc123"`).
  - `type`: `"function"`.
  - `function`: `{ "name": "get_weather", "arguments": "{\"location\": \"Paris\"}" }`.

The client:

1. Parses each `tool_calls[].function.arguments` as JSON.
2. Calls the local function / backend.
3. Appends a **tool** message: `{ "role": "tool", "tool_call_id": "<id>", "content": "<result>" }`.
4. Sends a new request with `messages` = previous messages + assistant message + tool message(s).
5. Repeats until `message.tool_calls` is null/empty and the model returns only text (or `finish_reason` is `stop` / `length`).

LocalWriter’s `request_with_tools()` in `main.py` does exactly this: one non-streaming request per round, parse `message.content` and `message.tool_calls`, then run tools and loop.

---

## 4. Streaming when tools are in the request

When you send `stream: true` **and** `tools` in the request, the API can still return a stream, but the **delta** now includes **partial tool call** data. The client must **accumulate** these deltas into a full message before it can run tools.

**Chunk shape (streaming with tool_calls):**

- Early chunks may contain **reasoning/thinking** (see section 5) and/or **content** deltas.
- Chunks for tool calls look like:

```json
{
  "choices": [{
    "delta": {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        { "index": 0, "id": "call_abc", "type": "function", "function": { "name": "get_weather", "arguments": "" } }
      ]
    },
    "finish_reason": null
  }
}
```

Later chunks add **partial arguments** (only the new fragment):

```json
{
  "choices": [{
    "delta": {
      "tool_calls": [
        { "index": 0, "function": { "arguments": "{\"location\":" } }
      ]
    }
  }
}
```

```json
{
  "choices": [{
    "delta": {
      "tool_calls": [
        { "index": 0, "function": { "arguments": " \"Paris\"}" } }
      ]
    }
  }
}
```

So **one** tool call is spread across **many** chunks. The client must:

- Maintain a buffer per `index` (or `id` when present): `id`, `type`, `function.name`, `function.arguments`.
- For each chunk, **merge** `delta.tool_calls[i]` into the buffer for that index (e.g. append `function.arguments`).
- When the stream ends (`finish_reason` set or `[DONE]`), parse the accumulated `function.arguments` as JSON and run the tools.

Order of appearance in the stream is typically: optional reasoning deltas, optional content deltas, then tool_calls deltas (often after content/reasoning). The exact order is provider-dependent.

---

## 5. Reasoning / thinking in the stream

Some models (e.g. OpenRouter with Claude, Gemini, or reasoning models) send **reasoning** or **thinking** tokens in addition to the main reply. These appear in the **same** SSE stream, in the **delta**.

### 5.1 OpenRouter-style: `reasoning_details`

OpenRouter normalizes reasoning into **reasoning_details**. In **streaming** responses, each chunk may contain:

- `choices[0].delta.reasoning_details`: **array** of objects. Each object can be:
  - `type: "reasoning.text"` and `text`: string to show as thinking.
  - `type: "reasoning.summary"` and `summary`: string summary.
  - `type: "reasoning.encrypted"` and `data`: opaque (e.g. redacted).

So the client should:

- For each chunk, read `delta.reasoning_details` (if present).
- For each element, if `type === "reasoning.text"` append `text`; if `type === "reasoning.summary"` append `summary` (or treat similarly).
- Pass that concatenated string to the UI (e.g. “thinking” area or same box as content).

Reasoning chunks often **precede** content chunks; the model “thinks” then “replies”. So in the same stream you may see:

1. Several chunks with only `delta.reasoning_details`.
2. Then chunks with `delta.content`.
3. Optionally chunks with `delta.tool_calls`.

### 5.2 Other providers: `reasoning_content`

Some APIs use a single string field in the delta, e.g. `delta.reasoning_content`. Same idea: if present, append it to the thinking buffer and show it in the UI.

### 5.3 Non-streaming

In **non-streaming** responses, reasoning is usually on the **message** object, e.g. `choices[0].message.reasoning` or `choices[0].message.reasoning_details`. So when we use non-streaming for tool rounds, we don’t get incremental thinking updates; we only get it when the full response arrives. To show thinking **during** tool rounds, the client must use **streaming** for those requests and implement the accumulation described in section 4 plus the reasoning extraction above.

---

## 6. Summary table

| Mode              | Request        | Response        | Content              | Tool calls           | Reasoning / thinking      |
|-------------------|----------------|-----------------|----------------------|----------------------|---------------------------|
| Chat, no stream   | `stream: false`| Single JSON     | `message.content`    | `message.tool_calls` | `message.reasoning*`      |
| Chat, stream      | `stream: true` | SSE chunks      | `delta.content`      | N/A (no tools)       | `delta.reasoning_*`       |
| Chat + tools, stream | `stream: true`, `tools` | SSE chunks | `delta.content`   | `delta.tool_calls` (accumulate) | `delta.reasoning_*` |

\* When the API supports it and the model returns it.

---

## 7. Testing with OpenRouter

If you have an OpenRouter API key, you can verify how streaming, tool calls, and reasoning actually behave.

### 7.1 What to test

1. **Streaming without tools**
   - `POST https://openrouter.ai/api/v1/chat/completions`, `stream: true`, no `tools`.
   - Inspect each SSE chunk: `choices[0].delta.content`, `finish_reason`. Confirm content is incremental and `[DONE]` or final chunk ends the stream.

2. **Streaming with a reasoning model**
   - Same URL, `stream: true`, use a model that returns reasoning (e.g. one of the OpenRouter models listed in their [reasoning docs](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)). Optionally set `reasoning: { effort: "low" }` in the body (OpenRouter-specific).
   - Inspect chunks for `choices[0].delta.reasoning_details`: you should see arrays of `{ type: "reasoning.text", text: "..." }` (or similar) before or interleaved with `delta.content`.

3. **Streaming with tools**
   - Same URL, `stream: true`, add a minimal `tools` array (e.g. one function) and ask the model to call it.
   - Inspect chunks for `delta.tool_calls`: first chunk(s) may have `id`, `type`, `function.name`, `arguments: ""`; later chunks add fragments to `function.arguments`. Confirm you can concatenate `arguments` and parse as JSON.

4. **Streaming with tools + reasoning**
   - Combine (2) and (3): model that supports reasoning, with tools. You should see reasoning_details chunks, then content and/or tool_calls. Order and exact shape depend on the model; the doc above is the generic pattern.

### 7.2 What you’ll learn

- **Exact chunk order** for your chosen model (reasoning → content → tool_calls, or interleaved).
- **Exact field names** OpenRouter uses (`reasoning_details` vs any variant).
- **Whether** `function.arguments` is split across many small chunks or fewer larger ones (affects accumulation logic).
- **Whether** `finish_reason` is `"tool_calls"` when the model stops to call tools, and what the final chunk looks like.

### 7.3 How to run tests

- **Manual:** Use `curl` or a small script: set `Authorization: Bearer <OPENROUTER_API_KEY>`, `Content-Type: application/json`, body with `model`, `messages`, `stream: true`, and optionally `tools` and `reasoning`. Parse SSE line by line and log each chunk (or key fields).
- **In LocalWriter:** After implementing the streaming + thinking callback, point the extension at OpenRouter (endpoint `https://openrouter.ai/api/v1`, API key set) and use a reasoning model; observe the sidebar to see when thinking vs content appears.

Once you’ve run these tests, you can document the **actual** chunk shapes and order in this file or in a short “OpenRouter streaming notes” section so the implementation can be aligned with real responses.

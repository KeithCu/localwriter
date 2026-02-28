# Streaming, Tool Calling, and Request Batching: How the APIs Work

This document explains how OpenAI-compatible chat APIs handle **streaming**, **tool calling**, and **request batching**, and how **reasoning/thinking** appears in streams. It is aimed at developers who need to implement or debug clients (e.g. LocalWriter’s chat sidebar).

References: OpenAI [Streaming](https://platform.openai.com/docs/api-reference/streaming), [Tool calling](https://platform.openai.com/docs/guides/function-calling). Your endpoint may have its own docs for streaming and reasoning tokens.

---

## Table of Contents

1. [Chat completions: streaming (no tools)](#1-chat-completions-streaming-no-tools)
2. [Streaming when tools are in the request](#2-streaming-when-tools-are-in-the-request)
3. [Reasoning / thinking in the stream](#3-reasoning--thinking-in-the-stream)
4. [Summary table](#4-summary-table)
5. [Testing with OpenRouter](#5-testing-with-openrouter)
6. [Implementation: `streaming_deltas.py`](#6-implementation-streaming_deltaspy)
7. [Error Handling and UI Threading](#7-error-handling-and-ui-threading)
8. [Parallel Tool Calling](#8-parallel-tool-calling)

---

## 1. Chat completions: streaming (no tools)

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

- Read line by line; skip empty lines and comments (some providers send processing hints).
- If line is `data: [DONE]`, stop.
- Otherwise parse `data: <json>`. From `choices[0].delta` take:
  - `content` — append to the displayed reply.
  - `finish_reason` — when non-null, stream is done (and may be `stop`, `length`, etc.).

The **delta** only contains what **changed** in this chunk; the client accumulates content itself.

---

## 2. Streaming when tools are in the request

When you send `stream: true` **and** `tools` in the request, the API can still return a stream, but the **delta** now includes **partial tool call** data. The client must **accumulate** these deltas into a full message before it can run tools.

**Chunk shape (streaming with tool_calls):**

- Early chunks may contain **reasoning/thinking** (see section 3) and/or **content** deltas.
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

## 3. Reasoning / thinking in the stream

Some models send **reasoning** or **thinking** tokens in addition to the main reply. These appear in the **same** SSE stream, in the **delta**.

### 3.1 Provider-style: `reasoning_details`

Some providers use **reasoning_details**. In **streaming** responses, each chunk may contain:

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

### 3.2 Other providers: `reasoning_content`

Some APIs use a single string field in the delta, e.g. `delta.reasoning_content`. Same idea: if present, append it to the thinking buffer and show it in the UI.

---

## 4. Summary table

| Mode                   | Request                  | Response   | Content              | Tool calls                        | Reasoning / thinking  |
|------------------------|--------------------------|------------|----------------------|-----------------------------------|------------------------|
| Chat, stream           | `stream: true`           | SSE chunks | `delta.content`      | N/A (no tools)                    | `delta.reasoning_*`    |
| Chat + tools, stream   | `stream: true`, `tools`  | SSE chunks | `delta.content`      | `delta.tool_calls` (accumulate)   | `delta.reasoning_*`    |

\* When the API supports it and the model returns it.

---

## 5. Testing with your endpoint

If you have an API key for your endpoint, you can verify how streaming, tool calls, and reasoning actually behave.

### 5.1 What to test

1. **Streaming without tools**
   - `POST <your-endpoint>/chat/completions`, `stream: true`, no `tools`.
   - Inspect each SSE chunk: `choices[0].delta.content`, `finish_reason`. Confirm content is incremental and `[DONE]` or final chunk ends the stream.

2. **Streaming with a reasoning model**
   - Same URL, `stream: true`, use a model that returns reasoning if your provider supports it. Some providers accept `reasoning: { effort: "low" }` in the body.
   - Inspect chunks for `choices[0].delta.reasoning_details`: you should see arrays of `{ type: "reasoning.text", text: "..." }` (or similar) before or interleaved with `delta.content`.

3. **Streaming with tools**
   - Same URL, `stream: true`, add a minimal `tools` array (e.g. one function) and ask the model to call it.
   - Inspect chunks for `delta.tool_calls`: first chunk(s) may have `id`, `type`, `function.name`, `arguments: ""`; later chunks add fragments to `function.arguments`. Confirm you can concatenate `arguments` and parse as JSON.

4. **Streaming with tools + reasoning**
   - Combine (2) and (3): model that supports reasoning, with tools. You should see reasoning_details chunks, then content and/or tool_calls. Order and exact shape depend on the model; the doc above is the generic pattern.

### 5.2 What you’ll learn

- **Exact chunk order** for your chosen model (reasoning → content → tool_calls, or interleaved).
- **Exact field names** your provider uses (`reasoning_details` vs any variant).
- **Whether** `function.arguments` is split across many small chunks or fewer larger ones (affects accumulation logic).
- **Whether** `finish_reason` is `"tool_calls"` when the model stops to call tools, and what the final chunk looks like.

### 5.3 How to run tests

- **Manual:** Use `curl` or a small script: set `Authorization: Bearer <OPENROUTER_API_KEY>`, `Content-Type: application/json`, body with `model`, `messages`, `stream: true`, and optionally `tools` and `reasoning`. Parse SSE line by line and log each chunk (or key fields).
- **In LocalWriter:** Set your endpoint URL and API key in Settings; use a reasoning model if your endpoint supports it. Observe the sidebar to see when thinking vs content appears.

Once you’ve run these tests, you can document the **actual** chunk shapes and order in this file or in a short “streaming notes” section so the implementation can be aligned with real responses.

---

## 6. Implementation: `streaming_deltas.py`

We chose the **lightweight, dependency-free** approach:

- We copied **[`accumulate_delta`](https://github.com/openai/openai-python/blob/main/src/openai/lib/streaming/_deltas.py)** from the OpenAI Python SDK into **`core/streaming_deltas.py`**.
- This function handles the complex logic of merging partial tool call arguments (which can be split across many chunks) and concatenating content strings.
- logic: `accumulate_delta(snapshot, delta)` -> updates snapshot in place.

This avoids adding the heavy `openai` dependency to the LibreOffice extension while ensuring 100% compatibility with OpenAI-style streaming deltas.

---

## 7. Event Loop and UI Threading

LibreOffice’s UI (VCL) is single-threaded. To keep the UI responsive during long-running network operations, LocalWriter uses a **flat event loop** architecture on the main thread, combined with worker threads that push messages to a single `queue.Queue`.

**The Architecture:**

1. **Worker Threads (Producers):**
   - The LLM stream (`_spawn_llm_worker`) runs on a background thread. It pushes messages like `("chunk", text)`, `("thinking", text)`, `("stream_done", response)`, or `("error", e)` to the queue.
   - Long-running network tools (like Web Search or Image Generation) also run on background threads and push `("tool_thinking", text)", `("status", text)`, and `("tool_done", ...)` to the *same* queue.

2. **Main Thread (Consumer):**
   - Runs a single `while True` event loop in `_start_tool_calling_async`.
   - Blocks briefly on `q.get(timeout=0.1)`.
   - If the queue is empty, it calls `toolkit.processEventsToIdle()` to pump LibreOffice UI events, keeping the application perfectly responsive.
   - If an item is received, it dispatches based on the message type (e.g., appending text, updating status, executing tools).

This flat architecture avoids nested callbacks and makes state transitions explicit.

## 8. Tool Execution and Queuing

### Overview

When the LLM finishes a stream and requests tools (`"stream_done"`), LocalWriter must execute them. Some tools (like modifying the spreadsheet) must run synchronously on the main thread because LibreOffice UNO calls are not thread-safe. Other tools (like Web Research) must run on a background thread because they do heavy network I/O and would freeze the UI.

### The `next_tool` Queuing System

To handle both sync and async tools without freezing the UI, LocalWriter uses an internal dispatch queue:

1. **Queueing:** When `"stream_done"` is received with `tool_calls`, the calls are added to a `pending_tools` list, and a `("next_tool",)` message is pushed onto the queue.
2. **Dispatching:** The main loop picks up `"next_tool"`. It pops the first tool from `pending_tools`:
   - **Async Tools (`ASYNC_TOOLS` set):** Spawned in a daemon thread. The main loop immediately returns to pumping UI events. When the thread finishes, it pushes a `("tool_done", ...)` message to the queue.
   - **Sync Tools (UNO operations):** Executed immediately on the main thread. A `("tool_done", ...)` message is pushed to the queue.
3. **Completion:** When `"tool_done"` is received, the result is saved to the session history, and another `("next_tool",)` message is pushed.
4. **Next Round:** When `"next_tool"` finds an empty `pending_tools` list, all tools are finished. The loop increments the round counter and spawns a new LLM worker to send the results back to the model.

This sequentializes tool execution while guaranteeing the UI never freezes during network-bound tool operations.

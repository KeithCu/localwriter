# Error Handling & Consistency: Dev Plan

## Focus: Standardize Error Patterns Across Modules

**Goal**: Make debugging easier and more predictable by creating unified error classes, standardizing error payload formats, improving error context logging, and adding recovery patterns for common failures.

This plan details a phased refactor to clean up widespread, ad-hoc `Exception` usage across the codebase.

---

## 1. Audit & Problem Statement

Currently, the WriterAgent codebase suffers from fragmented error handling:
- **Overuse of Base Exception**: Modules like `plugin/modules/http/client.py`, `plugin/framework/document.py`, and `plugin/framework/image_utils.py` extensively use `raise Exception("...")` and catch generic `except Exception:`.
- **Fragmented Custom Exceptions**: There are isolated custom exceptions scattered throughout (`ConfigAccessError` in `config.py`, `AuthError` in `auth.py`, `TunnelError` in `tunnel/__init__.py`, `BusyError` in `mcp_protocol.py`, `IdentifiedError` in `aihordeclient`).
- **Inconsistent Error Payloads**: Tool execution errors, MCP API responses, and streaming errors do not follow a strict JSON payload schema. Sometimes they return `{"status": "error", "message": "..."}`, sometimes just a raw string, sometimes an empty `{}`.
- **Lost Context**: Generic exceptions often lose their traceback or operational context (e.g. *which* tool failed, *which* UNO document threw the error), making the `writeragent_debug.log` hard to parse.

---

## 2. Refactor Strategy & Unified Error Classes

### Phase 1: Centralized Error Hierarchy (`plugin/framework/errors.py`)
Create a new central file `plugin/framework/errors.py` (or similar) defining a standard exception hierarchy:

```python
class WriterAgentException(Exception):
    """Base exception for all WriterAgent errors."""
    def __init__(self, message, code="INTERNAL_ERROR", context=None):
        super().__init__(message)
        self.code = code
        self.context = context or {}

class ConfigError(WriterAgentException):
    """Configuration, Auth, or Settings issues."""
    # Replaces ConfigAccessError, AuthError

class NetworkError(WriterAgentException):
    """HTTP/Network related failures."""
    # Replaces ad-hoc LlmClient / Request exceptions

class UnoObjectError(WriterAgentException):
    """LibreOffice UNO interface failures (stale docs, missing properties)."""

class ToolExecutionError(WriterAgentException):
    """Tool invocation and execution failures."""

class AgentParsingError(WriterAgentException):
    """LLM output / JSON parsing failures."""
```

*Action Items*:
- Map existing scattered custom exceptions (`ConfigAccessError`, `AuthError`, etc.) to inherit from or be replaced by these centralized classes.
- Update `plugin/modules/http/client.py` to raise `NetworkError` or `AgentParsingError` instead of generic `Exception`.
- Update `plugin/framework/document.py` UNO interactions to catch `Exception` and re-raise as context-rich `UnoObjectError` or handle gracefully.

---

## 3. Standardize Error Payload Formats

### Phase 2: Payload Normalization
Standardize how tools, MCP server responses, and UI elements serialize errors.

**Proposed Standard JSON Payload**:
```json
{
  "status": "error",
  "code": "SPECIFIC_ERROR_CODE",
  "message": "Human readable summary of the failure.",
  "details": {
    "key": "value (e.g., endpoint URL, tool name, token count)"
  }
}
```

*Action Items*:
- Refactor `ToolRegistry.execute()` (in `plugin/framework/tool_registry.py`) to consistently output this schema when catching a `ToolExecutionError` or `WriterAgentException`.
- Refactor MCP Server (`plugin/modules/http/server.py` and `mcp_protocol.py`) to map `WriterAgentException` codes to appropriate JSON-RPC or HTTP error payloads.
- Ensure the AI UI (Chat Sidebar) unwraps these payloads cleanly (e.g., in `send_handlers.py` and `api.format_error_for_display()`).

---

## 4. Improve Error Context Logging

### Phase 3: Enhanced Diagnostics
Generic exceptions currently lose the context of *what* the system was doing.

*Action Items*:
- Update `plugin/framework/logging.py` (`debug_log` and `log_exception`) to automatically extract and format the `.context` dictionary attached to `WriterAgentException`.
- When catching generic `Exception` in high-level loops (like the `drain_loop` in `tool_loop.py` or background workers in `worker_pool.py`), ensure the full `traceback.format_exc()` is reliably logged with context before gracefully returning the standardized error payload.

---

## 5. Recovery Patterns for Common Failures

### Phase 4: Resiliency
Based on the audit, implement localized recovery patterns where `except Exception` blocks are currently failing silently or crashing abruptly:

1. **UNO Stale Object Recovery** (`plugin/framework/document.py`):
   - When referencing a document element (e.g. `cursor`, `shape`) that no longer exists (often resulting in `DisposedException` or `RuntimeException`), catch it, invalidate the `DocumentCache`, and attempt a retry before giving up.
2. **Network/HTTP Transient Failures** (`plugin/modules/http/client.py`):
   - Implement exponential backoff for 502/503/504 errors on API endpoints instead of immediately hard-failing the chat session.
3. **JSON Parse Fallbacks** (`send_handlers.py` / `tool_call_parsers`):
   - If an LLM returns malformed JSON for a tool call, inject a fast-recovery prompt (e.g., "The previous tool call had malformed JSON. Please fix syntax and try again.") instead of surfacing the raw JSON decode error to the user.

---

## Summary of Next Steps for Implementation
1. Add `plugin/framework/errors.py`.
2. Migrate `plugin/framework/config.py` and `plugin/framework/auth.py` to use new error classes.
3. Overhaul `plugin/modules/http/client.py` to strip out bare `raise Exception("...")` calls.
4. Refactor `ToolRegistry` to emit the standardized `{"status": "error", "code": "...", "message": "..."}` payload format.
5. Run the full test suite (`make test`) ensuring that mocked/simulated error conditions correctly trigger the new payloads and log outputs.
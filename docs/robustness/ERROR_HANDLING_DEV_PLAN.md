

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
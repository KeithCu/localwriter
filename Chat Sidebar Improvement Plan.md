Chat Sidebar Improvement Plan

Current State (updated 2026-02-14)

The chat sidebar has conversation history, tool-calling, and 8 curated Writer document tools. The AI can read, search, replace, format, and style text in the open Writer document via the OpenAI-compatible tool-calling protocol.

**Recent improvements (Feb 2026):**
- **Streaming I/O: pure Python queue + main-thread drain (no UNO Timer)**: All streaming—sidebar tool-calling, sidebar simple stream, Writer Extend/Edit/menu Chat, Calc—uses the same pattern: a **worker thread** puts chunks/thinking/stream_done/error/stopped on a **`queue.Queue`**; the **main thread** runs a drain loop: `q.get(timeout=0.05)` → process item → **`toolkit.processEventsToIdle()`**. No UNO Timer or `XTimerListener` (that type is unavailable in the sidebar context). Interface is just the queue; only UNO used is toolkit by string name and `processEventsToIdle()`. Multiple chunks can be applied between redraws, so multiple inserts are shown in one repaint—fewer redraws and faster perceived speed. Implemented in `chat_panel.py` `_start_tool_calling_async()` (tool path) and in `core/async_stream.py` `run_stream_completion_async()` (simple stream + Writer/Calc flows). See AGENTS.md Section 3b "Streaming I/O".
- **Document context for chat**: Context sent to the AI now includes (1) **start and end excerpts** of the document (split of `chat_context_length`, e.g. 4000 + 4000) so long documents show both beginning and end; (2) **selection/cursor as inline markers** inside that text: `[SELECTION_START]` and `[SELECTION_END]` at the actual character positions. No separate selection block and no duplication—the selection is the span between the two markers (or both markers at the cursor when nothing is selected, indicating insertion point). Implemented in `core/document.py`: `get_document_end()`, `get_selection_range()` (start/end character offsets), `get_document_context_for_chat()`, and marker injection. Context is refreshed every Send; the single `[DOCUMENT CONTENT]` message is replaced so conversation history grows without duplicating the document. Both sidebar and menu "Chat with Document" use this. Scope: Chat with Document only; Extend Selection / Edit Selection are legacy and unchanged. Very long selections are capped (e.g. 2000 chars) so context stays usable.
- **Thinking display**: When the AI finishes thinking we append a newline after ` /thinking` so the following response starts on a new line.
- **Translation behavior**: Models were refusing translation ("I don't have a translation tool"). Prompt now explicitly states: "You CAN translate. Call get_document_text, translate the content yourself, then replace_text or search_and_replace_all. NEVER refuse." Result: model correctly uses get_document_text → translate → replace_text.
- **Reasoning verbosity**: Added `reasoning: { effort: 'minimal' }` to all chat requests (provider-agnostic). Thinking is still displayed for progress; model may remain verbose but no longer wastes tokens arguing with itself about whether it can perform tasks.
- **Prompt brevity**: "Keep reasoning minimal, then act. Do not repeat conclusions or over-explain." Reduces circular reasoning in thinking output.
- **Reasoning/thinking tokens**: Streamed and displayed as `[Thinking] ... /thinking` in the response area (progress indicator).
- **Auto-scroll**: Response area automatically tracks to the bottom during streaming and tool calls.
- **Undo grouping**: Tool-calling rounds are wrapped in an `UndoManager` context (`AI Edit`), allowing users to revert all AI changes from a single turn with one Ctrl+Z.

Key files:
- core/document.py -- get_full_document_text(), get_document_end(), get_selection_range(), get_document_context_for_chat() (start/end excerpts + inline selection markers)
- core/async_stream.py -- run_stream_completion_async(): worker + queue + main-thread drain loop (used by sidebar simple stream and by main.py for Writer/Calc streaming)
- chat_panel.py -- ChatSession (conversation history), SendButtonListener (tool-calling loop with queue+drain in _start_tool_calling_async), ClearButtonListener, ChatPanelElement/ChatToolPanel/ChatPanelFactory (sidebar plumbing)
- document_tools.py -- WRITER_TOOLS JSON schemas, executor functions, TOOL_DISPATCH table
- main.py -- uses run_stream_completion_async for Extend/Edit/menu Chat and Calc; API plumbing in core/api.py
- LocalWriterDialogs/ChatPanelDialog.xdl -- compact fixed-size panel layout (120x180 AppFont units)

**Document context design decisions (for future reference):**
- Selection/cursor is represented **inside the document** as inline markers, not a separate block, so there is no duplicated text and the model unambiguously knows which span is the user's focus (or where the cursor is for insertion).
- When there is no selection, both markers are placed at the cursor position so the model sees where text would be inserted.
- Context is refreshed every Send; the single [DOCUMENT CONTENT] message is replaced (not appended), so the conversation history grows without sending the document again and again.
- Scope: Chat with Document only; Extend Selection and Edit Selection are legacy and were not changed.
- Multiselect can be added later with the same approach (multiple marker pairs).

**Streaming/threading design (for future reference):**
- Use **pure Python** for the streaming pipeline: worker thread + `queue.Queue` + main-thread drain loop calling `toolkit.processEventsToIdle()`. Do **not** use UNO Timer or `XTimerListener` for draining—in the sidebar context `com.sun.star.util.XTimerListener` is not available (getClass/import fails). The queue is the only cross-thread interface; UNO is limited to creating the toolkit by string name and calling `processEventsToIdle()`. This pattern is used in both `chat_panel.py` (tool-calling and simple stream) and `core/async_stream.py` (Writer/Calc). Multiple chunks can be applied between `processEventsToIdle()` calls, giving fewer repaints and faster perceived speed.

Known issue: The panel uses a fixed layout (no dynamic resizing). The PanelResizeListener was removed because the sidebar's resize lifecycle gives the panel a very large initial height before settling, which positions controls off-screen. See FIXME comments in chat_panel.py. The XDL is set to a compact fixed size that works at the default sidebar width.


Phase 1: Conversation History and Chat State -- DONE

Implemented:
- ChatSession class in chat_panel.py holds messages list (system, user, assistant, tool roles)
- System prompt and document context injected as first messages, refreshed each turn (single [DOCUMENT CONTENT] message replaced, not appended)
- Document context built by get_document_context_for_chat(): start + end excerpts, inline [SELECTION_START]/[SELECTION_END] at cursor/selection positions (no separate block, no duplication)
- Conversation accumulates in response area with "You:" / "AI:" prefixes
- Clear button resets conversation history and UI


Phase 2: Tool-Calling Infrastructure in the API Layer -- DONE

Implemented in main.py:
- make_chat_request(messages, max_tokens, tools, stream) -- builds chat/completions request with optional tools array
- request_with_tools(messages, max_tokens, tools) -- non-streaming request that parses tool_calls from the response
- stream_chat_response(messages, max_tokens, append_callback) -- streaming text-only response for final AI replies
- Non-streaming used for tool-calling rounds (simpler parsing), streaming for final text response


Phase 3: Writer Document Tools -- DONE

Implemented in document_tools.py with 8 curated tools:
1. replace_text -- find first occurrence and replace (UNO SearchDescriptor)
2. search_and_replace_all -- replace all occurrences (UNO ReplaceDescriptor)
3. insert_text -- insert at beginning, end, before/after selection
4. get_selection -- return currently selected text
5. replace_selection -- replace selected text
6. format_text -- bold, italic, underline, strikethrough, font size, color (CharWeight, CharPosture, etc.)
7. set_paragraph_style -- apply named paragraph style (ParaStyleName)
8. get_document_text -- return full or truncated document text

Each tool function receives (model, args, ctx) and returns JSON result string. TOOL_DISPATCH maps names to functions. execute_tool() handles dispatch and error wrapping.


Phase 4: The Tool-Calling Conversation Loop -- DONE

Implemented in chat_panel.py SendButtonListener:
- **Tool path**: `_start_tool_calling_async()` — worker thread + `queue.Queue` + main-thread drain loop with `toolkit.processEventsToIdle()` (pure Python; no UNO Timer). Worker runs `stream_request_with_tools`, puts chunk/thinking/stream_done/error/stopped on queue; main thread drains and updates UI. Same pattern as `core/async_stream.run_stream_completion_async()` for consistency.
- **Simple stream**: When api_type is not "chat", uses `run_stream_completion_async()` (same queue+drain pattern).
- Multi-round tool calling (up to MAX_TOOL_ROUNDS); streaming for final text-only response.
- Status updates shown in status label: "Thinking...", "Calling replace_text...", "Streaming response..."
- _ensure_extension_on_path() resolves sys.path issues for cross-module imports in extension context


Phase 5: System Prompt Engineering -- PARTIALLY DONE

Implemented:
- DEFAULT_SYSTEM_PROMPT in chat_panel.py with: (1) translation rule — get_document_text → translate → replace_text; never refuse; (2) edit/rewrite/transform — same pattern; (3) reasoning brevity — think briefly, act, avoid long chains; (4) post-edit confirmation (one sentence).
- main.py sends `reasoning: { effort: 'minimal' }` on all chat requests (provider-agnostic).

Still TODO:
- ~~Make chat_system_prompt editable in the Settings dialog~~ (DONE)
- Add instructions about formatting tools (bold, italic, paragraph styles) so the AI uses them effectively


Phase 6: UI Polish -- PARTIALLY DONE

Done:
- Clear button added (next to Send)
- Status label added (shows "Thinking...", "Calling tool_name...", "Streaming response...", etc.)
- Query field is multiline with vertical scrollbar
- Response area is multiline with vertical scrollbar and read-only
- Auto-scroll response area to bottom after each update
- Conversation turns prefixed with "You:" / "AI:"

TODO:
- Enter-to-send key listener (requires XKeyListener)
- Disable Send button during API call (busy state)
- FIXME: Dynamic resizing -- panel uses fixed XDL layout (120x180 AppFont). PanelResizeListener was removed because the sidebar gives a large initial height (1375px) before settling, positioning controls off-screen. Needs investigation into sidebar resize lifecycle. See FIXME comments in chat_panel.py.


Phase 7: Configuration and Settings -- MOSTLY DONE

New config keys to expose in SettingsDialog.xdl and settings handling in main.py:
- chat_system_prompt -- DONE: multiline field in Settings dialog
- chat_max_tokens -- DONE: in Settings dialog
- chat_context_length -- DONE: in Settings dialog


Phase 8: Robustness and Error Handling -- PARTIALLY DONE

Done:
- Tool execution errors caught and returned as {"status": "error", "message": "..."} to the AI
- API errors displayed in the chat panel response area (not modal dialogs)
- Fallback to simple streaming when api_type is not "chat" (completions-only models)
- Iteration limit of 10 tool-calling rounds
- Undo support: wrap tool-calling rounds in UndoManager context (model.getUndoManager().enterUndoContext("AI Edit") / leaveUndoContext()) so user can Ctrl+Z all AI edits as one step

TODO:
- Better error messages for common failures (network timeout, invalid API key, etc.)


File Organization

- chat_panel.py -- ChatSession, SendButtonListener (tool-calling loop), ClearButtonListener, sidebar plumbing
- document_tools.py -- WRITER_TOOLS JSON schemas, tool executor functions, TOOL_DISPATCH
- main.py -- make_chat_request, request_with_tools, stream_chat_response
- LocalWriterDialogs/ChatPanelDialog.xdl -- compact fixed panel layout
- build.sh -- includes document_tools.py in .oxt


What To Work On Next

Priority order for remaining work:

1. Test end-to-end: Install extension, open a Writer document, try asking the AI to edit text, replace words, format bold/italic. Verify tool calls work and document is modified.
2. ~~Settings UI (Phase 7): Expose chat_system_prompt, chat_max_tokens, chat_context_length~~ (DONE).
3. System prompt tuning (Phase 5): Iterate on the default prompt based on real testing.
4. UI polish (Phase 6 remaining): Enter-to-send, auto-scroll, busy state (disable Send during API call).
5. Dynamic resize (Phase 6 FIXME): Investigate sidebar resize lifecycle and re-implement PanelResizeListener. See FIXME comments in chat_panel.py.


Advanced Roadmap (Future Phases)

Key findings: Phase 1 scope was overreaching — `get_document_structure()` and viewport content are expensive/fragile in UNO. Safety and observability must come before new features. Prioritize low-risk context primitives first.

**Phase 0: Foundation and Safety (Prerequisite)** -- DONE
- Shared API helper and request timeout (implemented in main.py)
- Unified user-facing error handling (message boxes; never write errors into document)
- Token/context budget guardrails
- Structured logging toggles

**Phase 1: Enhanced Context Awareness** -- PARTIALLY DONE (for Chat with Document)
- **Done**: `get_selection_range(model)` returns (start_offset, end_offset) for cursor/selection; `get_document_end(model, max_chars)`; `get_document_context_for_chat()` builds start/end excerpts and injects [SELECTION_START]/[SELECTION_END] inline (no separate block). Used by sidebar and menu Chat with Document only.
- Still open: `get_document_metadata()`, `get_style_information()`
- Deferred: `get_document_structure()`, `get_visible_content()` (too hard/expensive)

**Phase 2: Intelligent Editing Assistance**
- Predictive continuation (future-words suggestions, propose-first)
- Advanced text manipulation (regex search/replace, pattern styling)
- Context-aware suggestions (grammar, style, alternatives)
- Document analysis (readability, key concepts, summary)

**Phase 3: Versioning and Safer Experimentation**
- `create_snapshot()`, `compare_versions()`, `revert_changes()`

**Phase 4: Domain-Specific Intelligence**
- Document type detection, templates, domain-specific tools
- Integration with external knowledge (web search, knowledge bases)

**Research / Deferred:** Real-time collaboration, multi-document workflow, full document structure.

**Risk Register:** Model refusal (mitigated by explicit prompt); UNO API limits (defer heavy structure); large documents (context budget); tool schema changes (backward compatibility).

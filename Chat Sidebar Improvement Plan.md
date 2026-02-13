Chat Sidebar Improvement Plan

Current State (updated 2026-02-13)

The chat sidebar has conversation history, tool-calling, and 8 curated Writer document tools. The AI can read, search, replace, format, and style text in the open Writer document via the OpenAI-compatible tool-calling protocol.

**Recent improvements (Feb 2026):**
- **Translation behavior**: Models were refusing translation ("I don't have a translation tool"). Prompt now explicitly states: "You CAN translate. Call get_document_text, translate the content yourself, then replace_text or search_and_replace_all. NEVER refuse." Result: model correctly uses get_document_text → translate → replace_text.
- **Reasoning verbosity**: Added `reasoning: { effort: 'minimal' }` to all chat requests (provider-agnostic). Thinking is still displayed for progress; model may remain verbose but no longer wastes tokens arguing with itself about whether it can perform tasks.
- **Prompt brevity**: "Keep reasoning minimal, then act. Do not repeat conclusions or over-explain." Reduces circular reasoning in thinking output.
- **Reasoning/thinking tokens**: Streamed and displayed as `[Thinking] ... /thinking` in the response area (progress indicator).

Key files:
- chat_panel.py -- ChatSession (conversation history), SendButtonListener (tool-calling loop), ClearButtonListener, ChatPanelElement/ChatToolPanel/ChatPanelFactory (sidebar plumbing)
- document_tools.py -- WRITER_TOOLS JSON schemas, executor functions, TOOL_DISPATCH table
- main.py -- make_chat_request(), request_with_tools(), stream_chat_response() (API plumbing for tool-calling)
- LocalWriterDialogs/ChatPanelDialog.xdl -- compact fixed-size panel layout (120x180 AppFont units)

Known issue: The panel uses a fixed layout (no dynamic resizing). The PanelResizeListener was removed because the sidebar's resize lifecycle gives the panel a very large initial height before settling, which positions controls off-screen. See FIXME comments in chat_panel.py. The XDL is set to a compact fixed size that works at the default sidebar width.


Phase 1: Conversation History and Chat State -- DONE

Implemented:
- ChatSession class in chat_panel.py holds messages list (system, user, assistant, tool roles)
- System prompt and document context injected as first messages, refreshed each turn
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
- _do_tool_calling_loop() orchestrates multi-round tool calling (up to 10 iterations)
- Non-streaming request_with_tools() for tool-calling rounds (simpler parsing)
- Streaming stream_chat_response() for final text-only response
- Status updates shown in status label: "Thinking...", "Calling replace_text...", "Streaming response..."
- Falls back to simple streaming (_do_simple_stream) when api_type is not "chat"
- _ensure_extension_on_path() resolves sys.path issues for cross-module imports in extension context


Phase 5: System Prompt Engineering -- PARTIALLY DONE

Implemented:
- DEFAULT_SYSTEM_PROMPT in chat_panel.py with: (1) translation rule — get_document_text → translate → replace_text; never refuse; (2) edit/rewrite/transform — same pattern; (3) reasoning brevity — think briefly, act, avoid long chains; (4) post-edit confirmation (one sentence).
- main.py sends `reasoning: { effort: 'minimal' }` on all chat requests (provider-agnostic).

Still TODO:
- Make chat_system_prompt editable in the Settings dialog
- Add instructions about formatting tools (bold, italic, paragraph styles) so the AI uses them effectively


Phase 6: UI Polish -- PARTIALLY DONE

Done:
- Clear button added (next to Send)
- Status label added (shows "Thinking...", "Calling tool_name...", "Streaming response...", etc.)
- Query field is multiline with vertical scrollbar
- Response area is multiline with vertical scrollbar and read-only
- Conversation turns prefixed with "You:" / "AI:"

TODO:
- Enter-to-send key listener (requires XKeyListener)
- Auto-scroll response area to bottom after each update
- Disable Send button during API call (busy state)
- FIXME: Dynamic resizing -- panel uses fixed XDL layout (120x180 AppFont). PanelResizeListener was removed because the sidebar gives a large initial height (1375px) before settling, positioning controls off-screen. Needs investigation into sidebar resize lifecycle. See FIXME comments in chat_panel.py.


Phase 7: Configuration and Settings -- TODO

New config keys to expose in SettingsDialog.xdl and settings handling in main.py:
- chat_system_prompt -- multiline field (already in config, not yet in Settings dialog)
- chat_max_tokens -- already used, not yet in Settings
- chat_context_length -- already used, not yet in Settings
- chat_tool_calling -- boolean toggle to enable/disable tool-calling (some models don't support it)


Phase 8: Robustness and Error Handling -- PARTIALLY DONE

Done:
- Tool execution errors caught and returned as {"status": "error", "message": "..."} to the AI
- API errors displayed in the chat panel response area (not modal dialogs)
- Fallback to simple streaming when api_type is not "chat" (completions-only models)
- Iteration limit of 10 tool-calling rounds

TODO:
- Undo support: wrap tool-calling rounds in UndoManager context (model.getUndoManager().enterUndoContext("AI Edit") / leaveUndoContext()) so user can Ctrl+Z all AI edits as one step
- chat_tool_calling config flag to let users disable tool-calling for models that don't support it
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
2. Undo support (Phase 8): Wrap tool execution in UndoManager context so Ctrl+Z reverts AI edits.
3. Settings UI (Phase 7): Expose chat_system_prompt, chat_max_tokens, chat_context_length, chat_tool_calling in Settings dialog.
4. System prompt tuning (Phase 5): Iterate on the default prompt based on real testing.
5. UI polish (Phase 6 remaining): Enter-to-send, auto-scroll, busy state (disable Send during API call).
6. Dynamic resize (Phase 6 FIXME): Investigate sidebar resize lifecycle and re-implement PanelResizeListener. See FIXME comments in chat_panel.py.


Advanced Roadmap (Future Phases)

Key findings: Phase 1 scope was overreaching — `get_document_structure()` and viewport content are expensive/fragile in UNO. Safety and observability must come before new features. Prioritize low-risk context primitives first.

**Phase 0: Foundation and Safety (Prerequisite)**
- Shared API helper and request timeout
- Unified user-facing error handling (message boxes; never write errors into document)
- Token/context budget guardrails
- Structured logging toggles

**Phase 1: Enhanced Context Awareness**
- `get_selection_context()`, `get_cursor_context()`, lightweight `get_current_position()`
- `get_document_metadata()`, `get_style_information()`
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

# AGENTS.md — Context for AI Assistants

**Assume the reader knows nothing about this project.** This file summarizes what was learned and what to do next.

> [!IMPORTANT]
> **AI Assistants: You MUST update this file after making (nontrivial) changes to the project.** This ensures the next assistant has all the up-to-date context without needing manual user intervention.

---

## 1. Project Overview

**LocalWriter** is a LibreOffice extension (Python + UNO) that adds generative AI editing to Writer, Calc, and Draw:

- **Extend Selection** (Ctrl+Q): Model continues the selected text
- **Edit Selection** (Ctrl+E): User enters instructions; model rewrites the selection
- **Chat with Document** (Writer, Calc, and Draw): (a) **Sidebar panel**: LocalWriter deck in the right sidebar, multi-turn chat with tool-calling that edits the document; (b) **Menu item** (fallback): Opens input dialog, appends response to end of document (Writer) or to "AI Response" sheet (Calc/Draw)
- **Settings**: Configure endpoint, model, API key, temperature, request timeout, etc.
- **Calc** `=PROMPT()`: Cell formula that calls the model

**Connection Management**: LocalWriter includes built-in connection management in `core/api.py` that maintains persistent HTTP/HTTPS connections, significantly reducing overhead for sequential requests to the same endpoint.

Config is stored in `localwriter.json` in LibreOffice's user config directory. See `CONFIG_EXAMPLES.md` for examples (Ollama, OpenWebUI, OpenRouter, etc.).

---

## 2. Repository Structure

```
localwriter/
├── main.py              # MainJob: trigger(), dialogs, delegates to core
├── core/                # Shared core logic
│   ├── config.py        # get_config, set_config, get_api_config (localwriter.json)
│   ├── api.py           # LlmClient: streaming, chat, tool-calling, connection management
│   ├── document.py      # get_full_document_text, get_document_end, get_selection_range, get_document_length, get_text_cursor_at_range, get_document_context_for_chat (Writer/Calc), get_calc_context_for_chat (Calc)
│   ├── logging.py       # init_logging, debug_log(msg, context), agent_log; single debug file + optional agent log
│   ├── constants.py     # DEFAULT_CHAT_SYSTEM_PROMPT, DEFAULT_CALC_CHAT_SYSTEM_PROMPT, get_chat_system_prompt_for_document
│   ├── async_stream.py  # run_stream_completion_async: worker + queue + main-thread drain (no UNO Timer)
│   ├── calc_bridge.py   # in-process get_active_document, get_active_sheet, etc.
│   ├── calc_address_utils.py
│   ├── calc_inspector.py
│   ├── calc_sheet_analyzer.py
│   ├── calc_error_detector.py
│   ├── calc_manipulator.py
│   ├── calc_tools.py    # CALC_TOOLS (schemas), execute_calc_tool
│   ├── draw_bridge.py   # Draw/Impress page and shape manipulation
│   └── draw_tools.py    # DRAW_TOOLS (schemas), execute_draw_tool (pages, shapes)
├── prompt_function.py   # Calc =PROMPT() formula
├── chat_panel.py        # Chat sidebar: ChatPanelFactory, ChatPanelElement, ChatToolPanel
├── document_tools.py    # WRITER_TOOLS (get_markdown, apply_markdown only), execute_tool; legacy tools present but not exposed
├── markdown_support.py  # Markdown read/write: document_to_markdown, apply_markdown (hidden doc + transferable)
├── XPromptFunction.rdb  # Type library for PromptFunction
├── LocalWriterDialogs/  # XDL dialogs (XML, Map AppFont units)
│   ├── SettingsDialog.xdl
│   ├── EditInputDialog.xdl
│   ├── ChatPanelDialog.xdl   # Chat panel UI (response, query, send)
│   ├── dialog.xlb           # Library index
│   └── script.xlb          # Empty (required for Basic library)
├── registry/
│   └── org/openoffice/Office/UI/
│       ├── Sidebar.xcu      # LocalWriter deck + ChatPanel
│       └── Factories.xcu    # ChatPanelFactory registration
├── META-INF/manifest.xml
├── Addons.xcu             # Menu entries
├── Accelerators.xcu       # Ctrl+Q, Ctrl+E
├── description.xml
├── build.sh               # Creates localwriter.oxt
├── assets/                # icon_16.png, logo.png
├── localwriter.json.example
└── CONFIG_EXAMPLES.md     # Config templates
```

---

## 3. What Was Done (Dialog Refactor)

### Before
- Settings and Edit Input dialogs were built **programmatically** with `UnoControlDialog`, `UnoControlEditModel`, etc.
- Layout issues: wrong sizing, truncation, poor HiDPI behavior, no scrollbar

### After
- Both dialogs use **XDL files** (XML) loaded via `DialogProvider`
- `LocalWriterDialogs.SettingsDialog` — 12 config fields in a **compact side-by-side layout** (labels left, textfields right) to reduce vertical footprint.
- `LocalWriterDialogs.EditInputDialog` — label + text field + OK

### Key implementation details
- **DialogProvider with direct package URL**: Dialogs are loaded by their XDL file URL, not the Basic library script URL. This avoids a deadlock that occurs when the sidebar panel is also registered as a UNO component.
  ```python
  pip = self.ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
  base_url = pip.getPackageLocation("org.extension.localwriter")
  dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
  dlg = dp.createDialog(base_url + "/LocalWriterDialogs/SettingsDialog.xdl")
  ```
- **Use `self.ctx`**, not `uno.getComponentContext()` — the extension's component context is required for `PackageInformationProvider` singleton lookup.
- **Populate**: `dlg.getControl("endpoint").getModel().Text = value`
- **Read**: `dlg.getControl("endpoint").getModel().Text` after `dlg.execute()`
- **Manifest** must register the Basic library: `LocalWriterDialogs/` with `application/vnd.sun.star.basic-library`

---

## 3b. Chat with Document (Sidebar + Menu)

The sidebar and menu Chat work for **Writer and Calc** (same deck/UI; ContextList includes `com.sun.star.sheet.SpreadsheetDocument`).

- **Sidebar panel**: LocalWriter deck in Writer's or Calc's right sidebar; panel has Response area, Ask field, Send button, Stop button, and Clear button.
  - **Auto-scroll**: The response area automatically scrolls to the bottom as text is streamed or tools are called, ensuring the latest AI output is always visible.
  - **Stop button**: A dedicated "Stop" button allows users to halt AI generation mid-stream. It is enabled only while the AI is active and disabled when idle.
  - **Undo grouping**: AI edits performed during tool-calling rounds are grouped into a single undo context ("AI Edit"). Users can revert all changes from an AI turn with a single Ctrl+Z.
  - **Send/Stop button state (lifecycle-based)**: "AI is busy" is defined by the single run of `actionPerformed`: Send is disabled (Stop enabled) at the **start** of the run, and re-enabled (Stop disabled) **only** in the `finally` block when `_do_send()` has returned. No dependence on internal job_done or drain-loop state. `_set_button_states(send_enabled, stop_enabled)` uses per-control try/except (prefer `control.setEnable()`, fallback to model `Enabled`) so a UNO failure on one control cannot leave Send stuck disabled. `SendButtonListener._send_busy` is set True at run start and False in finally for external checks. This prevents multiple concurrent requests.
- **Implementation**: `chat_panel.py` (ChatPanelFactory, ChatPanelElement, ChatToolPanel); `ContainerWindowProvider` + `ChatPanelDialog.xdl`; `setVisible(True)` required after `createContainerWindow()`.
- **Tool-calling**: `chat_panel.py` (and the menu path in `main.py`) detect document type using robust service-based identification (`supportsService`) in `core/document.py`. This ensures Writer, Calc, and Draw/Impress documents are never misidentified. **Gotcha**: `hasattr(model, "getDrawPages")` is `True` for Writer (drawing layer for shapes), so strict service checks are required.
    - **Writer**: `com.sun.star.text.TextDocument`. `document_tools.py` exposes **WRITER_TOOLS** = `get_markdown`, `apply_markdown`; implementations in `core/format_support.py`.
    - **Calc**: `com.sun.star.sheet.SpreadsheetDocument`. `core/calc_tools.py` exposes **CALC_TOOLS** and `execute_calc_tool`; core logic in `core/calc_*.py`.
    - **Draw/Impress**: `com.sun.star.drawing.DrawingDocument` or `com.sun.star.presentation.PresentationDocument`. `core/draw_tools.py` exposes **DRAW_TOOLS** and `execute_draw_tool`.
- **Menu fallback**: Menu item "Chat with Document" opens input dialog, streams response with no tool-calling. **Writer**: appends to document end. **Calc**: streams to "AI Response" sheet. Both sidebar and menu use the same robust document detection.
- **Config keys** (used by chat): `chat_context_length`, `chat_max_tokens`, `additional_instructions` (in Settings).
- **Unified Prompt System**: See Section 3c.

### Document context for chat (current implementation)

- **Refreshed every Send**: On each user message we re-read the document and rebuild the context; the single `[DOCUMENT CONTENT]` system message is **replaced** (not appended), so the conversation history grows but the context block does not duplicate.
- **Writer**: `core/document.py` provides `get_document_context_for_chat(model, max_context, include_end=True, include_selection=True, ctx=None)` which builds one string with: document length (metadata); **start and end excerpts** (for long docs, first/last half of `chat_context_length` with `[DOCUMENT START]` / `[DOCUMENT END]` / `[END DOCUMENT]` labels); **selection/cursor**: `(start_offset, end_offset)` from `get_selection_range(model)` with **`[SELECTION_START]`** / **`[SELECTION_END]`** injected at those positions (capped for very long selections). Helpers: `get_document_end`, `get_selection_range`, `get_document_length`, `get_text_cursor_at_range`, `_inject_markers_into_excerpt()`).
- **Calc**: For Calc documents, `get_document_context_for_chat(..., ctx=...)` delegates to `get_calc_context_for_chat(model, max_context, ctx)` in `core/document.py`. **`ctx` is required for Calc** (component context from panel or MainJob); do not use `uno.getComponentContext()` in this path. Calc context includes: document URL, active sheet name, used range, column headers, current selection range, and (for small selections) selection content. See [Calc support from LibreCalc.md](Calc%20support%20from%20LibreCalc.md).
- **Scope**: Chat with Document only. Extend Selection and Edit Selection are legacy and unchanged.

### Markdown tool-calling (current)

- **get_markdown**: Returns the document (or selection/range) as Markdown. Parameters: optional `max_chars`, optional `scope` (`"full"` | `"selection"` | `"range"`); when `scope="range"`, required `start` and `end` (character offsets). Result JSON includes **`document_length`** so the AI can replace the whole doc with `apply_markdown(target="range", start=0, end=document_length)` or use `target="full"`. When `scope="range"`, result also includes `start` and `end` echoed back. Implementation: for full scope tries `XStorable.storeToURL` with FilterName `"Markdown"` to a temp file; on failure or for selection/range uses structural fallback (paragraph enumeration + `ParaStyleName` → headings, lists, blockquote). See `markdown_support.py`.
- **apply_markdown / apply_document_content**: Inserts or replaces content using Markdown/HTML **with native formatting**, or plain text **with format preservation**. Parameters: `content` (string), `target` (`"beginning"` | `"end"` | `"selection"` | `"search"` | **`"full"`** | **`"range"`**); when `target="search"`, also `search`, optional `all_matches`, `case_sensitive`; when **`target="range"`**, required **`start`** and **`end`** (character offsets). **`target="full"`** replaces the entire document (clear all, insert at start). **`target="range"`** replaces the character span `[start, end)` with the markdown (no need to send the original text back). Preferred flow for "make my resume look nice" or reformat: call `get_markdown(scope="full")` once, then `apply_markdown(markdown=<new content>, target="full")` or `target="range", start=0, end=document_length` — **only the new markdown is sent**, never the original document text. Implementation: writes markdown to a temp `.md` file, then **`cursor.insertDocumentFromURL(file_url, {FilterName: "Markdown"})`** at the chosen position; for `"full"` uses `_insert_markdown_full`; for `"range"` uses `get_text_cursor_at_range()` then `setString("")` and `insertDocumentFromURL`. See `format_support.py`. **Note**: Both Markdown and HTML injection are implemented; further testing will determine the default path for rich formatting and layout control.
  - **Format-preserving replacement (auto-detected)**: When `target="search"` and the replacement content is **plain text** (no Markdown/HTML markup detected by `_content_has_markup()`), the system automatically uses `_replace_text_preserving_format()` instead of `insertDocumentFromURL`. This replaces text **character-by-character**, so every per-character property (CharBackColor, CharColor, CharWeight, CharHeight, CharPosture, CharUnderline, etc.) is preserved — including exotic formatting the AI has no knowledge of. If the new text is longer, extra characters inherit formatting from the last original character; if shorter, leftover characters are deleted.
    - **Auto-detect logic** (`_content_has_markup()`): Scans content for common Markdown patterns (`**`, `# `, `` ` ` ``, `|---`) and HTML tags (`<b>`, `<table>`, `</`, etc.). If markup is found → import path (existing behavior). If plain text → format-preserving path. Deliberately errs on the side of detecting markup, since a false positive just falls back to the existing behavior. No tool schema changes and no AI decision needed — works identically for 30B local models and frontier models.
    - **Why auto-detect works**: The operation type and content type are naturally correlated. Small text edits like "change Joe Blow to Jane Doe" are sent as `target="search"` with plain text content like `"Jane Doe"` — auto-detect sees no markup → preserves all formatting (bold, italic, background colors, everything). Structural rewrites like "make this look pretty" or "convert to a table" naturally use `target="full"` or `target="range"` with markdown/HTML content — the auto-detect sees markup → uses the import path to apply the new formatting. No system prompt guidance is needed because the AI's natural behavior already routes correctly.
    - **Important subtlety**: The format-preserving path preserves ALL character properties, not just background colors. Bold (`CharWeight`), italic (`CharPosture`), underline, font size, font color — these are all per-character UNO properties that survive the single-character `setString()` call. So if the AI replaces `"Joe"` (bold+red-bg) with `"Jan"` (plain text), the result is `"Jan"` still bold with the same red background. The AI does NOT need to re-specify formatting it read from the document.
    - **Edge case**: If the AI unnecessarily wraps a simple replacement in markdown (e.g., sends `"**Jane** Doe"` instead of `"Jane Doe"`), the `**` triggers markup detection and the import path is used, losing background colors. This is a model behavior quirk, not a code issue — the import path is what we had before this feature, so it's no worse than previous behavior. Future hybrid approach: strip markup to plain text, do format-preserving replacement, then apply the markup as character properties on top.
    - **Implementation**: `_replace_text_preserving_format()` and `_apply_preserving_format_at_search()` in `format_support.py`. Tests in `format_tests.py` verify `CharBackColor` preservation for same-length, longer, and shorter replacements.


### System prompt and reasoning (latest)

- **Chat** uses `get_chat_system_prompt_for_document(model, additional_instructions)` in `core/constants.py` so the correct prompt is chosen by document type: **Writer** → `DEFAULT_CHAT_SYSTEM_PROMPT` + additional_instructions (get_markdown/apply_markdown, presume document editing, translate/proofread, no preamble); **Calc** → `DEFAULT_CALC_CHAT_SYSTEM_PROMPT` + additional_instructions (semicolon formula syntax, 4-step workflow: understand → get state → use tools → short confirmation; tools grouped READ / WRITE & FORMAT / SHEET MANAGEMENT / CHART / ERRORS). Used by both sidebar and menu Chat.
- **Reasoning tokens**: `main.py` sends `reasoning: { effort: 'minimal' }` on all chat requests (OpenRouter and other providers).
- **Thinking display**: Reasoning tokens are shown in the response area as `[Thinking] ... /thinking`. When thinking ends we append a newline after ` /thinking` so the following response text starts on a new line.

See [CHAT_SIDEBAR_IMPLEMENTATION.md](CHAT_SIDEBAR_IMPLEMENTATION.md) for implementation details.

- **Streaming I/O**: pure Python queue + main-thread drain
  All streaming paths (sidebar tool-calling, sidebar simple stream, Writer Extend/Edit/menu Chat, Calc) use the same pattern so the UI stays responsive without relying on UNO Timer/listeners:
  - **Worker thread**: Runs blocking API/streaming (e.g. `stream_completion`, `stream_request_with_tools`), puts items on a **`queue.Queue`** (`("chunk", text)`, `("thinking", text)`, `("stream_done", ...)`, `("error", e)`, `("stopped",)`).
  - **Main thread**: After starting the worker, runs a **drain loop**: `q.get(timeout=0.1)` → process item (append text, update status, call on_done/on_error) → **`toolkit.processEventsToIdle()`**. Repeats until job_done.
  - **Connection Keep-Alive**: `LlmClient` uses `http.client.HTTPConnection` (or `HTTPSConnection`) for persistent connections. The client instance is cached in `chat_panel.py` (sidebar), `main.py` (MainJob), and `prompt_function.py` (Calc =PROMPT()) to reuse connections across multiple requests, significantly improving performance for multi-turn chat and cell recalculations.

---

## 3d. Multi-Document Scoping Fix

**Issue**: When multiple Calc (or Writer) documents were open, the AI agent in one sidebar would edit the wrong document because tool executions and context building used global `desktop.getCurrentComponent()` instead of the document associated with the sidebar's frame.

**Root Cause**: Sidebar panels were not properly scoped to their respective documents. The `CalcBridge` and document context functions relied on the global active document, which changes with user focus.

**Fix**:
- Modified `CalcBridge.__init__()` and `DrawBridge.__init__()` to take a specific document (`doc`) instead of global context (`ctx`).
- Updated `execute_calc_tool()`, `execute_draw_tool()`, and `execute_tool()` to take `doc` directly.
- Changed `get_document_context_for_chat()` and `get_calc_context_for_chat()` to take `doc` instead of `ctx`.
- In `chat_panel.py`, each panel uses `self.doc = self.xFrame.getController().getModel()` and passes it to all operations.
- Menu chat continues to use the active document as expected.

**Result**: Each sidebar panel now operates independently on its associated document, preventing cross-contamination when multiple documents are open.

---

## 3c. Unified Prompt System with History

The "Additional Instructions" (previously system prompts) are now unified across **Chat, Edit Selection, and Extend Selection** into a single configuration key with a history dropdown (ComboBox).

- **Implementation**:
    - **Shared LRU Logic**: `core/config.py` contains `populate_combobox_with_lru()` and `update_lru_history()` used by all dialogs and features.
    - **Unified Key**: All features use the `additional_instructions` config key. LEGACY: The key was renamed from `chat_system_prompt` to avoid legacy data from "full system prompt" iterations.
    - **History Persistence**: Up to 10 entries are stored in `prompt_lru` (JSON list).
- **Behavior**:
    - **Dropdown (ComboBox)**: All dialogs (Settings, Edit Selection input, Chat sidebar) show a dropdown of recent instructions.
    - **Multiline Support**: LibreOffice ComboBoxes are single-line. We display a preview in the list and restore full multiline content upon selection.
    - **Prompt Construction**:
        - **Chat**: `get_chat_system_prompt_for_document(model, additional_instructions)` so Writer and Calc get the correct base prompt; in both cases `additional_instructions` is appended.
        - **Edit/Extend**: `additional_instructions` is used as the primary guiding prompt (representing the special system role for that edit).

---

## 4. Shared Helpers

- **`MainJob._apply_settings_result(self, result)`** (`main.py`): Applies settings dialog result to config. Used by both Writer and Calc settings branches.
- **`core/logging.py`**:
  - Call `init_logging(ctx)` once from an entry point (e.g. start of `trigger`, or when the chat panel wires controls). Sets global log paths and optional `enable_agent_log` from config.
  - `debug_log(msg, context=None)` — single debug file. Writes to `localwriter_debug.log` in user config dir (or `~/localwriter_debug.log`). Use `context="API"`, `"Chat"`, or `"Markdown"` for prefixed lines. No ctx passed at write time.
  - `agent_log(location, message, ...)` — NDJSON to `localwriter_agent.log` (user config or `~/`), only if config `enable_agent_log` is true.
  - Watchdog: `update_activity_state(phase, ...)`, `start_watchdog_thread(ctx, status_control)` for hang detection (logs and status "Hung: ..." if no activity for threshold).
- **`SendButtonListener._send_busy`** (`chat_panel.py`): Boolean; True from run start until the `finally` block of `actionPerformed` (single source of truth for "is the AI running?"). Used together with lifecycle-based `_set_button_states(send_enabled, stop_enabled)`.
- **`core/api.format_error_for_display(e)`**: Returns user-friendly error string for cells/dialogs (e.g. `"Error: Connection refused..."`).

---

## 4. Critical Learnings: LibreOffice Dialogs

### Units
- **Map AppFont** units: device- and HiDPI-independent. 1 unit ≈ 1/4 char width, 1/8 char height.
- XDL uses Map AppFont for `dlg:left`, `dlg:top`, `dlg:width`, `dlg:height`
- **Do not** use raw pixels for layout; they break on HiDPI

### No automatic layout
- LibreOffice dialogs have **no flexbox, no auto-size**. Every control needs explicit position/size.
- Scrollbars require manual implementation (complex). Prefer splitting into tabs or keeping content compact.

### Recommended approach: XDL + DialogProvider (direct package URL)
- Design dialogs as **XDL files** (XML). Edit `LocalWriterDialogs/*.xdl` directly.
- Load via `DialogProvider.createDialog(base_url + "/LocalWriterDialogs/DialogName.xdl")` where `base_url` comes from `PackageInformationProvider.getPackageLocation()`.
- **Do NOT** use the Basic library script URL format (`vnd.sun.star.script:LibraryName.DialogName?location=application`) — it deadlocks when sidebar UNO components are also registered.
- The Dialog Editor in LibreOffice Basic produces XDL; you can also hand-write or generate it.

### XDL format (condensed)
- Root: `<dlg:window>` with `dlg:id`, `dlg:width`, `dlg:height`, `dlg:title`, `dlg:resizeable`
- Content: `<dlg:bulletinboard>` containing controls
- Controls: `dlg:text` (label), `dlg:textfield`, `dlg:button` with `dlg:id`, `dlg:left`, `dlg:top`, `dlg:width`, `dlg:height`, `dlg:value`
- DTD: `xmlscript/dtd/dialog.dtd` in LibreOffice source

### Compact layout
- Label height ~10, textfield height ~14, gap label→edit ~1, gap between rows ~2
- Margins ~8. Tighter = more compact but must stay readable.

---

## 4b. Critical Learnings: Format Preservation

### The Challenge
When replacing text (e.g., correcting a name), we must preserve character-level formatting (fonts, colors, bold/italic) even if the replacement text length differs. By default, LibreOffice replacements inherit the formatting of the *insertion point* (usually the character *before*), which wipes out specific formatting on the replaced text itself.

### The Solution: `_replace_text_preserving_format`
We implemented a custom engine in `core/format_support.py` that iterates character-by-character.
- **Same length**: 1:1 replacement, keeping each character's properties.
- **Longer**: 1:1 for the overlap, then insert extra chars inheriting from the last original char.
- **Shorter**: 1:1 for the overlap, then delete the leftover original chars.

### Critical Implementation Details (Gotchas)
1.  **"Insert After + Delete" Strategy (Robustness)**:
    - **Problem**: `setString()` on a selection is flaky at paragraph boundaries (often inherits formatting from the *next* char instead of the replaced one), and "insert and replace" can wipe attributes.
    - **Solution**: Do not replace in-place. Instead, **insert** the new character immediately *after* the old one (inheriting its exact attributes), then **delete** the old character.
    - **Optimization**: If `new_char == old_char`, skip the operation entirely.

2.  **Performance (O(N) Traversal)**:
    - **Don't** create a new cursor from the document start for every character (`O(N^2)`). This hangs for >500 chars (30s+).
    - **Do** use a single **persistent cursor** for traversal. Move it relative to its current position (`goRight(1)`).
    - **Note**: When using "Insert After + Delete", careful cursor management is needed to advance past the newly inserted character without losing sync. Use local `text.createTextCursorByRange(main_cursor)` clones for the insert/delete ops so the main traversal cursor stays stable.

3.  **ProcessEvents Reliability**:
    - **Warning**: `toolkit.processEvents()` can sometimes raise exceptions (especially in test environments or headless contexts). Always wrap it in a `try/except` block and disable if it fails.

2.  **Raw Content vs. HTML Wrapping**:

    - **The Bug**: AI often sends plain text. If `DOCUMENT_FORMAT="html"`, `_ensure_html_linebreaks` wraps this in `<html><body><p>...</p></body></html>`.
    - **The Injection**: If you pass this wrapped string to the format-preserving function, it will replace your document text with literal HTML source code (e.g., replacing "K" with "<", "e" with "h", "i" with "t", etc.), effectively destroying the document.
    - **The Fix**: Always modify `tool_apply_document_content` to capture `raw_content` *before* any HTML processing. Use `raw_content` for the format-preserving path. Use `content` (wrapped) only for the standard `insertDocumentFromURL` path.

3.  **Markup Detection Order**:
    - **Don't** run `_content_has_markup(content)` *after* HTML wrapping. It will always return True (because of the added tags), forcing the non-preserving path.
    - **Do** run it on the **raw input string** immediately.

4.  **Auto-Detection is Key**:
    - The AI doesn't know about `target="search"` vs `target="range"` for formatting. It just calls tools.
    - We must auto-detect plain text in **all** paths (`search`, `range`, `full`). If `content` is plain text, divert to `_replace_text_preserving_format`. This allows "Make this whole paragraph blue" (Markdown path) and "Correct spelling of 'Burtis'" (Preserving path) to work seamlessly with the same tool.


## 5. Config File

- **Path**: LibreOffice UserConfig directory + `localwriter.json`
  - Linux: `~/.config/libreoffice/4/user/localwriter.json` (or `24/user` for LO 24)
  - macOS: `~/Library/Application Support/LibreOffice/4/user/localwriter.json`
  - Windows: `%APPDATA%\LibreOffice\4\user\localwriter.json`
- **Single file**: No presets or multiple configs. To use a different setup (e.g. `localwriter.openrouter.json`), copy it to the path above as `localwriter.json`.
- **Settings dialog** reads/writes this file via `get_config()` / `set_config()` in `core/config.py`.
- **Chat-related keys** (used by `chat_panel.py` and menu Chat): `chat_context_length` (default 8000), `chat_max_tokens` (default 512 menu / 16384 sidebar), `additional_instructions`. Also `api_key`, `api_type` (in Settings) for OpenRouter/OpenAI-compatible endpoints.
- **Note**: `chat_context_length`, `chat_max_tokens`, `additional_instructions` are now in the Settings dialog.

---

## 5b. Log Files

- **Unified debug log**: `~/.config/libreoffice/4/user/config/localwriter_debug.log` (exact path; fallback `~/localwriter_debug.log` if user config dir not found). Written by `debug_log(msg, context=...)` with prefixes `[API]`, `[Chat]`, `[Markdown]`. Paths set once via `init_logging(ctx)`; no ctx needed at call sites.

- **Agent log** (NDJSON, optional): `localwriter_agent.log` in user config (or `~/`). Written by `agent_log(...)` only when config key `enable_agent_log` is true (default false). Used for hypothesis/debug tracking.
- **Watchdog**: If no activity for the threshold (e.g. 30s), a line is written to the debug log and the status control shows "Hung: ...".

---

## 6. Build and Install

```bash
bash build.sh
unopkg add localwriter.oxt   # or remove first: unopkg remove org.extension.localwriter
```

Restart LibreOffice after install/update. Test: menu **LocalWriter → Settings** and **LocalWriter → Edit Selection**.

---

## 7. What to Do Next

### High priority (from IMPROVEMENT_PLAN.md) — DONE
- ~~Extract shared API helper; add request timeout~~ (implemented: `stream_completion`, `_get_request_timeout`, config `request_timeout`)
- ~~Improve error handling (message box instead of writing errors into selection)~~ (implemented: `show_error()` with MessageBox, `format_error_message()`)
- ~~Refactor duplicate logic~~ (see Section 3c Shared Helpers)

### Dialog-related
- **Config presets**: Add "Load from file" or preset dropdown in Settings so users can switch between `localwriter.json`, `localwriter.openrouter.json`, etc.
- **EditInputDialog**: Consider multiline for long instructions; current layout is single-line.

### Format-preserving replacement
- **Proportional format mapping**: For large length differences, distribute the original formatting pattern proportionally across the new text instead of simple 1:1 character mapping.
- **Paragraph-style preservation**: Handle cases where replacement spans paragraph breaks.
- **Edit Selection streaming**: Apply format-preserving logic to the Edit Selection streaming path for character-level formatting retention during live edits.

### General
- OpenRouter/Together.ai: API key and auth are already implemented; optional: endpoint presets (Local / OpenRouter / Together / Custom).
- Impress support; Calc range-aware behavior.

### Chat settings in UI — DONE
- ~~Expose `chat_context_length`, `chat_max_tokens`, `additional_instructions` in the Settings dialog~~ (implemented in SettingsDialog.xdl).

### Chat Sidebar Enhancement Roadmap

- **Document context (DONE)**: Start + end excerpts and inline selection/cursor markers via `get_document_context_for_chat()`; see "Document context for chat" above and [Chat Sidebar Improvement Plan.md](Chat%20Sidebar%20Improvement%20Plan.md) for design decisions and current implementation.
- **Range-based markdown replace (DONE)**: `get_markdown` returns `document_length` and supports scope `"range"` with `start`/`end`; `apply_markdown` supports target `"full"` (replace entire document) and target `"range"` with `start`/`end` (replace by character span). Enables "read once, replace with new markdown only" so the AI does not send document text twice (e.g. "make my plain text resume look nice"). Helpers in `core/document.py`: `get_document_length()`, `get_text_cursor_at_range()`. System prompt updated to direct the model to use this flow.
- **Calc chat/tools (DONE)**: Sidebar and menu Chat for Calc with CALC_TOOLS, get_calc_context_for_chat, and get_chat_system_prompt_for_document. See [Calc support from LibreCalc.md](Calc%20support%20from%20LibreCalc.md).
- **Draw chat/tools (DONE)**: Sidebar and menu Chat for Draw with DRAW_TOOLS and execute_draw_tool.

---

## 7b. Future Roadmap

- **Richer Context**: Metadata awareness (word counts, styles, formula dependencies).
- **Safer Workflows**: Propose-first execution with user confirmation (diff preview).
- **Predictive Typing**: Trigram-based "ghost text" for real-time drafting assist.
- **Multimodal Integration**: Image generation/editing via **Stable Diffusion** and DALL-E.
- **Reliability Foundations**: Robust timeouts, clear error prompts, and rollback safety.
- **Suite Completeness**: Finalizing Draw and Impress slide/shape toolsets.
- **Offline First**: Optimized local performance for privacy and speed.

---

## 8. Gotchas

- **PR dependency**: Settings dialog field list must match `get_config`/`set_config` keys. If submitting to a repo without PR #31 and #36 merged, either base on those PRs or remove unused fields from `SettingsDialog.xdl`.
- **Library name**: `LocalWriterDialogs` (folder name) must match `library:name` in `dialog.xlb`.
- **DialogProvider deadlock**: Using `vnd.sun.star.script:...?location=application` URLs with `DialogProvider.createDialog()` will deadlock when the sidebar panel (chat_panel.py) is also registered as a UNO component. Always use direct package URLs instead (see Section 3).
- **Use `self.ctx` for PackageInformationProvider**: `uno.getComponentContext()` returns a limited global context that cannot look up extension singletons. Always use `self.ctx` (the context passed to the UNO component constructor).
- **dtd reference**: XDL uses `<!DOCTYPE dlg:window PUBLIC "... "dialog.dtd">`. LibreOffice resolves this from its installation.
- **Chat sidebar visibility**: After `createContainerWindow()`, call `setVisible(True)` on the returned window; otherwise the panel content stays blank.
- **Chat panel imports**: `chat_panel.py` uses `_ensure_extension_on_path()` to add the extension dir to `sys.path` so `from main import MainJob` and `from document_tools import ...` work.
- **Logging**: Call `init_logging(ctx)` once from an entry point that has ctx. Then use `debug_log(msg, context="API"|"Chat"|"Markdown")` and `agent_log(...)`; both use global paths. Do not add new ad-hoc log paths.
- **Streaming in sidebar**: Do not use UNO Timer or `XTimerListener` for draining the stream queue—the type is not available in the sidebar context. Use the pure Python pattern: worker + `queue.Queue` + main-thread loop with `toolkit.processEventsToIdle()` (see "Streaming I/O" in Section 3b).
- **Document scoping in sidebar**: Each sidebar panel instance must operate on its associated document only. Use `self.xFrame.getController().getModel()` to get the document for the panel's frame. Do not rely on global `desktop.getCurrentComponent()` as it changes with user focus and causes the AI to edit the wrong document when multiple documents are open. Tool executions and context building must pass the specific document to avoid cross-document contamination.
- **Strict Verification**: `SendButtonListener` tracks `initial_doc_type` during `_wireControls`. In `_do_send`, it re-verifies the document type. If it differs from the initial type, it logs an error and refuses to send. This prevents document-type "leakage" and ensures the AI never uses the wrong tools.
- **Writer has a Drawing Layer**: `hasattr(model, "getDrawPages")` returns `True` for Writer documents because they have a drawing layer for shapes. Always use `is_writer(model)` (via `supportsService`) to avoid misidentifying Writer as Draw.
- **Context function signatures**: All document context functions should follow the signature `(model, max_context, ctx=None)`. Missing the `ctx` default can lead to `TypeError` during document type transitions in the sidebar.
- **API Keys / Security**: API keys MUST be handled via the Settings dialog and stored in `localwriter.json`. Never bake in fallbacks to environment variables (like `OPENROUTER_API_KEY`) in production code, as this bypasses the user's manual configuration and complicates privacy auditing. Env vars are for developer testing ONLY.

---

## 9. References

- LibreOffice xmlscript: `~/Desktop/libreoffice/xmlscript/` (if you have a local clone)
- DTD: `xmlscript/dtd/dialog.dtd`
- Example XDL: `odk/examples/DevelopersGuide/Extensions/DialogWithHelp/DialogWithHelp/Dialog1.xdl`
- DevGuide: https://wiki.documentfoundation.org/Documentation/DevGuide/Graphical_User_Interfaces

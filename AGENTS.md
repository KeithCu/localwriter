# AGENTS.md — Context for AI Assistants

**Assume the reader knows nothing about this project.** This file summarizes what was learned and what to do next.

---

## 1. Project Overview

**LocalWriter** is a LibreOffice extension (Python + UNO) that adds generative AI editing to Writer and Calc:

- **Extend Selection** (Ctrl+Q): Model continues the selected text
- **Edit Selection** (Ctrl+E): User enters instructions; model rewrites the selection
- **Chat with Document**: (a) **Sidebar panel** (Writer): LocalWriter deck in the right sidebar, multi-turn chat with tool-calling that edits the document; (b) **Menu item** (fallback): Opens input dialog, appends response to end of document
- **Settings**: Configure endpoint, model, API key, temperature, request timeout, etc.
- **Calc** `=PROMPT()`: Cell formula that calls the model

Config is stored in `localwriter.json` in LibreOffice's user config directory. See `CONFIG_EXAMPLES.md` for examples (Ollama, OpenWebUI, OpenRouter, etc.).

---

## 2. Repository Structure

```
localwriter/
├── main.py              # MainJob: trigger(), dialogs, delegates to core
├── core/                # Shared core logic
│   ├── config.py        # get_config, set_config, get_api_config (localwriter.json)
│   ├── api.py           # LlmClient: streaming, chat, tool-calling
│   ├── document.py      # get_full_document_text, get_document_end, get_selection_range, get_document_length, get_text_cursor_at_range, get_document_context_for_chat (Writer)
│   ├── logging.py       # log_to_file, agent_log, debug_log, debug_log_paths
│   ├── constants.py     # DEFAULT_CHAT_SYSTEM_PROMPT
│   └── async_stream.py  # run_stream_completion_async: worker + queue + main-thread drain (no UNO Timer)
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

- **Sidebar panel**: LocalWriter deck in Writer's right sidebar; panel has Response area, Ask field, Send button, Stop button, and Clear button.
  - **Auto-scroll**: The response area automatically scrolls to the bottom as text is streamed or tools are called, ensuring the latest AI output is always visible.
  - **Stop button**: A dedicated "Stop" button allows users to halt AI generation mid-stream. It is enabled only while the AI is active and disabled when idle.
  - **Undo grouping**: AI edits performed during tool-calling rounds are grouped into a single undo context ("AI Edit"). Users can revert all changes from an AI turn with a single Ctrl+Z.
  - **Send/Stop button state (lifecycle-based)**: "AI is busy" is defined by the single run of `actionPerformed`: Send is disabled (Stop enabled) at the **start** of the run, and re-enabled (Stop disabled) **only** in the `finally` block when `_do_send()` has returned. No dependence on internal job_done or drain-loop state. `_set_button_states(send_enabled, stop_enabled)` uses per-control try/except (prefer `control.setEnable()`, fallback to model `Enabled`) so a UNO failure on one control cannot leave Send stuck disabled. `SendButtonListener._send_busy` is set True at run start and False in finally for external checks. This prevents multiple concurrent requests.
- **Implementation**: `chat_panel.py` (ChatPanelFactory, ChatPanelElement, ChatToolPanel); `ContainerWindowProvider` + `ChatPanelDialog.xdl`; `setVisible(True)` required after `createContainerWindow()`.
- **Tool-calling**: The AI sees only two tools (markdown-centric). `document_tools.py` exposes **WRITER_TOOLS** = `get_markdown`, `apply_markdown`. Implementations live in `markdown_support.py`; `document_tools.py` imports them and defines `TOOL_DISPATCH` for `execute_tool`. Legacy tools (`replace_text`, `insert_text`, `get_selection`, `replace_selection`, `format_text`, `set_paragraph_style`, `get_document_text`) remain in `document_tools.py` but are **not** in WRITER_TOOLS and their TOOL_DISPATCH entries are commented out (kept for possible future use).
- **Menu fallback**: Menu item "Chat with Document" opens input dialog, appends streaming response to document end (no tool-calling). Both sidebar and menu use the same document context (see below).
- **Config keys** (used by chat): `chat_context_length`, `chat_max_tokens`, `chat_system_prompt` (in Settings).

### Document context for chat (current implementation)

- **Refreshed every Send**: On each user message we re-read the document and rebuild the context; the single `[DOCUMENT CONTENT]` system message is **replaced** (not appended), so the conversation history grows but the context block does not duplicate.
- **Rich context**: `core/document.py` provides `get_document_context_for_chat(model, max_context, include_end=True, include_selection=True)` which builds one string with:
  - Document length (metadata).
  - **Start and end excerpts**: For long documents, first half and last half of `chat_context_length` (e.g. 4000 + 4000), with `[DOCUMENT START]` / `[DOCUMENT END]` / `[END DOCUMENT]` labels and a middle-omitted note. For short documents, one full block.
  - **Selection/cursor inside the document**: No separate selection block and no duplicated text. We get `(start_offset, end_offset)` from `get_selection_range(model)` (cursor = same start and end; no selection uses view cursor). We inject **`[SELECTION_START]`** and **`[SELECTION_END]`** at those character positions in the excerpt text so the model sees exactly where the selection/cursor is. When there is no selection, both markers are placed at the cursor so the model knows where text would be inserted. Very long selections are capped (e.g. 2000 chars) so context stays usable.
- **Scope**: Chat with Document only. Extend Selection and Edit Selection are legacy and unchanged.
- **Helpers**: `get_document_end(model, max_chars)`, `get_selection_range(model)` → `(start_offset, end_offset)`; `get_document_length(model)` → character count; `get_text_cursor_at_range(model, start, end)` → cursor selecting `[start, end)` (used for range replace); `_inject_markers_into_excerpt()` for placing markers in start/end excerpts.

### Markdown tool-calling (current)

- **get_markdown**: Returns the document (or selection/range) as Markdown. Parameters: optional `max_chars`, optional `scope` (`"full"` | `"selection"` | `"range"`); when `scope="range"`, required `start` and `end` (character offsets). Result JSON includes **`document_length`** so the AI can replace the whole doc with `apply_markdown(target="range", start=0, end=document_length)` or use `target="full"`. When `scope="range"`, result also includes `start` and `end` echoed back. Implementation: for full scope tries `XStorable.storeToURL` with FilterName `"Markdown"` to a temp file; on failure or for selection/range uses structural fallback (paragraph enumeration + `ParaStyleName` → headings, lists, blockquote). See `markdown_support.py`.
- **apply_markdown**: Inserts or replaces content using Markdown **with native formatting**. Parameters: `markdown` (string), `target` (`"beginning"` | `"end"` | `"selection"` | `"search"` | **`"full"`** | **`"range"`**); when `target="search"`, also `search`, optional `all_matches`, `case_sensitive`; when **`target="range"`**, required **`start`** and **`end`** (character offsets). **`target="full"`** replaces the entire document (clear all, insert at start). **`target="range"`** replaces the character span `[start, end)` with the markdown (no need to send the original text back). Preferred flow for "make my resume look nice" or reformat: call `get_markdown(scope="full")` once, then `apply_markdown(markdown=<new content>, target="full")` or `target="range", start=0, end=document_length` — **only the new markdown is sent**, never the original document text. Implementation: writes markdown to a temp `.md` file, then **`cursor.insertDocumentFromURL(file_url, {FilterName: "Markdown"})`** at the chosen position; for `"full"` uses `_insert_markdown_full`; for `"range"` uses `get_text_cursor_at_range()` then `setString("")` and `insertDocumentFromURL`. See `markdown_support.py`.

### System prompt and reasoning (latest)

- **DEFAULT_CHAT_SYSTEM_PROMPT** in `core/constants.py` (imported by `main.py`, `chat_panel.py`) instructs the model to: (1) use **get_markdown** to read (full or range) and **apply_markdown** to write — for "replace whole document" (e.g. make my resume look nice) call `get_markdown(scope="full")` once, then `apply_markdown(markdown=<new markdown>, target="full")` and pass **only the new content**, never the original document text; (2) **presume document editing** — for requests like "write me a resume" or "create a joke", it should use document tools rather than just replying in chat; (3) use internal linguistic knowledge for translate/proofread/edit — NEVER refuse translation; (4) no preamble, concise reasoning, one-sentence confirmation after edits.
- **Reasoning tokens**: `main.py` sends `reasoning: { effort: 'minimal' }` on all chat requests (OpenRouter and other providers).
- **Thinking display**: Reasoning tokens are shown in the response area as `[Thinking] ... /thinking`. When thinking ends we append a newline after ` /thinking` so the following response text starts on a new line.

See [CHAT_SIDEBAR_IMPLEMENTATION.md](CHAT_SIDEBAR_IMPLEMENTATION.md) for implementation details.

### Streaming I/O: pure Python queue + main-thread drain

All streaming paths (sidebar tool-calling, sidebar simple stream, Writer Extend/Edit/menu Chat, Calc) use the same pattern so the UI stays responsive without relying on UNO Timer/listeners:

- **Worker thread**: Runs blocking API/streaming (e.g. `stream_completion`, `stream_request_with_tools`), puts items on a **`queue.Queue`** (`("chunk", text)`, `("thinking", text)`, `("stream_done", ...)`, `("error", e)`, `("stopped",)`).
- **Main thread**: After starting the worker, runs a **drain loop**: `q.get(timeout=0.05)` → process item (append text, update status, call on_done/on_error) → **`toolkit.processEventsToIdle()`**. Repeats until job_done.
- **UNO usage**: Only `ctx.getServiceManager().createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)` (string-based, no `com` import) and `toolkit.processEventsToIdle()`. No Timer, no `XTimerListener`—avoids "XTimerListener unknown" in the sidebar context and keeps the design consistent everywhere.
- **Why it’s better**: Standard Python (`queue`, `threading`); interface is just the queue; multiple chunks can be applied between `processEventsToIdle()` calls so multiple inserts are shown in one redraw (fewer repaints, faster perceived speed).
- **Where**: **Sidebar** — `chat_panel.py` `_start_tool_calling_async()` (tool path) and simple stream via `run_stream_completion_async()`. **Writer/Calc** — `main.py` calls `core/async_stream.run_stream_completion_async()` for Extend Selection, Edit Selection, menu Chat with Document, and Calc Extend/Edit.

---

## 3c. Shared Helpers

- **`MainJob._apply_settings_result(self, result)`** (`main.py`): Applies settings dialog result to config. Used by both Writer and Calc settings branches.
- **`core/logging.py`**:
  - `agent_log(location, message, data=None, hypothesis_id=None, run_id=None)` — NDJSON agent log. Paths: `{ext_dir}/.cursor/debug.log`, `~/localwriter_agent_debug.log`, `/tmp/localwriter_agent_debug.log`.
  - `debug_log(ctx, msg)` — chat debug log. Paths: UserConfig, `~/localwriter_chat_debug.log`, `/tmp/localwriter_chat_debug.log`.
  - `debug_log_paths(ctx)` — returns writable paths for chat debug.
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

## 5. Config File

- **Path**: LibreOffice UserConfig directory + `localwriter.json`
  - Linux: `~/.config/libreoffice/4/user/localwriter.json` (or `24/user` for LO 24)
  - macOS: `~/Library/Application Support/LibreOffice/4/user/localwriter.json`
  - Windows: `%APPDATA%\LibreOffice\4\user\localwriter.json`
- **Single file**: No presets or multiple configs. To use a different setup (e.g. `localwriter.openrouter.json`), copy it to the path above as `localwriter.json`.
- **Settings dialog** reads/writes this file via `get_config()` / `set_config()` in `core/config.py`.
- **Chat-related keys** (used by `chat_panel.py` and menu Chat): `chat_context_length` (default 8000), `chat_max_tokens` (default 512 menu / 16384 sidebar), `chat_system_prompt`. Also `api_key`, `api_type` (in Settings) for OpenRouter/OpenAI-compatible endpoints.
- **Note**: `chat_context_length`, `chat_max_tokens`, `chat_system_prompt` are now in the Settings dialog.

---

## 5b. Log Files

- **Agent log** (NDJSON): `core/logging.agent_log()`. Paths tried: `{ext_dir}/.cursor/debug.log`, `~/localwriter_agent_debug.log`, `/tmp/localwriter_agent_debug.log`.
  - Used by `main.py`, `chat_panel.py`, `document_tools.py` for hypothesis/debug tracking.
- **Chat sidebar debug log**: `core/logging.debug_log()`. Paths: UserConfig dir (`localwriter_chat_debug.log`), `~/localwriter_chat_debug.log`, `/tmp/localwriter_chat_debug.log`.
  - Contains tool-calling loop details, import status, API round-trip info.
- **General API log**: `~/log.txt`
  - Written by `log_to_file()` in `core/logging.py`
  - Contains API request URLs, headers, response status for all completions/chat requests

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

### General
- OpenRouter/Together.ai: API key and auth are already implemented; optional: endpoint presets (Local / OpenRouter / Together / Custom).
- Impress support; Calc range-aware behavior.

### Chat settings in UI — DONE
- ~~Expose `chat_context_length`, `chat_max_tokens`, `chat_system_prompt` in the Settings dialog~~ (implemented in SettingsDialog.xdl).

### Chat Sidebar Enhancement Roadmap

- **Document context (DONE)**: Start + end excerpts and inline selection/cursor markers via `get_document_context_for_chat()`; see "Document context for chat" above and [Chat Sidebar Improvement Plan.md](Chat%20Sidebar%20Improvement%20Plan.md) for design decisions and current implementation.
- **Range-based markdown replace (DONE)**: `get_markdown` returns `document_length` and supports scope `"range"` with `start`/`end`; `apply_markdown` supports target `"full"` (replace entire document) and target `"range"` with `start`/`end` (replace by character span). Enables "read once, replace with new markdown only" so the AI does not send document text twice (e.g. "make my plain text resume look nice"). Helpers in `core/document.py`: `get_document_length()`, `get_text_cursor_at_range()`. System prompt updated to direct the model to use this flow.

---

## 8. Gotchas

- **PR dependency**: Settings dialog field list must match `get_config`/`set_config` keys. If submitting to a repo without PR #31 and #36 merged, either base on those PRs or remove unused fields from `SettingsDialog.xdl`.
- **Library name**: `LocalWriterDialogs` (folder name) must match `library:name` in `dialog.xlb`.
- **DialogProvider deadlock**: Using `vnd.sun.star.script:...?location=application` URLs with `DialogProvider.createDialog()` will deadlock when the sidebar panel (chat_panel.py) is also registered as a UNO component. Always use direct package URLs instead (see Section 3).
- **Use `self.ctx` for PackageInformationProvider**: `uno.getComponentContext()` returns a limited global context that cannot look up extension singletons. Always use `self.ctx` (the context passed to the UNO component constructor).
- **dtd reference**: XDL uses `<!DOCTYPE dlg:window PUBLIC "... "dialog.dtd">`. LibreOffice resolves this from its installation.
- **Chat sidebar visibility**: After `createContainerWindow()`, call `setVisible(True)` on the returned window; otherwise the panel content stays blank.
- **Chat panel imports**: `chat_panel.py` uses `_ensure_extension_on_path()` to add the extension dir to `sys.path` so `from main import MainJob` and `from document_tools import ...` work.
- **Logging**: Use `core.logging.agent_log()` for NDJSON agent logs and `core.logging.debug_log(ctx, msg)` for chat debug logs. Do not add new ad-hoc log paths.
- **Streaming in sidebar**: Do not use UNO Timer or `XTimerListener` for draining the stream queue—the type is not available in the sidebar context. Use the pure Python pattern: worker + `queue.Queue` + main-thread loop with `toolkit.processEventsToIdle()` (see "Streaming I/O" in Section 3b).

---

## 9. References

- LibreOffice xmlscript: `~/Desktop/libreoffice/xmlscript/` (if you have a local clone)
- DTD: `xmlscript/dtd/dialog.dtd`
- Example XDL: `odk/examples/DevelopersGuide/Extensions/DialogWithHelp/DialogWithHelp/Dialog1.xdl`
- DevGuide: https://wiki.documentfoundation.org/Documentation/DevGuide/Graphical_User_Interfaces

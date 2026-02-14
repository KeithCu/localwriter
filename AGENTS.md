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
├── main.py              # MainJob: trigger(), API calls, dialogs
├── core/                # Shared core logic
│   └── config.py        # get_config, set_config (localwriter.json)
├── prompt_function.py   # Calc =PROMPT() formula
├── chat_panel.py        # Chat sidebar: ChatPanelFactory, ChatPanelElement, ChatToolPanel
├── document_tools.py    # 7 Writer tools + executor for OpenAI tool-calling
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
  - **Send button disable**: The Send button is programmatically disabled via `setEnable(False)` when the tool-calling loop starts and re-enabled in a `finally` block when done. This prevents multiple concurrent requests.
- **Implementation**: `chat_panel.py` (ChatPanelFactory, ChatPanelElement, ChatToolPanel); `ContainerWindowProvider` + `ChatPanelDialog.xdl`; `setVisible(True)` required after `createContainerWindow()`.
- **Tool-calling**: `document_tools.py` defines 7 tools: `replace_text`, `insert_text`, `get_selection`, `replace_selection`, `format_text`, `set_paragraph_style`, `get_document_text`.
- **Menu fallback**: Menu item "Chat with Document" opens input dialog, appends streaming response to document end (no tool-calling).
- **Config keys** (used by chat): `chat_context_length`, `chat_max_tokens`, `chat_system_prompt` (in Settings).

### System prompt and reasoning (latest)

- **DEFAULT_CHAT_SYSTEM_PROMPT** in `main.py` (imported by `chat_panel.py`) instructs the model to: (1) use tools proactively; (2) use internal linguistic knowledge for translate/proofread/edit; (3) for translate: call `get_document_text`, translate internally, then apply via tools — NEVER refuse translation; (4) keep reasoning minimal and act; (5) confirm edits briefly.
- **Reasoning tokens**: `main.py` sends `reasoning: { effort: 'minimal' }` on all chat requests (OpenRouter and other providers).
- **Thinking display**: Reasoning tokens are shown in the response area as `[Thinking] ... /thinking`.

See [CHAT_SIDEBAR_IMPLEMENTATION.md](CHAT_SIDEBAR_IMPLEMENTATION.md) for implementation details.

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

- **Chat sidebar debug log**: Same folder as `localwriter.json`, e.g. `~/.config/libreoffice/4/user/localwriter_chat_debug.log` (no `config` subfolder). Fallbacks: `~/localwriter_chat_debug.log`, `/tmp/localwriter_chat_debug.log`. `_debug_log_paths()` in `chat_panel.py` uses `PathSettings.UserConfig`.
  - Written by `_debug_log()` in `chat_panel.py`
  - Contains tool-calling loop details, import status, API round-trip info
- **General API log**: `~/log.txt`
  - Written by `log_to_file()` in `main.py`
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
- ~~Improve error handling (message box instead of writing errors into selection)~~ (implemented: `show_error()` with MessageBox, `_format_error_message()`)

### Dialog-related
- **Config presets**: Add "Load from file" or preset dropdown in Settings so users can switch between `localwriter.json`, `localwriter.openrouter.json`, etc.
- **EditInputDialog**: Consider multiline for long instructions; current layout is single-line.

### General
- OpenRouter/Together.ai: API key and auth are already implemented; optional: endpoint presets (Local / OpenRouter / Together / Custom).
- Impress support; Calc range-aware behavior.

### Chat settings in UI — DONE
- ~~Expose `chat_context_length`, `chat_max_tokens`, `chat_system_prompt` in the Settings dialog~~ (implemented in SettingsDialog.xdl).

### Chat Sidebar Enhancement Roadmap

See [Chat Sidebar Improvement Plan.md](Chat%20Sidebar%20Improvement%20Plan.md) for current capabilities, recent improvements, and advanced roadmap.

---

## 8. Gotchas

- **PR dependency**: Settings dialog field list must match `get_config`/`set_config` keys. If submitting to a repo without PR #31 and #36 merged, either base on those PRs or remove unused fields from `SettingsDialog.xdl`.
- **Library name**: `LocalWriterDialogs` (folder name) must match `library:name` in `dialog.xlb`.
- **DialogProvider deadlock**: Using `vnd.sun.star.script:...?location=application` URLs with `DialogProvider.createDialog()` will deadlock when the sidebar panel (chat_panel.py) is also registered as a UNO component. Always use direct package URLs instead (see Section 3).
- **Use `self.ctx` for PackageInformationProvider**: `uno.getComponentContext()` returns a limited global context that cannot look up extension singletons. Always use `self.ctx` (the context passed to the UNO component constructor).
- **dtd reference**: XDL uses `<!DOCTYPE dlg:window PUBLIC "... "dialog.dtd">`. LibreOffice resolves this from its installation.
- **Chat sidebar visibility**: After `createContainerWindow()`, call `setVisible(True)` on the returned window; otherwise the panel content stays blank.
- **Chat panel imports**: `chat_panel.py` uses `_ensure_extension_on_path()` to add the extension dir to `sys.path` so `from main import MainJob` and `from document_tools import ...` work.

---

## 9. References

- LibreOffice xmlscript: `~/Desktop/libreoffice/xmlscript/` (if you have a local clone)
- DTD: `xmlscript/dtd/dialog.dtd`
- Example XDL: `odk/examples/DevelopersGuide/Extensions/DialogWithHelp/DialogWithHelp/Dialog1.xdl`
- DevGuide: https://wiki.documentfoundation.org/Documentation/DevGuide/Graphical_User_Interfaces

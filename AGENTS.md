# AGENTS.md — Context for AI Assistants

**Assume the reader knows nothing about this project.** This file summarizes what was learned and what to do next.

---

## 1. Project Overview

**LocalWriter** is a LibreOffice extension (Python + UNO) that adds generative AI editing to Writer and Calc:

- **Extend Selection** (Ctrl+Q): Model continues the selected text
- **Edit Selection** (Ctrl+E): User enters instructions; model rewrites the selection
- **Settings**: Configure endpoint, model, API key, temperature, etc.
- **Calc** `=PROMPT()`: Cell formula that calls the model

Config is stored in `localwriter.json` in LibreOffice's user config directory. See `CONFIG_EXAMPLES.md` for examples (Ollama, OpenWebUI, OpenRouter, etc.).

---

## 2. Repository Structure

```
localwriter/
├── main.py              # MainJob: trigger(), API calls, config, dialogs
├── prompt_function.py   # Calc =PROMPT() formula
├── XPromptFunction.rdb  # Type library for PromptFunction
├── LocalWriterDialogs/   # XDL dialogs (XML, Map AppFont units)
│   ├── SettingsDialog.xdl
│   ├── EditInputDialog.xdl
│   ├── dialog.xlb       # Library index
│   └── script.xlb       # Empty (required for Basic library)
├── META-INF/manifest.xml
├── Addons.xcu           # Menu entries
├── Accelerators.xcu     # Ctrl+Q, Ctrl+E
├── build.sh             # Creates localwriter.oxt
└── CONFIG_EXAMPLES.md   # Config templates
```

---

## 3. What Was Done (Dialog Refactor)

### Before
- Settings and Edit Input dialogs were built **programmatically** with `UnoControlDialog`, `UnoControlEditModel`, etc.
- Layout issues: wrong sizing, truncation, poor HiDPI behavior, no scrollbar

### After
- Both dialogs use **XDL files** (XML) loaded via `DialogProvider`
- `LocalWriterDialogs.SettingsDialog` — 12 config fields
- `LocalWriterDialogs.EditInputDialog` — label + text field + OK

### Key implementation details
- **DialogProvider**: `createDialog("vnd.sun.star.script:LocalWriterDialogs.SettingsDialog?location=application")`
- **Populate**: `dlg.getControl("endpoint").getModel().Text = value`
- **Read**: `dlg.getControl("endpoint").getModel().Text` after `dlg.execute()`
- **Manifest** must register the Basic library: `LocalWriterDialogs/` with `application/vnd.sun.star.basic-library`

---

## 4. Critical Learnings: LibreOffice Dialogs

### Units
- **Map AppFont** units: device- and HiDPI-independent. 1 unit ≈ 1/4 char width, 1/8 char height.
- XDL uses Map AppFont for `dlg:left`, `dlg:top`, `dlg:width`, `dlg:height`
- **Do not** use raw pixels for layout; they break on HiDPI

### No automatic layout
- LibreOffice dialogs have **no flexbox, no auto-size**. Every control needs explicit position/size.
- Scrollbars require manual implementation (complex). Prefer splitting into tabs or keeping content compact.

### Recommended approach: XDL + DialogProvider
- Design dialogs as **XDL files** (XML). Edit `LocalWriterDialogs/*.xdl` directly.
- Load via `DialogProvider.createDialog("vnd.sun.star.script:LibraryName.DialogName?location=application")`
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
- **Settings dialog** reads/writes this file via `get_config()` / `set_config()`.

---

## 5b. Log Files

- **Chat sidebar debug log**: `~/.config/libreoffice/4/user/config/localwriter_chat_debug.log`
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

### High priority (from IMPROVEMENT_PLAN.md)
- Extract shared API helper; add request timeout
- Fix typo `"versio"` → `"version"` in Edit prompt (if still present)
- Improve error handling (message box instead of writing errors into selection)
- Fix manifest if it references missing files

### Dialog-related
- **Config presets**: Add "Load from file" or preset dropdown in Settings so users can switch between `localwriter.json`, `localwriter.openrouter.json`, etc.
- **EditInputDialog**: Consider multiline for long instructions; current layout is single-line.

### General
- OpenRouter/Together.ai support (API key, auth header)
- Chat mode, Impress support
- Calc range-aware behavior

---

## 8. Gotchas

- **PR dependency**: Settings dialog field list must match `get_config`/`set_config` keys. If submitting to a repo without PR #31 and #36 merged, either base on those PRs or remove unused fields from `SettingsDialog.xdl`.
- **Library name**: `LocalWriterDialogs` (folder name) must match `library:name` in `dialog.xlb` and the URL.
- **DialogProvider failure**: If the XDL library isn't loaded (e.g. extension not fully installed), `createDialog` throws. No fallback; ensure the extension is installed correctly.
- **dtd reference**: XDL uses `<!DOCTYPE dlg:window PUBLIC "... "dialog.dtd">`. LibreOffice resolves this from its installation.

---

## 9. References

- LibreOffice xmlscript: `~/Desktop/libreoffice/xmlscript/` (if you have a local clone)
- DTD: `xmlscript/dtd/dialog.dtd`
- Example XDL: `odk/examples/DevelopersGuide/Extensions/DialogWithHelp/DialogWithHelp/Dialog1.xdl`
- DevGuide: https://wiki.documentfoundation.org/Documentation/DevGuide/Graphical_User_Interfaces

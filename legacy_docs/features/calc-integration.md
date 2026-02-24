---
name: Calc Support from LibreCalc AI
overview: "Calc support (chat/tools) is now implemented in LocalWriter, reusing and adapting the in-process Calc UNO layer, tool set, and error detector from libre_calc_ai-1.0.2."
status: "COMPLETE (Feb 2026)"
todos: []
isProject: false
---

Calc support (chat/tools) is now fully integrated into LocalWriter. We have reused the following components from [libre_calc_ai-1.0.2](libre_calc_ai-1.0.2/) in-process, translated and adapted for LocalWriter's architecture.

---

## IMPLEMENTATION SUMMARY (Feb 2026)

All planned modules are implemented in `core/` and integrated into the **Chat Sidebar** and **LibreOffice Menu**.

- **Core Calc Logic**: Ported and translated `calc_bridge.py`, `calc_address_utils.py`, `calc_inspector.py`, `calc_sheet_analyzer.py`, `calc_error_detector.py`, and `calc_manipulator.py`.
- **AI Toolset**: `CALC_TOOLS` in `core/calc_tools.py` (read ranges, write formulas, format, merge, sheet management, chart creation, detect_and_explain_errors).
- **Dynamic Tool Loading**: `chat_panel.py` detects document type and switches between `WRITER_TOOLS` and `CALC_TOOLS`.
- **Calc Chat Context**: `get_calc_context_for_chat(model, max_context, ctx)` in `core/document.py` provides a summary of the active sheet and selection. **Requires `ctx`** (component context); callers pass it from the panel or MainJob so we never use `uno.getComponentContext()` in this path.
- **Robust prompt selection**: `get_chat_system_prompt_for_document(model, additional_instructions)` in `core/constants.py` is the single source of truth for the chat system prompt. It returns `DEFAULT_CALC_CHAT_SYSTEM_PROMPT` for Calc and `DEFAULT_CHAT_SYSTEM_PROMPT` for Writer, so Writer/Calc prompts cannot be mixed. Used by `chat_panel.py` and `main.py` for both sidebar and menu Chat.
- **Calc System Prompt**: `DEFAULT_CALC_CHAT_SYSTEM_PROMPT` in `core/constants.py` states semicolon formula syntax, a 4-step workflow (understand → get state if needed → use tools → short confirmation), and tools grouped by use (READ / WRITE & FORMAT / SHEET MANAGEMENT / CHART / ERRORS). Structure inspired by libre_calc_ai `prompt_templates.py` (workflow, grouped tools, “do not explain—do the operation”).
- **Menu**: "Chat with Document" for Calc in `main.py` (streams response to "AI Response" sheet; uses same prompt helper and `ctx` for context).
- **Tests**: `tests/test_calc_address_utils.py` and `core/calc_tests.py`.

---

## 1. In-process “bridge”: document from ctx

**Do not use:** Their socket/pipe `connect()` and BridgeServer/BridgeClient.

**Use:** The same abstraction they use when running inside LO: get document/sheet/cell from the current component context.

- **Source:** [CalcAI/core/uno_bridge.py](libre_calc_ai-1.0.2/Scripts/python/CalcAI/core/uno_bridge.py) (lines 155–217 and helpers).
- **Status:** **IMPLEMENTED** in `core/calc_bridge.py`.
- **How it works:** Uses `XSCRIPTCONTEXT` or `officehelper.bootstrap()` to get the UNO context. Exposes `get_active_document()`, `get_active_sheet()`, etc.

---

## 2. Address utilities (copy or merge)

**Source:** [CalcAI/core/address_utils.py](libre_calc_ai-1.0.2/Scripts/python/CalcAI/core/address_utils.py)

- **Status:** **IMPLEMENTED** in `core/calc_address_utils.py`.
- **Action:** Pure Python address handling for A1/range parsing.

---

## 3. Cell inspector (read operations)

**Source:** [CalcAI/core/cell_inspector.py](libre_calc_ai-1.0.2/Scripts/python/CalcAI/core/cell_inspector.py)

- **Status:** **IMPLEMENTED** in `core/calc_inspector.py`.
- **Action:** Ported all analytical methods and translated Turkish comments/docstrings.

---

## 4. Sheet analyzer

**Source:** [CalcAI/core/sheet_analyzer.py](libre_calc_ai-1.0.2/Scripts/python/CalcAI/core/sheet_analyzer.py)

- **Status:** **IMPLEMENTED** in `core/calc_sheet_analyzer.py`.
- **Action:** Used to build the AI context in `core/document.py:get_calc_context_for_chat()`.

---

## 5. Error detector (formula errors)

**Source:** [CalcAI/core/error_detector.py](libre_calc_ai-1.0.2/Scripts/python/CalcAI/core/error_detector.py)

- **Status:** **IMPLEMENTED** in `core/calc_error_detector.py`.
- **Action:** Full error code mapping ported and translated. Exposed as `detect_and_explain_errors` tool.

---

## 6. Cell manipulator (write / format / structure)

**Source:** [CalcAI/core/cell_manipulator.py](libre_calc_ai-1.0.2/Scripts/python/CalcAI/core/cell_manipulator.py)

- **Status:** **IMPLEMENTED** in `core/calc_manipulator.py`.
- **Action:** Tier 1 and 2 methods implemented. Added Tier 3 `create_chart` support.

---

## 7. Tool definitions and dispatcher

**Source:** [CalcAI/llm/tool_definitions.py](libre_calc_ai-1.0.2/Scripts/python/CalcAI/llm/tool_definitions.py)

- **Status:** **IMPLEMENTED** in `core/calc_tools.py`.
- **Action:** Defined `CALC_TOOLS` and `execute_calc_tool` dispatcher. Integrated with `chat_panel.py` and `main.py`.

---

## 8. System prompt for Calc

**Source:** [CalcAI/llm/prompt_templates.py](libre_calc_ai-1.0.2/Scripts/python/CalcAI/llm/prompt_templates.py)

- **Status:** **IMPLEMENTED** in [core/constants.py](core/constants.py).
- **Implementation:** `DEFAULT_CALC_CHAT_SYSTEM_PROMPT` plus `get_chat_system_prompt_for_document(model, additional_instructions)` so the correct prompt is chosen by document type (Calc vs Writer). The Calc prompt includes:
  - “Do not explain—do the operation directly using tools” and “Perform as many steps as needed in one turn when possible.”
  - A 4-step **WORKFLOW**: understand → get state (get_sheet_summary/read_cell_range) if needed → use tools → short confirmation (mention cell/range addresses when changing).
  - **FORMULA SYNTAX**: Semicolon (;) as argument separator; correct vs wrong examples.
  - **TOOLS** grouped by use: READ / WRITE & FORMAT / SHEET MANAGEMENT / CHART / ERRORS (only tools we expose).
- Structure inspired by libre_calc_ai’s prompt_templates (workflow, grouped tools).

---

## 9. Context for each Calc request

**Source:** interface.py `_build_context_func` and sheet_analyzer usage.

- **Status:** **IMPLEMENTED** in `core/document.py`: `get_calc_context_for_chat(model, max_context, ctx)`.
- **Shape:** Builds a string with document URL, active sheet name, used range (rows × columns), column headers, current selection range, and (for small selections) selection content. Uses `SheetAnalyzer.get_sheet_summary()` and selection from the controller.
- **Context parameter:** `ctx` is **required** (component context from panel or MainJob). No `uno.getComponentContext()` in this path. `get_document_context_for_chat(..., ctx=None)` requires `ctx` when the document is Calc.

---

## 10. Integration with LocalWriter (no bridge)

- **Entry point:** Chat from Calc uses the same sidebar/menu as Writer; `ctx` comes from the UNO component (panel or MainJob). Both pass `ctx` into `get_document_context_for_chat` so the extension context is always used.
- **Single process:** All Calc code runs in LO’s Python. No BridgeServer, BridgeClient, or subprocess.
- **LlmClient:** Reuse [core/api.py](core/api.py) (streaming, tool-calling, reasoning). Pass **CALC_TOOLS** and `execute_calc_tool` when the active document is a spreadsheet.
- **UI:** Same sidebar (LocalWriter deck) and menu for Writer and Calc; ContextList includes `com.sun.star.sheet.SpreadsheetDocument`. Response area + input + Send/Stop. No PyQt5.
- **Undo:** Undo grouping for AI edits is out of scope for now (Writer has the same limitation).

---

## 11. Suggested file layout (when you add Calc)

```
core/
  calc_address_utils.py   # address_utils (from libre_calc_ai)
  calc_bridge.py          # thin in-process get_active_document/sheet/cell/selection
  calc_inspector.py       # CellInspector-style read (read_range, get_cell_details, ...)
  calc_sheet_analyzer.py  # get_sheet_summary, optional detect_data_regions
  calc_error_detector.py  # detect_and_explain_errors
  calc_manipulator.py     # write_formula, set_cell_style, merge_cells, sort_range, ...
  calc_tools.py           # CALC_TOOLS (schemas) + execute_calc_tool / CalcToolDispatcher
```

Optional: a single `core/calc.py` that re-exports the public API (get_calc_context, get_sheet_summary, execute_calc_tool, CALC_TOOLS) so chat_panel or a Calc panel only imports from one place.

---

## 12. What not to take from libre_calc_ai

- **interface.py** (script entry, subprocess launch, bridge server): Not needed; LocalWriter uses UNO service/sidebar.
- **BridgeServer / BridgeClient:** Not needed; everything in-process.
- **PyQt5 UI (main_window, chat_widget, settings_dialog):** Not needed; use LO sidebar/XDL.
- **Their config (settings.json, .env, multi-provider):** Keep LocalWriter config (localwriter.json, single endpoint); optional env overrides only if you want.
- **event_listener.py:** Only needed if you want “auto-refresh on document change”; can be added later with UNO listeners in-process.

---

- **Status:** **DONE**. Integrated into `main.py` and `chat_panel.py`.
- **Order of Implementation (Actual):**
  1. Ported and translated core logic (`calc_bridge` to `calc_manipulator`).
  2. Integrated `get_calc_context_for_chat` in `core/document.py`.
  3. Created `core/calc_tools.py` with schemas and dispatcher.
  4. Updated `chat_panel.py` for document type detection and tool swapping.
  5. Updated `main.py` for menu support and response-to-sheet flow.
  6. Added tests in `tests/test_calc_address_utils.py` and `core/calc_tests.py`.
  7. **Robustness:** Added `get_chat_system_prompt_for_document()` in `core/constants.py`; all chat entry points use it so Writer/Calc prompt cannot be mixed. Added required `ctx` parameter to `get_document_context_for_chat` and `get_calc_context_for_chat`; callers pass component context (no `uno.getComponentContext()` in this path).
  8. **Calc system prompt:** Added `DEFAULT_CALC_CHAT_SYSTEM_PROMPT` with workflow, grouped tools, and formula syntax; structure inspired by libre_calc_ai `prompt_templates.py`.

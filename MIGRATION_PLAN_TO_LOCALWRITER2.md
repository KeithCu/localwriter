# Incremental Migration Plan: localwriter -> localwriter2

The goal of this plan is to incrementally reduce the diffs between the `localwriter` (current directory with some new features not in localwriter2) and `localwriter2` (refactoring from a week old fork), ensuring the plugin remains functional at every step.

**Current status:** Phases 1–4 are complete (tooling/Make, docs/cleanup, framework infrastructure porting, Writer/Calc/Chatbot module reorganization). Most framework files from `localwriter2` are now present and `mcp_thread.py` has been updated to use the new `main_thread.py`. Phase 5 (AI/HTTP modules) remains.

## Proposed Changes

### Phase 1: Porting Tooling & The Make System ✅ (Completed)
The current `localwriter` uses a simple `build.sh` script, while `localwriter2` uses a robust `Makefile` and python scripts in `scripts/`. We can migrate this by:
1. Copying `Makefile`, `Makefile.local-dist`, and the `scripts/` directory from `localwriter2` into `localwriter`.
2. Copying `plugin/_manifest.py` and `plugin/plugin.yaml` (which the new Make system needs to build `manifest.xml`).
3. Commenting out any modules or configurations in `_manifest.py` that don't yet exist in the old `localwriter` tree.
4. Verifying that `make build` and `make deploy` work for our current codebase, and then retiring `build.sh`.

### Phase 2: Documentation and Root File Cleanup ✅ (Completed)
`localwriter` has a lot of `.md` and `.odt` files cluttering the root directory. `localwriter2` organizes these better.
1. Move the root project notes and design docs into `docs/` or `contrib/` matching the `localwriter2` layout.
2. Remove any obsolete files that `localwriter2` has deleted.

*Documentation and root-file reorganization was completed by another agent.*

### Phase 3: Bringing in Framework Infrastructure ✅ (Completed)
`localwriter2` has a rich abstraction layer in `plugin/framework/` (e.g., `module_base.py`, `service_base.py`, `event_bus.py`, `tool_base.py`). 
1. **Framework files ported** ✅ (Completed) Core framework files are now present in `plugin/framework/`: `event_bus.py`, `service_registry.py`, `main_thread.py`, `uno_context.py`, `dialogs.py`, `module_base.py`, `service_base.py`, `tool_base.py`, `tool_registry.py`, `tool_context.py`, `schema_convert.py`, `constants.py`, `uno_helpers.py`, `logging.py`, `http.py`, `image_utils.py`.
2. **Infrastructure Alignment** ✅ (Completed) `plugin/modules/core/mcp_thread.py` has been refactored to delegate safe UNO execution to the new `plugin.framework.main_thread` module, which uses the superior `AsyncCallback` mechanism.
3. **Writer tools on ToolBase** ✅ (Completed) Writer tools use a `ToolRegistry` and thin `ToolBase` wrapper classes in `plugin/modules/core/document_tools.py`.

### Phase 4: Module Reorganization ✅ (Completed)
`localwriter2` heavily refactors logic out of core and into specific modules under `plugin/modules/writer/`, `plugin/modules/calc/`, `plugin/modules/chatbot/`, etc.
1. **Writer Module:** ✅ (Completed) Split `ops.py` into smaller focused files (`outline.py`, `tables.py`, etc.) and updated imports.
2. **Calc Module:** ✅ (Completed) Missing directories created; tool implementations moved from core to `plugin/modules/calc/` (by another agent).
3. **Chatbot Module:** ✅ (Completed) UI and chat-specific logic moved out of core:
   - `plugin/chat_panel.py` moved via `git mv` to `plugin/modules/chatbot/panel_factory.py` (history preserved). Manifest and build script updated to register the new path.
   - ChatSession, SendButtonListener, StopButtonListener, and ClearButtonListener extracted into `plugin/modules/chatbot/panel.py`; `panel_factory.py` imports them and passes `ensure_path_fn=_ensure_extension_on_path` into the listener.
   - Extension-root path fix: when loaded from the unpacked .oxt, `panel_factory.py` adds the extension root (4 levels up from itself) to `sys.path` so `import plugin` resolves correctly.
4. `AGENTS.md` and tests updated iteratively.

### Phase 5: Additional Core Services (Future Work)
`localwriter2` separates LLM and web services into distinct modules.
1. **AI Module:** Port over the `ai` module (`plugin/modules/ai/`) and register it properly in `_manifest.py`.
2. **HTTP Module:** Port over the internal web server and MCP routes (`plugin/modules/http/`).
3. Update `config.py` and remove legacy hardcoded settings in favor of the new modular configuration system.

## Verification Plan

### Automated Tests
- Run `make test` (or `pytest`) after each incremental step to ensure unit tests still pass.

### Manual Verification
- After porting the Make system in Phase 1, we will actively use `make deploy` and verify the plugin starts up cleanly in LibreOffice.
- For each subsequent phase, we will click a few tools via the Sidebar in LibreOffice to test end-to-end functionality.

---

## What to work on later (advised follow-ups)

- **Phase 3 remaining (optional):** Minor alignment files like `panel_layout.py`, `config_schema.py`, `http_server.py`, and `http_routes.py` remain in `localwriter2` and could be ported if the higher-level HTTP/UI services are migrated. 

- **Writer tool layout (optional):** To make the repo “look” more like localwriter2, you can refactor Writer tools from a single block in `document_tools.py` into one module per domain (e.g. `plugin/modules/writer/format_tools.py`, `outline_tools.py`, …), each defining `ToolBase` subclasses whose `execute()` still delegates to the existing implementations. Same behavior, but file layout matches localwriter2.

- **Writer tools with logic in ToolBase (optional):** Later you can replace the thin Writer wrappers with “real” ToolBase classes that contain the logic (or call a document/paragraph service) and use `ctx.services`, so Writer tools align with localwriter2’s style. That implies introducing a document service (and optionally writer_index, writer_tree) and wiring it into `ToolContext.services` when building the context for Writer.

- **EventBus reconciliation (optional):** Reconcile the two `EventBus` implementations. Currently, `plugin/modules/core/tool_bus.py` uses a simple broadcast list, while the new `plugin/framework/event_bus.py` supports event-keyed subscriptions and weak references. In the future, `tool_bus.py` can be refactored to use the framework version.

- **Phase 5:** Port the AI module (`plugin/modules/ai/`), HTTP/MCP module (`plugin/modules/http/`), and move config toward the new modular/schema-based system when you are ready to reduce divergence from localwriter2.

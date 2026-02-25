# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.5.1] — 2026-02-25

### Changed

- Unified streaming + tool-calling loop into `chat_event_stream()` generator in `streaming.py`
- Panel and HTTP API chatbot handlers now consume the same NDJSON event stream

## [1.5.0] — 2026-02-25

### Added

- Document context strategies (full/page/tree/stats/auto) with config `chatbot.context_strategy`
- Session summary compression: older messages condensed when history exceeds 24K chars
- Chatbot HTTP API module (`chatbot_api`): REST/SSE endpoints for external integrations
- Debug module: System Info and Test AI Providers actions (conditional on `debug.enabled`)
- Dummy AI provider (`ai_dummy`): Homer Simpson mode for testing (streams "D'oh!")
- Enter-to-send in chat panel (Shift+Enter for newline), configurable via `chatbot.enter_sends`
- Query input history with up/down arrow keys, persisted across sessions
- EndpointImageProvider: separate image instance when `image: true` on ai_openai instances
- Model name displayed in AI Settings dropdown labels
- `internal: true` support in module.yaml config fields (hidden from Options UI, stored in registry)

### Changed

- AI Settings panel: fixed height, inline labels ("Text AI" / "Image AI") next to dropdowns
- AI Settings panel: wider dropdowns, better vertical spacing

## [1.4.0] — 2026-02-25

### Changed

- Removed `LlmService` and `ImageService` shims — `AiService` is the sole AI service
- Moved provider ABCs (`LlmProvider`, `ImageProvider`) from `core/services/` to `ai/provider_base.py`
- Writer image tools use `services.ai.generate_image()` directly (no more `services.image`)
- Module dependencies: `chatbot`, `writer`, `draw` now require `ai` instead of `llm`/`image`
- AI provider modules no longer declare `provides_services: [llm]` or `[image]`
- Core module no longer provides `llm` or `image` services

## [1.3.0] — 2026-02-25

### Added

- AI Settings sidebar panel with dropdown selects for Text AI and Image AI instances
- Volatile instance selection: sidebar changes are session-only, Options panel sets persistent defaults
- `AiService.set_active_instance()` / `get_active_instance()` for volatile overrides
- Dynamic status display in query label ("Ask (Ready)", "Ask (...)")

### Changed

- Renamed config keys `ai.text_instance` / `ai.image_instance` → `ai.default_text_instance` / `ai.default_image_instance`
- Chat panel: removed "Chat:" response label, response area starts at top
- Chat panel: query label shows status instead of separate status field
- Sidebar panel order: AI Settings first, Chat with Document second
- Dropdown controls created programmatically via `addControl()` for proper rendering in sidebar

## [1.2.0] — 2026-02-25

### Added

- Unified AI service (`plugin/modules/ai/`) with model catalog, instance registry, and capability-based routing
- Flat model catalog format: each model has `ids` (provider-specific IDs) and `capability` field
- `resolve_model_id()` helper for provider-aware model ID resolution
- YAML model files support both new flat format and old grouped format (backward-compatible)
- `providers` field on custom models to restrict visibility to specific providers
- Endpoint-based image provider (`ai_openai/image_provider.py`)
- Menus, dialogs, icons, and dispatch handler via module manifests
- `generate_manifest.py`: XDL dialog generation, Addons.xcu menus, Accelerators.xcu shortcuts
- Options handler: list_detail widget, file picker, number spinner, dynamic options_provider
- Chatbot module: panel factory, dialog-based settings, multi-instance support
- Document service helpers (`core/services/document.py`)
- Example YAML model files in `contrib/yaml/`

### Changed

- Renamed AI modules: `openai_compat` → `ai_openai`, `ollama` → `ai_ollama`, `horde` → `ai_horde`
- Model catalog: nested `{provider: {cap: [...]}}` dict → flat list with `ids`/`capability` per model
- Deduplicated cross-provider models (Llama 3.3, Mistral Large, GPT-OSS, Mistral 7B, Pixtral Large)
- `get_model_catalog(providers=)` accepts provider key list instead of single `provider_type`
- AI module `get_model_options()` functions now use provider-filtered catalog

### Removed

- Old status bar icons (`running_*.png`, `starting_*.png`, `stopped_*.png`)

## [1.1.1] — framework branch

> The master port is not yet complete.

### Added

- Modular plugin framework with service registry, tool registry, event bus, and YAML-based module manifests
- 39 tools ported from mcp-libre (editing, search, images, frames, workflow, lifecycle, impress, diagnostics)
- HTTP server, tunnel, batch, writer navigation, and writer index modules

### Changed

- Architecture: flat `core/` monolith → modular `plugin/framework/` + `plugin/modules/`
- Config: `localwriter.json` → per-module YAML schemas with LibreOffice native Options panel
- Build: `build.sh` → `Makefile` + Python scripts (cross-platform)

### Removed

- `core/` directory, root-level `main.py`/`chat_panel.py`, custom settings dialogs
- `localwriter.json.example`, `build.sh`, root `META-INF/`
- `pricing.py`, `eval_runner.py` (not yet ported)

### Fixed

- UNO context going stale — now uses fresh `get_ctx()` on every call
- `search_in_document` regex compilation and result counting
- `set_image_properties` crop parameter handling

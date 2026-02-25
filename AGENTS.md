# AGENTS.md — Context for AI Assistants

> [!IMPORTANT]
> Update this file after making nontrivial changes.

---

## Project

**LocalWriter** — LibreOffice extension (Python/UNO) adding AI editing to Writer, Calc, Draw via chatbot sidebar + MCP server for external AI clients.

---

## Layout

```
plugin/
├── main.py                    # Entry point, UNO registration, bootstrap
├── plugin.yaml                # Global config schema
├── version.py                 # Single source of truth for version
├── _manifest.py               # Generated — do not edit
├── framework/                 # Core engine (see below)
└── modules/                   # Feature modules (see below)
extension/                     # Static LO files (XCU, manifest, dialogs, assets)
scripts/                       # build_oxt.py, generate_manifest.py, deploy scripts
tests/                         # Pytest suite (+ tests/legacy/ for old tests)
Makefile                       # All build/dev/install targets
```

### Framework (`plugin/framework/`)

| File | Role |
|------|------|
| `service_registry.py` | Singleton service management |
| `tool_registry.py` | Auto-discovers tools from modules |
| `tool_base.py`, `tool_context.py` | Base class + injected context for tools |
| `event_bus.py` | Inter-module pub/sub |
| `module_base.py`, `service_base.py` | Base classes |
| `config_schema.py` | YAML config schema + access control |
| `schema_convert.py` | YAML → XCS/XCU for LibreOffice |
| `uno_context.py` | `get_ctx()` — fresh UNO context every time |
| `http_server.py`, `http_routes.py` | Shared HTTP server |
| `dialogs.py` | Dialog utilities |
| `main_thread.py` | Main thread dispatch |
| `image_utils.py` | Image encoding |
| `logging.py` | Logging (`~/localwriter.log`) |

### Modules (`plugin/modules/`)

`core`, `writer`, `writer_nav`, `writer_index`, `calc`, `draw`, `common`, `batch`, `ai_openai`, `ai_ollama`, `ai_horde`, `chatbot`, `http`, `mcp`, `tunnel`, `tunnel_bore`, `tunnel_cloudflare`, `tunnel_ngrok`, `tunnel_tailscale`

Each module: `module.yaml` manifest → auto-discovered at build time → `_manifest.py` + XCS/XCU + Options UI.

---

## Dev Workflow

```bash
make deploy                    # Build + reinstall + restart LO + show log / wait with 10s timeout max
make deploy LOCALWRITER_SET_CONFIG="mcp.port=9000"
make log                       # ~/localwriter.log
make lo-log                    # ~/soffice-debug.log
make check-ext                 # Verify extension + manifest
make test                      # Pytest
make repack-deploy             # Re-zip build/bundle/ without regenerating
make set-config                # Show available config keys
```

### Build pipeline

```
module.yaml → generate_manifest.py → _manifest.py + XCS/XCU + XDL
extension/ + plugin/ + vendor/ → build_oxt.py → build/bundle/ → .oxt
```

See `Makefile` for all targets. Vendored deps: `requirements-vendor.txt` → `vendor/` → copied into `plugin/lib/` at build.

---

## Critical Rules

### UNO context
Services MUST NOT store `ctx` from `initialize()` — it goes stale. Use `get_ctx()` from `plugin/framework/uno_context.py`.

### Bootstrap order (`plugin/main.py`)
1. `set_fallback_ctx(ctx)`
2. `config_svc.set_manifest(manifest_dict)` — loads defaults + env overrides
3. Other modules initialize

### Auto-start
`extension/Jobs.xcu` → OnStartApp → `MainJob.execute()` → `bootstrap(ctx)`. Fallback: daemon thread after 3s. LO launched with `--writer` for desktop availability.

### Config
Namespaced `"module.key"`, access via `ModuleConfigProxy`. Override: `LOCALWRITER_SET_CONFIG="key=value,..."`.

---

## Module System

Each module in `plugin/modules/<name>/`:
- `module.yaml` — name, description, requires, provides_services, config schema
- `__init__.py` — module class extending `ModuleBase`
- `tools/` — tool classes extending `ToolBase`
- `services/` — service classes extending `ServiceBase`

`generate_manifest.py` reads all `module.yaml` → produces `_manifest.py` + XCS/XCU + XDL dialog pages + `OptionsDialog.xcu`.

---

## LO Dialog Gotchas

- **Units**: Map AppFont (not pixels). `1 unit ≈ 1/4 char width, 1/8 char height`.
- **No auto-layout**: Every control needs explicit position/size.
- **Load via**: `DialogProvider.createDialog(base_url + "/path/to/Dialog.xdl")` using `PackageInformationProvider.getPackageLocation()`.
- **Do NOT use** `vnd.sun.star.script:...?location=application` — deadlocks with sidebar.
- **Multi-page**: Use `dlg:page="N"` on controls + `dlg.getModel().Step = N`. Do NOT use `tabpagecontainer` (not in DTD).
- **Sidebar**: Call `setVisible(True)` after `createContainerWindow()`.
- **Streaming**: Pure Python `queue.Queue` + main-thread drain + `processEventsToIdle()`. No UNO Timer.
- **Document scoping**: `self.xFrame.getController().getModel()` — never `desktop.getCurrentComponent()`.
- **Writer has a drawing layer**: `hasattr(model, "getDrawPages")` is True for Writer. Use `supportsService()`.

---

## Key Files Reference

| What | Where |
|------|-------|
| Entry point | `plugin/main.py` |
| Config service | `plugin/modules/core/services/config.py` |
| Document service | `plugin/modules/core/services/document.py` |
| LLM service | `plugin/modules/core/services/llm.py` |
| Writer tools | `plugin/modules/writer/tools/*.py` |
| Calc tools | `plugin/modules/calc/tools/*.py` |
| Draw tools | `plugin/modules/draw/tools/*.py` |
| Chatbot panel | `plugin/modules/chatbot/panel.py` |
| MCP protocol | `plugin/modules/mcp/protocol.py` |
| Format support | `plugin/modules/writer/format_support.py` |
| Image utils | `plugin/framework/image_utils.py` |
| Event bus | `plugin/framework/event_bus.py` |
| UNO context | `plugin/framework/uno_context.py` |
| Build manifest | `scripts/generate_manifest.py` |
| Build OXT | `scripts/build_oxt.py` |
| Jobs auto-start | `extension/Jobs.xcu` |
| Version | `plugin/version.py` |

---

## Testing MCP

```bash
curl -s http://localhost:8766/health
curl -s http://localhost:8766/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
curl -s http://localhost:8766/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

---

## Debugging

- `~/localwriter.log` — plugin log (overwritten each session)
- `~/soffice-debug.log` — LO internal errors
- Empty log = `main.py` never loaded
- `make check-ext` — verify extension installed + manifest valid

---

## POC Extension (`poc-ext/`)

Standalone throwaway extension for testing LO features in isolation. Gitignored. Same extension ID (`org.extension.poc`).

```bash
make poc-deploy
make poc-log
make poc-uninstall
```

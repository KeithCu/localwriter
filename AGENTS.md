# AGENTS.md — Quickstart cheatsheet for AI agents

> [!IMPORTANT]
> Update this file after making nontrivial changes.

## Project

**LocalWriter** — LibreOffice extension (Python/UNO) adding AI editing to Writer, Calc, Draw via chatbot sidebar + MCP server.

## Where is what

```
plugin/main.py              Entry point, bootstrap
plugin/version.py           Version (single source of truth)
plugin/plugin.yaml          Global config schema
plugin/_manifest.py         Generated — do not edit
plugin/framework/           Core engine (services, tools, events, config, http, dialogs)
plugin/modules/<name>/      Feature modules (module.yaml + __init__.py + tools/ + services/)
extension/                  Static LO files (XCU, manifest, assets)
scripts/                    Build & deploy scripts
tests/                      Pytest suite (tests/legacy/ = old, may not pass)
Makefile                    All build/dev targets
install.ps1 / install.sh    Dev environment setup (installs bash, make, pyyaml, vendor deps)
```

## Setup & dev loop

```bash
./install.ps1               # Windows: installs deps (bash, make, pyyaml, vendor)
./install.sh                # Linux/macOS equivalent
make build                  # Build .oxt
make deploy                 # Build + reinstall + restart LO + show log
make log                    # Show ~/localwriter.log
make test                   # Pytest
make set-config             # List all config keys
make help                   # All targets
```

## Build pipeline

```
module.yaml -> generate_manifest.py -> _manifest.py + XCS/XCU + XDL
extension/ + plugin/ + vendor/ -> build_oxt.py -> .oxt
```

## Module structure

Each module in `plugin/modules/<name>/`:
- `module.yaml` — deps, config schema, actions, menus
- `__init__.py` — extends `ModuleBase`
- `tools/` — extends `ToolBase`
- `services/` — extends `ServiceBase`

Auto-discovered at build time by `generate_manifest.py`.

## Critical rules

- **UNO context**: NEVER store `ctx` from `initialize()`. Use `get_ctx()` from `framework/uno_context.py`.
- **Config**: Namespaced `"module.key"`, access via `ModuleConfigProxy`. Override: `LOCALWRITER_SET_CONFIG="key=val,..."`.
- **Document scoping**: `self.xFrame.getController().getModel()` — never `desktop.getCurrentComponent()`.
- **Sidebar**: `setVisible(True)` after `createContainerWindow()`.
- **Writer drawing layer**: `hasattr(model, "getDrawPages")` is True for Writer. Use `supportsService()`.

## Debugging

- `~/localwriter.log` — plugin log (overwritten each session)
- `~/soffice-debug.log` — LO internal errors
- Empty log = `main.py` never loaded = extension not installed
- `make check-ext` — verify install + manifest

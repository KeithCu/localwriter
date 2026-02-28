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
plugin/modules/<name>/      Feature modules (module.yaml + __init__.py + tools + services/ + providers/)
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

## Release

```bash
# bump version in plugin/version.py + CHANGELOG.md, then:
git add -A && git commit -m "v1.x.y: description"
git push
make build
gh release create v1.x.y --target framework --title "v1.x.y" --notes "changelog"
gh release upload v1.x.y build/localwriter.oxt
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
- `tool_*.py` / `tools/` — extends `ToolBase` (auto-discovered)
- `service_*.py` / `services/` — extends `ServiceBase` (explicit or auto-discovered)

Auto-discovered at build time by `generate_manifest.py`.

## Critical rules

- **UNO context**: NEVER store `ctx` from `initialize()`. Use `get_ctx()` from `framework/uno_context.py`.
- **Config**: Namespaced `"module.key"`, access via `ModuleConfigProxy`. Override: `LOCALWRITER_SET_CONFIG="key=val,..."`.
- **Document scoping**: `self.xFrame.getController().getModel()` — never `desktop.getCurrentComponent()`.
- **Sidebar**: Panels use programmatic layout (`plugin/framework/panel_layout.py`), not XDL. Use `create_panel_window()` + `add_control()` for new panels.
- **Writer drawing layer**: `hasattr(model, "getDrawPages")` is True for Writer. Use `supportsService()`.

## Cross-renderer testing

Sidebar panels use programmatic layout (no XDL) — test on multiple VCL backends to catch rendering issues:

```bash
SAL_USE_VCLPLUGIN=kf6 make deploy      # KDE/Qt6 (install: dnf install libreoffice-kf6)
SAL_USE_VCLPLUGIN=gtk3 make deploy     # GNOME (default)
SAL_USE_VCLPLUGIN=gtk4 make deploy     # GTK4
SAL_USE_VCLPLUGIN=gen make deploy      # X11 pure
```

Check: sidebar controls visible and non-overlapping, resize works, settings dropdowns functional. If the backend is missing, LO silently falls back to default — verify visually.

## Debugging

- `~/localwriter.log` — plugin log (overwritten each session)
- `~/soffice-debug.log` — LO internal errors
- Symlinks exist in the project root (`./localwriter.log`, `./soffice-debug.log`) for convenience
- Empty log = `main.py` never loaded = extension not installed
- `make check-ext` — verify install + manifest

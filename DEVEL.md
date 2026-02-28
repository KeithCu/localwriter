# Developer Guide

## Prerequisites

### Required

| Tool | Min version | Install (Linux) | Install (Windows) |
|------|-------------|-----------------|-------------------|
| **Python** | 3.8+ | `sudo dnf install python3` / `sudo apt install python3` | [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3` |
| **PyYAML** | any | `pip install --user pyyaml` or `uv pip install pyyaml` | `pip install pyyaml` |
| **LibreOffice** | 7.0+ | `sudo dnf install libreoffice` / `sudo apt install libreoffice` | [libreoffice.org](https://www.libreoffice.org/download/) |
| **make** | any | `sudo dnf install make` / `sudo apt install make` | `winget install GnuWin32.Make` |
| **git** | any | `sudo dnf install git` / `sudo apt install git` | `winget install Git.Git` |
| **pip** or **uv** | any | Usually bundled with Python | `pip` bundled; uv: `winget install astral-sh.uv` |

### Windows only

| Tool | Purpose | Install |
|------|---------|---------|
| **bash** (Git Bash) | Makefile uses Unix commands | Comes with Git for Windows |

### Optional

| Tool | Purpose | Install |
|------|---------|---------|
| **openssl** | MCP HTTPS/TLS certificates | Usually pre-installed; Windows: `winget install ShiningLight.OpenSSL` |
| **uv** | Faster pip alternative | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

## Check your setup

Run the check script to verify everything is installed:

```bash
# Linux / macOS
bash scripts/check-setup.sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\check-setup.ps1
```

The script outputs a copy-paste brief at the end — useful for sharing in issues.

## Docker build (no local setup needed)

If you just want to build the `.oxt` without installing Python, PyYAML, or any local dependencies, use the Docker build:

```bash
make docker-build
# or directly:
docker compose -f builder/docker-compose.yml up --build
```

The built extension will be at `build/localwriter.oxt`. This is the recommended approach for contributors who don't have the full dev stack installed.

To use Docker for **all** build targets (`deploy`, `install`, etc.):

```bash
# One-shot:
make deploy USE_DOCKER=1

# Persistent (create a gitignored Makefile.local):
echo "USE_DOCKER = 1" > Makefile.local
make deploy   # now uses Docker automatically
```

**Requirements:** Docker with Compose plugin (`docker compose`).

## First-time setup

```bash
# 1. Clone the repo
git clone https://github.com/quazardous/localwriter.git
cd localwriter
git checkout framework

# 2. Install dev dependencies (PyYAML, vendor libs, bash/make on Windows)
./install.sh              # Linux / macOS
# .\install.ps1           # Windows (PowerShell as Admin for winget)

# 3. Build and deploy
make deploy
```

## Build commands

| Command | What it does |
|---------|-------------|
| `make build` | Generate manifests + vendor deps + assemble `.oxt` |
| `make deploy` | **Main dev loop**: build + kill LO + unopkg reinstall + restart LO + show log |
| `make install` | Build + install via `scripts/install-plugin.sh` (interactive, asks before killing LO) |
| `make install-force` | Same as `install` but non-interactive |
| `make uninstall` | Remove extension via unopkg |
| `make clean` | Delete `build/` and `__pycache__` |

### `deploy` vs `install`

- **`make deploy`** — automated: kills LO, reinstalls, restarts, shows log. Use this for daily dev.
- **`make install`** — interactive: prompts before killing LO and before restarting. Use this for first install or when you want control.

Both do the same thing (build + unopkg remove/add), just with different levels of automation.

## Dev iteration shortcuts

| Command | What it does |
|---------|-------------|
| `make cache` | Hot-deploy to LO cache via rsync (no unopkg, faster but less reliable) |
| `make dev-deploy` | Symlink project into LO extensions dir (changes apply on restart) |
| `make dev-deploy-remove` | Remove the dev symlink |
| `make repack` | Re-zip `build/bundle/` without regenerating (fast after manual edits) |
| `make repack-deploy` | Repack + kill LO + reinstall + restart + show log |

## LibreOffice commands

| Command | What it does |
|---------|-------------|
| `make lo-start` | Launch LO with `--writer --norestore` + WARN/ERROR logging |
| `make lo-start-full` | Same but with INFO level (verbose, slow startup) |
| `make lo-kill` | Kill all LO processes |
| `make lo-restart` | Kill + wait + start |

## Config overrides

Pass config at deploy time via `LOCALWRITER_SET_CONFIG`:

```bash
make deploy LOCALWRITER_SET_CONFIG="mcp.port=9000,ai_openai.timeout=30"
```

List all available config keys:

```bash
make set-config
```

## Cross-renderer testing

LibreOffice uses VCL backend plugins for rendering. The sidebar panels use programmatic layout (`setPosSize()` + `XWindowListener`) instead of XDL files to ensure consistent rendering across all backends.

### Available backends

List installed VCL plugins:

```bash
ls /usr/lib64/libreoffice/program/libvclplug_*
```

Common backends: `gtk3`, `gtk4`, `kf6` (KDE/Qt6), `gen` (X11, no toolkit).

### Installing additional backends

```bash
# Fedora — install KDE/Qt6 backend alongside GTK (non-destructive)
sudo dnf install libreoffice-kf6

# Arch/Manjaro (KDE) — install GTK backend alongside Qt
sudo pacman -S libreoffice-fresh  # includes all VCL backends
# or if using libreoffice-still:
sudo pacman -S libreoffice-still
```

On Arch, `libreoffice-fresh` ships all VCL backends (gtk3, gtk4, qt5, qt6, gen) in one package. No extra packages needed.

### Testing with a specific backend

Set `SAL_USE_VCLPLUGIN` before any `make` target that starts LO:

```bash
# Deploy and start LO with the KDE/Qt6 backend
SAL_USE_VCLPLUGIN=kf6 make deploy

# Just restart LO with a different backend (no rebuild)
SAL_USE_VCLPLUGIN=kf6 make lo-restart

# Other backends
SAL_USE_VCLPLUGIN=gtk3 make deploy     # GNOME (default)
SAL_USE_VCLPLUGIN=gtk4 make deploy     # GTK4
SAL_USE_VCLPLUGIN=gen make deploy      # X11 pure (no toolkit)
```

If the requested backend is not installed, LO silently falls back to the default. Verify which plugin is actually loaded by checking for visual differences (widget style, font rendering).

### What to check

1. Sidebar chat panel — all 6 controls visible, no overlap
2. Resize sidebar — controls reflow correctly
3. Settings panel — AI dropdowns render and respond to clicks
4. Modal dialogs (Tools > LocalWriter options) — layout is acceptable

## Logs and debugging

| File | Content |
|------|---------|
| `~/localwriter.log` | Plugin log (overwritten each LO session) |
| `~/soffice-debug.log` | LO internal errors |

Symlinks exist in the project root for convenience (`./localwriter.log`, `./soffice-debug.log`). Created by `scripts/check-setup.sh`.

```bash
make log          # Show plugin log
make log-tail     # Tail plugin log (live)
make lo-log       # Show LO error log
```

**Empty log = extension not loaded.** Check:

1. `make check-ext` — verify extension is registered
2. LO sidebar: View > Sidebar > LocalWriter panel
3. If crash on startup, try `make nuke-cache` then `make deploy`

## Cache management

| Command | What it does |
|---------|-------------|
| `make clean-cache` | Repair extension cache (fix revoked flags, remove locks) |
| `make nuke-cache` | Wipe entire cache (requires `make deploy` after) |
| `make unbundle` | Remove bundled dev symlink |

## Release

1. Bump version in `plugin/version.py`
2. Update `CHANGELOG.md`
3. Commit and push
4. Build and create GitHub release with the `.oxt` artifact:

```bash
make build
gh release create v1.x.y --target framework --title "v1.x.y" --notes "changelog"
gh release upload v1.x.y build/localwriter.oxt
```

## Tests

```bash
make test
```

Runs pytest on `tests/`. Legacy tests in `tests/legacy/` may not pass.

## Troubleshooting

### `std::bad_alloc` during `unopkg add`

**Cause**: running `unopkg` from a Python venv instead of system Python.

**Fix**: deactivate any venv before running `make deploy`:

```bash
deactivate          # if in a venv
make deploy
```

### Panel is empty / no sidebar

1. Check `~/localwriter.log` — if empty, extension didn't load
2. `make nuke-cache && make deploy`
3. In LO: View > Sidebar, look for the LocalWriter panel

### LO crashes on second startup

Extension cache is corrupted from a failed install.

```bash
make lo-kill
make nuke-cache
make deploy
```

### `unopkg not found`

LibreOffice's `program/` directory is not on PATH. The scripts search common locations automatically. If it still fails, find it manually:

```bash
# Linux
find /usr -name unopkg -type f 2>/dev/null
find /opt -name unopkg -type f 2>/dev/null

# Windows (PowerShell)
Get-ChildItem "C:\Program Files\LibreOffice" -Recurse -Filter "unopkg.exe"
```

### XCS/XCU files — are they needed?

Yes. These are LibreOffice's standard mechanism for declarative configuration. Each module declares its config schema in `module.yaml`, and the build generates the corresponding XCS (schema) and XCU (defaults) files. They are required for the LO Options dialog and for config persistence across sessions.

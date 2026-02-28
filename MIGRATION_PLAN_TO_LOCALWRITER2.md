# Incremental Migration Plan: localwriter -> localwriter2

The goal of this plan is to incrementally reduce the diffs between the `localwriter` (current directory) and `localwriter2` (new version), ensuring the plugin remains functional at every step.

## Proposed Changes

### Phase 1: Porting Tooling & The Make System
The current `localwriter` uses a simple `build.sh` script, while `localwriter2` uses a robust `Makefile` and python scripts in `scripts/`. We can migrate this by:
1. Copying `Makefile`, `Makefile.local-dist`, and the `scripts/` directory from `localwriter2` into `localwriter`.
2. Copying `plugin/_manifest.py` and `plugin/plugin.yaml` (which the new Make system needs to build `manifest.xml`).
3. Commenting out any modules or configurations in `_manifest.py` that don't yet exist in the old `localwriter` tree.
4. Verifying that `make build` and `make deploy` work for our current codebase, and then retiring `build.sh`.

### Phase 2: Documentation and Root File Cleanup
`localwriter` has a lot of `.md` and `.odt` files cluttering the root directory. `localwriter2` organizes these better.
1. Move the root project notes and design docs into `docs/` or `contrib/` matching the `localwriter2` layout.
2. Remove any obsolete files that `localwriter2` has deleted.

### Phase 3: Bringing in Framework Infrastructure
`localwriter2` has a rich abstraction layer in `plugin/framework/` (e.g., `module_base.py`, `service_base.py`, `event_bus.py`, `tool_base.py`). 
1. Copy all new files from `localwriter2/plugin/framework/` into `localwriter/plugin/framework/`.
2. Since these are mostly base classes and utilities, dropping them in shouldn't break the existing code.
3. We can then incrementally refactor existing tools (like `format_support.py` or Calc tools) to inherit from the new base classes.

### Phase 4: Module Reorganization
`localwriter2` heavily refactors logic out of core and into specific modules under `plugin/modules/writer/`, `plugin/modules/calc/`, `plugin/modules/chatbot/`, etc.
1. We will tackle one module at a time (e.g., starting with Writer).
2. Create the missing directories and progressively move tool implementations from `plugin/modules/core/document_tools.py` into their respective module files (e.g., `plugin/modules/writer/tables.py`, etc.).
3. Update `AGENTS.md` and tests iteratively.

## Verification Plan

### Automated Tests
- Run `make test` (or `pytest`) after each incremental step to ensure unit tests still pass.

### Manual Verification
- After porting the Make system in Phase 1, we will actively use `make deploy` and verify the plugin starts up cleanly in LibreOffice.
- For each subsequent phase, we will click a few tools via the Sidebar in LibreOffice to test end-to-end functionality.

# Settings and Edit Selection Dialog Bug

## Summary

The Settings dialog and Edit Selection (input) dialog no longer appear when invoked from the LocalWriter menu. The code used to work (commit `147426778864b307467b6935ef6895a96e2481c7`). Both dialogs use `DialogProvider.createDialog()` with the script URL format.

## What Works

- **Chat with Document (sidebar)** — Works perfectly. Uses `ContainerWindowProvider.createContainerWindow()` with the package path (`base_url + "/LocalWriterDialogs/ChatPanelDialog.xdl"`), not `DialogProvider` or the Basic library.

## What Doesn't Work

- **Settings** — Menu item LocalWriter → Settings; no dialog appears
- **Edit Selection** — Menu item LocalWriter → Edit Selection (Ctrl+E); no input dialog appears

Both use the same pattern:

```python
dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
dlg = dp.createDialog("vnd.sun.star.script:LocalWriterDialogs.SettingsDialog?location=application")
# ... populate, then dlg.execute()
```

## Debug Findings (from instrumentation)

1. **`trigger()` is called correctly** — Logs show `args="settings"`, `model_is_none=False`, `has_text=True`. The code path reaches `settings_box()`.

2. **`createDialog()` never returns** — Logs show "before createDialog" but never "createDialog block exited" (from `finally`) or "createDialog succeeded" or "createDialog failed". The call blocks indefinitely; it does not throw.

3. **No exception is raised** — If it threw, we would see "createDialog failed" and "settings exception (Writer)" in the logs. We don't.

## What Was Tried (no effect)

- `location=user` instead of `location=application` — no change
- Removing `ChatPanelDialog` from `LocalWriterDialogs/dialog.xlb` — no change
- Lazy import of `streaming_deltas` — reverted; user said irrelevant

## Key Difference: Working vs Broken

The working commit (`147426778864b307467b6935ef6895a96e2481c7`) had:

- No `chat_panel.py` in manifest
- No sidebar registry (Sidebar.xcu, Factories.xcu)
- No `ChatPanelDialog` in `dialog.xlb`
- No `sys.path.insert` or `streaming_deltas` import at top of main.py

Current state adds: chat panel, sidebar, ChatPanelDialog in library, path/imports. Something in that set appears to cause `DialogProvider.createDialog()` to block when loading Settings/Edit dialogs.

## Possible Directions for Later

1. **Sidebar/chat panel interaction** — Does registering the sidebar or loading chat_panel affect the Basic library or DialogProvider state? Try temporarily removing sidebar from manifest to isolate.

2. **Different dialog loading** — Use the same package-URL approach as the sidebar (`PackageInformationProvider.getPackageLocation` + path) with `DialogProvider` or another service, if supported.

3. **LibreOffice version/behavior** — Check if a LO upgrade changed how script URLs or `location=application` resolve for extensions.

4. **DialogProvider with document model** — Some docs suggest `createInstanceWithArguments("com.sun.star.awt.DialogProvider", (model,))` for document context; might affect resolution.

5. **Known LO bug** — "Closing one dialog and opening a new dialog" can cause freezing (Ask LibreOffice). The sidebar's ContainerWindow might be treated as a dialog; opening Settings could hit that.

## Files Involved

- `main.py` — `input_box()`, `settings_box()`, `trigger()`
- `LocalWriterDialogs/SettingsDialog.xdl` — Settings dialog definition
- `LocalWriterDialogs/EditInputDialog.xdl` — Edit input dialog definition
- `LocalWriterDialogs/dialog.xlb` — Basic library index (SettingsDialog, EditInputDialog, ChatPanelDialog)
- `META-INF/manifest.xml` — Registers LocalWriterDialogs as basic-library, chat_panel, sidebar registry

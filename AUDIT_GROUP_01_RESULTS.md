# Error Audit Results - Group 01 (Framework Core)

## Summary
- Total files audited: 10
- Total broad catches found: 87
- Critical: 14 | Medium: 32 | Low: 41

## Detailed Findings

### 1. plugin/framework/dialogs.py
**Total catches**: 26

#### Catch 1 (Line 76)
- **Category**: Low
- **Context**: msgbox fallback.
- **Current Handling**: Logs exception if message box display fails.
- **Issues**: Silent failure displaying error boxes, but since it's a fallback it's mostly harmless.
- **Recommendation**: Leave as is or map to `UnoObjectError` and log.

#### Catch 2 (Line 120)
- **Category**: Low
- **Context**: show_approval_dialog (HITL).
- **Current Handling**: Logs exception and returns False.
- **Issues**: Fails to show approval box.
- **Recommendation**: Catch `UnoObjectError` directly.

#### Catch 3 (Line 181)
- **Category**: Low
- **Context**: show_web_search_query_edit_dialog.
- **Current Handling**: Swallows error parsing edit dialog text and sets it to "".
- **Issues**: Hides UI model extraction errors.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 4 (Line 204)
- **Category**: Low
- **Context**: show_web_search_query_edit_dialog outer catch.
- **Current Handling**: Returns None.
- **Issues**: Masks dialog launch failure.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 5 (Line 245)
- **Category**: Medium
- **Context**: copy_to_clipboard.
- **Current Handling**: Logs and returns False.
- **Issues**: Fails clipboard copy quietly.
- **Recommendation**: Leave or catch `UnoObjectError`.

#### Catch 6 (Line 358)
- **Category**: Low
- **Context**: _CopyListener setting CopyBtn Label.
- **Current Handling**: Logs debug and ignores.
- **Issues**: Button label doesn't update, minor UI glitch.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 7 (Line 366)
- **Category**: Low
- **Context**: show_copy_dialog.
- **Current Handling**: msgbox fallback on error.
- **Issues**: Standard UI fallback.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 8 (Line 433)
- **Category**: Low
- **Context**: Status dialog _CopyListener setting CopyBtn Label.
- **Current Handling**: Logs debug.
- **Issues**: Button label won't update.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 9 (Line 450)
- **Category**: Low
- **Context**: Status dialog background probe UI update.
- **Current Handling**: Pass (assumes dialog closed).
- **Issues**: Hides unexpected UI update errors while dialog is open.
- **Recommendation**: Catch `com.sun.star.lang.DisposedException` and `UnoObjectError`.

#### Catch 10 (Line 457)
- **Category**: Low
- **Context**: Status dialog outer exception.
- **Current Handling**: msgbox fallback.
- **Issues**: Fallback.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 11 (Line 507)
- **Category**: Low
- **Context**: About dialog.
- **Current Handling**: msgbox fallback.
- **Issues**: Fallback.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 12 (Line 529)
- **Category**: Low
- **Context**: _xcc helper to query XControlContainer.
- **Current Handling**: Returns None.
- **Issues**: Control traversal silently stops.
- **Recommendation**: Catch `UnoObjectError` or `RuntimeException`.

#### Catch 13 (Line 556)
- **Category**: Low
- **Context**: _dialog_model_element_names.
- **Current Handling**: Returns empty tuple.
- **Issues**: Fails to find element names.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 14 (Line 588)
- **Category**: Low
- **Context**: translate_dialog root container check.
- **Current Handling**: root_child_count = 0.
- **Issues**: Prevents normal translation traversal.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 15 (Line 611)
- **Category**: Medium
- **Context**: translate_one property translation.
- **Current Handling**: Logs debug.
- **Issues**: Single label doesn't translate.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 16 (Line 618)
- **Category**: Medium
- **Context**: translate_one child loop.
- **Current Handling**: Logs debug.
- **Issues**: Entire child tree misses translation.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 17 (Line 623)
- **Category**: Medium
- **Context**: translate_dialog outer translate_one.
- **Current Handling**: Logs debug.
- **Issues**: Entire dialog misses translation.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 18 (Line 639)
- **Category**: Low
- **Context**: translate_dialog fallback name loop.
- **Current Handling**: Logs debug.
- **Issues**: Individual fallback control misses translation.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 19 (Line 688)
- **Category**: Medium
- **Context**: get_optional fallback control fetch.
- **Current Handling**: Logs debug and returns None.
- **Issues**: Returns None instead of throwing. Expected behaviour but masks underlying UNO crashes.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 20 (Line 707)
- **Category**: Low
- **Context**: is_checkbox_control.
- **Current Handling**: Logs debug, returns False.
- **Issues**: Misidentifies checkbox.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 21 (Line 722)
- **Category**: Low
- **Context**: set_control_enabled.
- **Current Handling**: Logs debug.
- **Issues**: Fails to disable control.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 22 (Line 736)
- **Category**: Low
- **Context**: set_control_visible.
- **Current Handling**: Logs debug.
- **Issues**: Fails to hide/show control.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 23 (Line 750)
- **Category**: Low
- **Context**: get_control_text.
- **Current Handling**: Logs debug, returns default.
- **Issues**: Fails to read UI value.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 24 (Line 773)
- **Category**: Low
- **Context**: set_control_text.
- **Current Handling**: Logs debug.
- **Issues**: Fails to set text.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 25 (Line 789)
- **Category**: Low
- **Context**: get_checkbox_state.
- **Current Handling**: Logs debug, returns 0.
- **Issues**: Fails to read checkbox state.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 26 (Line 806)
- **Category**: Low
- **Context**: set_checkbox_state.
- **Current Handling**: Logs debug.
- **Issues**: Fails to set checkbox state.
- **Recommendation**: Catch `UnoObjectError`.


### 2. plugin/framework/i18n.py
**Total catches**: 2

#### Catch 1 (Line 59)
- **Category**: Low
- **Context**: Determine LibreOffice locale property.
- **Current Handling**: Returns default locale if property missing.
- **Issues**: Minor localization fallback.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 2 (Line 101)
- **Category**: Medium
- **Context**: Initialize gettext translation logic.
- **Current Handling**: Falls back to `NullTranslations`.
- **Issues**: UI remains untranslated if locales fail.
- **Recommendation**: Catch `ConfigError` / `FileNotFoundError`.


### 3. plugin/framework/errors.py
**Total catches**: 0


### 4. plugin/framework/worker_pool.py
**Total catches**: 8

#### Catch 1 (Line 42)
- **Category**: Critical
- **Context**: Background thread execution wrapper `_worker`.
- **Current Handling**: Logs error and traceback.
- **Issues**: Thread crash is swallowed, main thread might wait forever.
- **Recommendation**: Catch `Exception`, but wrap in `WriterAgentException` if sending to UI or emit specific `ToolExecutionError`.

#### Catch 2 (Line 48)
- **Category**: Critical
- **Context**: Background thread error callback itself failing.
- **Current Handling**: Logs the error.
- **Issues**: Double fault in async worker.
- **Recommendation**: Keep broad `Exception` since it's the absolute last line of defense in a thread, but ensure logging uses `log_exception`.

#### Catch 3 (Line 90)
- **Category**: Critical
- **Context**: `AsyncProcess.start()` subprocess creation.
- **Current Handling**: Logs error and re-raises.
- **Issues**: Leaves caller to handle raw `Exception`.
- **Recommendation**: Wrap in `ToolExecutionError` or `NetworkError` depending on context and re-raise.

#### Catch 4 (Line 125)
- **Category**: Medium
- **Context**: `AsyncProcess` stream reader thread loop.
- **Current Handling**: Logs debug.
- **Issues**: Stream read dies silently.
- **Recommendation**: Catch `IOError` or wrap in `NetworkError`.

#### Catch 5 (Line 130)
- **Category**: Low
- **Context**: `AsyncProcess` stream reader finally block close.
- **Current Handling**: Pass.
- **Issues**: Fails to close stream.
- **Recommendation**: Leave `Exception` to ignore `close()` errors.

#### Catch 6 (Line 137)
- **Category**: Low
- **Context**: `AsyncProcess` stream drainer iteration.
- **Current Handling**: Pass.
- **Issues**: None.
- **Recommendation**: Leave `Exception`.

#### Catch 7 (Line 142)
- **Category**: Low
- **Context**: `AsyncProcess` stream drainer finally block close.
- **Current Handling**: Pass.
- **Issues**: None.
- **Recommendation**: Leave `Exception`.

#### Catch 8 (Line 151)
- **Category**: Medium
- **Context**: `AsyncProcess._wait_for_exit` calling `on_exit_cb`.
- **Current Handling**: Logs error.
- **Issues**: Fails the callback without crashing the process monitoring.
- **Recommendation**: Keep `Exception` but log clearly.


### 5. plugin/framework/legacy_ui.py
**Total catches**: 15

#### Catch 1 (Line 51)
- **Category**: Medium
- **Context**: `input_box` dialog creation.
- **Current Handling**: Logs and raises raw error.
- **Issues**: Bubbles raw error to UI event loop.
- **Recommendation**: Wrap in `UnoObjectError`.

#### Catch 2 (Line 88)
- **Category**: Medium
- **Context**: `input_box` execution and return flow.
- **Current Handling**: Logs and raises raw error.
- **Issues**: Bubbles raw error.
- **Recommendation**: Wrap in `UnoObjectError`.

#### Catch 3 (Line 96)
- **Category**: Low
- **Context**: `input_box` dialog disposal.
- **Current Handling**: Pass.
- **Issues**: Dialog leak if disposal fails.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 4 (Line 117)
- **Category**: Critical
- **Context**: `settings_box` dialog creation.
- **Current Handling**: Catches Exception, wraps in `UnoObjectError` and raises.
- **Issues**: Excellent handling!
- **Recommendation**: Keep as is.

#### Catch 5 (Line 212)
- **Category**: Medium
- **Context**: `EndpointCombinedListener` updating dropdowns.
- **Current Handling**: Logs error.
- **Issues**: UI dropdowns fail to update.
- **Recommendation**: Catch `UnoObjectError` or `ConfigError`.

#### Catch 6 (Line 224)
- **Category**: Medium
- **Context**: `EndpointCombinedListener` item state changed.
- **Current Handling**: Logs error.
- **Issues**: Fails to update endpoint text.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 7 (Line 230)
- **Category**: Medium
- **Context**: `EndpointCombinedListener` text changed.
- **Current Handling**: Logs error.
- **Issues**: Fails to update dropdowns.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 8 (Line 244)
- **Category**: Low
- **Context**: settings_box checkbox state initialization.
- **Current Handling**: Pass.
- **Issues**: Checkbox defaults wrongly.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 9 (Line 261)
- **Category**: Low
- **Context**: populating StringItemList for comboboxes.
- **Current Handling**: Logs error.
- **Issues**: Combobox is empty.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 10 (Line 280)
- **Category**: Low
- **Context**: settings_box set text for basic controls.
- **Current Handling**: Pass.
- **Issues**: Value fails to show.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 11 (Line 288)
- **Category**: Low
- **Context**: settings_box disable web_cache fields.
- **Current Handling**: Pass.
- **Issues**: Fields remain incorrectly enabled.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 12 (Line 294)
- **Category**: Low
- **Context**: settings_box set Title.
- **Current Handling**: Pass.
- **Issues**: Dialog missing title.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 13 (Line 309)
- **Category**: Low
- **Context**: settings_box retrieve control text on OK.
- **Current Handling**: Defaults to "".
- **Issues**: Fails to save setting.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 14 (Line 332)
- **Category**: Medium
- **Context**: settings_box entire field extraction loop failure.
- **Current Handling**: Sets field value to "".
- **Issues**: Massive configuration data loss on save.
- **Recommendation**: Catch `UnoObjectError` and `ValueError`. Do not silent default everything to "".

#### Catch 15 (Line 338)
- **Category**: Critical
- **Context**: settings_box overarching execute block.
- **Current Handling**: msgbox error, returns error payload.
- **Issues**: Good fallback but should be specific to the underlying exception.
- **Recommendation**: Keep broad, but use `format_error_payload(e)`.


### 6. plugin/framework/utils.py
**Total catches**: 6

#### Catch 1 (Line 19)
- **Category**: Medium
- **Context**: `get_url_hostname`
- **Current Handling**: Returns "" on parsing failure.
- **Issues**: Masking `ValueError` from `urllib`.
- **Recommendation**: Catch `ValueError`.

#### Catch 2 (Line 30)
- **Category**: Medium
- **Context**: `get_url_domain`
- **Current Handling**: Returns truncated URL.
- **Issues**: Masking `ValueError` from `urllib`.
- **Recommendation**: Catch `ValueError`.

#### Catch 3 (Line 38)
- **Category**: Medium
- **Context**: `get_url_path`
- **Current Handling**: Returns "".
- **Issues**: Masking `ValueError`.
- **Recommendation**: Catch `ValueError`.

#### Catch 4 (Line 46)
- **Category**: Medium
- **Context**: `get_url_query_dict`
- **Current Handling**: Returns {}.
- **Issues**: Masking `ValueError`.
- **Recommendation**: Catch `ValueError`.

#### Catch 5 (Line 57)
- **Category**: Medium
- **Context**: `get_url_path_and_query`
- **Current Handling**: Returns "".
- **Issues**: Masking `ValueError`.
- **Recommendation**: Catch `ValueError`.

#### Catch 6 (Line 65)
- **Category**: Medium
- **Context**: `is_pdf_url`
- **Current Handling**: Returns False.
- **Issues**: Masking `ValueError`.
- **Recommendation**: Catch `ValueError`.


### 7. plugin/framework/logging.py
**Total catches**: 14

#### Catch 1 (Line 66)
- **Category**: Medium
- **Context**: init_logging setting global paths.
- **Current Handling**: Pass.
- **Issues**: Logging fails to initialize paths correctly.
- **Recommendation**: Catch `ConfigError` or `OSError`.

#### Catch 2 (Line 95)
- **Category**: Low
- **Context**: init_logging closing existing handlers.
- **Current Handling**: Pass.
- **Issues**: Handler leak.
- **Recommendation**: Leave `Exception`.

#### Catch 3 (Line 124)
- **Category**: Low
- **Context**: init_logging generic block end.
- **Current Handling**: Pass.
- **Issues**: None.
- **Recommendation**: Catch `OSError`.

#### Catch 4 (Line 151)
- **Category**: Critical
- **Context**: sys.excepthook format_error_payload
- **Current Handling**: Pass.
- **Issues**: Fails to format unhandled exception crash context.
- **Recommendation**: Catch `Exception`.

#### Catch 5 (Line 154)
- **Category**: Critical
- **Context**: sys.excepthook outer block
- **Current Handling**: Pass.
- **Issues**: Fails to log unhandled exception.
- **Recommendation**: Catch `Exception`.

#### Catch 6 (Line 158)
- **Category**: Critical
- **Context**: sys.excepthook calling original excepthook.
- **Current Handling**: Pass.
- **Issues**: Fails chain.
- **Recommendation**: Catch `Exception`.

#### Catch 7 (Line 178)
- **Category**: Critical
- **Context**: threading.excepthook formatting payload.
- **Current Handling**: Pass.
- **Issues**: Same as sys hook.
- **Recommendation**: Catch `Exception`.

#### Catch 8 (Line 181)
- **Category**: Critical
- **Context**: threading.excepthook outer logging.
- **Current Handling**: Pass.
- **Issues**: Same as sys hook.
- **Recommendation**: Catch `Exception`.

#### Catch 9 (Line 186)
- **Category**: Critical
- **Context**: threading.excepthook original chain.
- **Current Handling**: Pass.
- **Issues**: Same as sys hook.
- **Recommendation**: Catch `Exception`.

#### Catch 10 (Line 201)
- **Category**: Medium
- **Context**: log_exception error
- **Current Handling**: Pass.
- **Issues**: Circular logging failure.
- **Recommendation**: Catch `Exception`.

#### Catch 11 (Line 227)
- **Category**: Low
- **Context**: format_tool_call_for_display parsing error.
- **Current Handling**: Returns format error string.
- **Issues**: Fails display formatting.
- **Recommendation**: Catch `TypeError` / `ValueError`.

#### Catch 12 (Line 278)
- **Category**: Low
- **Context**: format_tool_result_for_display parsing error.
- **Current Handling**: Returns format error string.
- **Issues**: Fails display formatting.
- **Recommendation**: Catch `TypeError` / `ValueError`.

#### Catch 13 (Line 298)
- **Category**: Medium
- **Context**: agent_log file write.
- **Current Handling**: Pass.
- **Issues**: Silent failure to write agent log.
- **Recommendation**: Catch `OSError`.

#### Catch 14 (Line 337)
- **Category**: Low
- **Context**: Watchdog thread updating UI status control.
- **Current Handling**: Pass.
- **Issues**: Fails to set text (expected on dead UI).
- **Recommendation**: Catch `UnoObjectError`.


### 8. plugin/framework/async_stream.py
**Total catches**: 8

#### Catch 1 (Line 160)
- **Category**: Medium
- **Context**: `run_stream_drain_loop` approval callback.
- **Current Handling**: Logs error.
- **Issues**: Approval handler crash is isolated.
- **Recommendation**: Catch `Exception` since it's an external callback boundary, but map it if possible.

#### Catch 2 (Line 191)
- **Category**: Critical
- **Context**: `run_stream_drain_loop` general processing loop exception.
- **Current Handling**: Logs error, breaks loop, calls `on_error`.
- **Issues**: Entire stream loop crashes.
- **Recommendation**: Keep `Exception` here as it's a thread loop boundary, ensure `WriterAgentException` formatting.

#### Catch 3 (Line 236)
- **Category**: Critical
- **Context**: `stream_completion` worker thread outer catch.
- **Current Handling**: Formats error payload and queues it.
- **Issues**: Good handling, but broad.
- **Recommendation**: Keep `Exception` as thread boundary.

#### Catch 4 (Line 243)
- **Category**: Medium
- **Context**: `stream_completion` UNO Toolkit instance creation.
- **Current Handling**: Calls `on_error_fn` directly.
- **Issues**: Good fallback.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 5 (Line 304)
- **Category**: Critical
- **Context**: `stream_request_with_tools` worker thread outer catch.
- **Current Handling**: Formats error payload and queues it.
- **Issues**: Good handling, but broad.
- **Recommendation**: Keep `Exception` as thread boundary.

#### Catch 6 (Line 311)
- **Category**: Medium
- **Context**: `stream_request_with_tools` UNO Toolkit creation.
- **Current Handling**: Calls `on_error_fn`.
- **Issues**: Good fallback.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 7 (Line 346)
- **Category**: Critical
- **Context**: `run_blocking_with_pump` worker thread exception.
- **Current Handling**: Queues error.
- **Issues**: Good handling, thread boundary.
- **Recommendation**: Keep `Exception` as thread boundary.

#### Catch 8 (Line 352)
- **Category**: Medium
- **Context**: `run_blocking_with_pump` UNO Toolkit creation.
- **Current Handling**: Falls back to direct synchronous execution.
- **Issues**: Safe fallback when no UI.
- **Recommendation**: Catch `UnoObjectError`.


### 9. plugin/framework/main_thread.py
**Total catches**: 4

#### Catch 1 (Line 76)
- **Category**: Medium
- **Context**: Initialize AsyncCallback UNO service.
- **Current Handling**: Logs warning, disables async dispatch.
- **Issues**: Degrades performance on systems without the service.
- **Recommendation**: Catch `UnoObjectError` or `Exception` (as expected).

#### Catch 2 (Line 104)
- **Category**: Critical
- **Context**: `_MainThreadCallback` queue execution.
- **Current Handling**: Catches error, stores in `item.exception`.
- **Issues**: Crucial for cross-thread exception bubbling.
- **Recommendation**: Keep `Exception`.

#### Catch 3 (Line 123)
- **Category**: Medium
- **Context**: `_poke_vcl` AsyncCallback dispatch `Any`.
- **Current Handling**: Retries with `None`.
- **Issues**: UNO interface variance.
- **Recommendation**: Catch `UnoObjectError`.

#### Catch 4 (Line 127)
- **Category**: Medium
- **Context**: `_poke_vcl` AsyncCallback dispatch `None`.
- **Current Handling**: Logs warning.
- **Issues**: Fails to trigger main thread execution.
- **Recommendation**: Catch `UnoObjectError`.


### 10. plugin/framework/tool_registry.py
**Total catches**: 3

#### Catch 1 (Line 69)
- **Category**: Medium
- **Context**: `auto_discover_package` module iteration.
- **Current Handling**: Logs error, skips module.
- **Issues**: Tools in that module are not loaded.
- **Recommendation**: Catch `ImportError` or `Exception`.

#### Catch 2 (Line 93)
- **Category**: Medium
- **Context**: `auto_discover` instantiation.
- **Current Handling**: Logs error, skips tool.
- **Issues**: Tool is broken, not loaded.
- **Recommendation**: Catch `Exception`.

#### Catch 3 (Line 225)
- **Category**: Critical
- **Context**: `execute_tool` main execution catch.
- **Current Handling**: Logs exception, emits event, formats payload.
- **Issues**: Prevents individual tool crash from crashing the AI loop.
- **Recommendation**: Keep `Exception`, since tools can fail in arbitrary ways. Ensure it wraps securely into `ToolExecutionError` or standard payload (which it does).

## Priority Recommendations
List the top 3 most critical fixes from this group:

1. **File**: `plugin/framework/worker_pool.py` Line 90
   - **Reason**: Background subprocess execution failure.
   - **Impact**: Fails silently in the caller if not handled correctly, leads to ghost processes or stalled logic.
   - **Recommendation**: Wrap with `ToolExecutionError` or `OSError` explicitly before raising.

2. **File**: `plugin/framework/legacy_ui.py` Line 332
   - **Reason**: Settings UI parsing failure during `SettingsDialog` save.
   - **Impact**: Silently wiping user settings `result[field["name"]] = ""` if a model read fails, which corrupts user config.
   - **Recommendation**: Catch `UnoObjectError` and `ValueError` specifically, and fail cleanly rather than wiping values.

3. **File**: `plugin/framework/dialogs.py` Line 688
   - **Reason**: `get_optional` UNO control retrieval
   - **Impact**: Currently catches any Exception, which hides underlying LibreOffice bridge crashes when looking for dialog elements, making debugging UI issues extremely difficult.
   - **Recommendation**: Catch `UnoObjectError` and `com.sun.star.lang.DisposedException`.

## Next Step
- Apply recommended fixes to critical issues first
- Create unit tests for fixed error paths
- Verify no regressions in existing functionality

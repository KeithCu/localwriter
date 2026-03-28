# Framework Test Coverage Analysis

## Summary
- **Total framework modules**: 33
- **Test files**: 44
- **Total tests**: 366
- **All tests passing**: ✅

## Coverage Map

### Covered Modules (with tests)
| Module | Test File | Notes |
|--------|-----------|-------|
| async_stream.py | test_async_stream.py | ✅ 10 tests |
| config.py | test_config_sync.py, test_config_service.py | ✅ 20 tests |
| errors.py | test_error_handling.py | ✅ 10 tests |
| event_bus.py | test_event_bus.py | ✅ 5 tests |
| logging.py | test_logging.py | ✅ 3 tests |
| main_thread.py | test_main_thread.py | ✅ 5 tests |
| module_base.py | test_module_base.py | ✅ 3 tests |
| module_loader.py | test_module_loader.py | ✅ 3 tests |
| service_base.py | test_service_base.py | ✅ 14 tests |
| service_registry.py | test_service_registry.py | ✅ 10 tests |
| tool_base.py | test_tool_base.py | ✅ 4 tests |
| tool_context.py | test_tool_context.py | ✅ 2 tests |
| tool_registry.py | test_tool_registry.py | ✅ 18 tests |
| uno_context.py | test_uno_context.py | ✅ 3 tests |
| worker_pool.py | test_framework_utils.py | ✅ 2 tests |
| i18n.py | test_i18n.py | ✅ 5 tests |
| image_tools.py | test_image_tools_cursor.py | ✅ 3 tests |
| image_utils.py | test_image_service_refactor.py, test_image_status_callback.py | ✅ 10 tests |
| schema_convert.py | test_schema_convert.py | ✅ 3 tests |
| streaming_deltas.py | test_streaming_deltas.py | ✅ 3 tests |
| utils.py | test_framework_utils.py | ✅ 8 tests |

### Uncovered Modules (no dedicated tests)
| Module | Imported By | Criticality |
|--------|-------------|-------------|
| auth.py | http/client.py, scripts/translate_missing.py | High (auth logic) |
| constants.py | http/*, chatbot/*, modules/*, contrib/* | High (shared constants) |
| default_models.py | ? | Low (data only) |
| dialogs.py | framework/*, modules/* | High (UI helpers) |
| format.py | main.py | Medium (format service) |
| legacy_ui.py | framework/*, modules/* | Medium (legacy UI) |
| listeners.py | framework/*, modules/chatbot/* | Medium (listener base classes) |
| pricing.py | tests/smoke_pricing.py, tests/eval_runner.py | Low (pricing utils) |
| settings_dialog.py | framework/*, modules/http/* | High (settings UI) |
| smol_model.py | modules/chatbot/web_research.py | Medium (smolagents wrapper) |

## Recommendations

### High Priority (Critical Path)
1. **auth.py**: Add unit tests for `resolve_auth_for_config`, `build_auth_headers`, and provider detection logic. Mock `get_provider_from_endpoint` and `normalize_endpoint_url`.
2. **constants.py**: Add tests for `get_chat_system_prompt_for_document`, `get_greeting_for_document`, and other prompt builders. Ensure Writer/Calc/Draw prompts are correct.
3. **dialogs.py**: Add tests for dialog creation helpers (`add_dialog_button`, `add_dialog_label`, etc.) and translation logic.
4. **settings_dialog.py**: Add tests for `get_settings_field_specs` and `apply_settings_result` to ensure settings are correctly read/written.

### Medium Priority (Used but Stable)
1. **format.py**: Add tests for `FormatService.export_as_text`, `export_as_html`, `import_from_html` with mock UNO objects.
2. **listeners.py**: Add tests for `BaseActionListener`, `BaseItemListener`, etc., to ensure exception handling works.
3. **smol_model.py**: Add tests for `WriterAgentSmolModel.generate` with mocked `LlmClient`.

### Low Priority (Data/Utility)
1. **default_models.py**: Likely data-only; no tests needed unless logic is added.
2. **legacy_ui.py**: Deprecated; tests not urgent unless actively used.
3. **pricing.py**: Already used by tests; add unit tests if pricing logic becomes more complex.

## Quick Wins
- **auth.py**: High impact, small module (~200 lines), critical for API calls.
- **constants.py**: High impact, contains prompt templates used by chat and tools.
- **dialogs.py**: High impact, used by all UI dialogs; test helpers to prevent regressions.

## Notes
- **dialogs.py** and **settings_dialog.py** are heavily used by the UI but lack unit tests. They are good candidates for mock-based tests.
- **auth.py** is critical for API calls and should be tested to prevent auth failures.
- **constants.py** contains prompt templates; tests would catch regressions in system prompts.
- **format.py** and **listeners.py** are stable but could benefit from tests if they change frequently.

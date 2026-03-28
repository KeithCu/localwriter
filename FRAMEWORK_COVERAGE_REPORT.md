# Framework Coverage Report (pytest-cov)

## Summary
- **Total lines**: 4607
- **Covered lines**: 1999 (43%)
- **Missing lines**: 2607 (57%)
- **Tests**: 366 passed

## Coverage by Module

### Well Covered (>= 80%)
| Module | Stmts | Cover | Missing |
|--------|-------|-------|---------|
| __init__.py | 0 | 100% | - |
| module_base.py | 21 | 100% | - |
| service_base.py | 5 | 100% | - |
| tool_context.py | 13 | 100% | - |
| schema_convert.py | 33 | 100% | - |
| errors.py | 77 | 91% | 51, 79, 85, 91-94, 145, 149 |
| event_bus.py | 59 | 90% | 91-92, 96, 98, 106-107 |
| streaming_deltas.py | 45 | 98% | 103 |
| tool_base.py | 70 | 81% | 178, 182-185, 189-202 |
| auth.py | 62 | 87% | 26, 110, 144, 149, 191, 199-201 |
| i18n.py | 45 | 89% | 72, 103-106 |
| image_utils.py | 238 | 75% | 50, 94, 96, 137-142, 155-173, 202-203, 211-212, 218-221, 228, 270-272, 281-287, 302-307, 315, 323-324, 328-329, 359-369 |
| module_loader.py | 75 | 83% | 18-22, 45, 79-83, 106-107 |
| listeners.py | 60 | 62% | 36-44, 53, 61, 65, 73, 77, 85, 89, 97, 101, 105, 112, 115, 118, 121 |
| logging.py | 289 | 65% | 89, 96-97, 139, 145-160, 168-188, 194, 233, 248-249, 259-261, 271-275, 294, 300-301, 320-321, 329-332, 341-344, 351-352, 359-372, 389-411, 417-421 |
| service_registry.py | 48 | 71% | 49-69, 77 |
| tool_registry.py | 148 | 70% | 48-49, 51-52, 54-55, 59-62, 67-68, 72-87, 110-111, 129, 131, 133, 149, 153-154, 180-182, 195-199, 284-290 |
| utils.py | 50 | 64% | 11, 19-20, 28, 30-31, 38-39, 46-47, 55, 57-58, 62-66 |

### Partially Covered (30%-79%)
| Module | Stmts | Cover | Missing |
|--------|-------|-------|---------|
| async_stream.py | 223 | 61% | 76-79, 91-104, 164, 172-173, 175-179, 200-203, 223-234, 252-288, 313-359, 388-391, 407 |
| config.py | 844 | 57% | 31, 97, 106, 118-119, 141-142, 148, 260-261, 264-265, 268-269, 272-273, 297-303, 387-388, 393, 400, 415-416, 422, 429, 438-439, 444, 456-457, 460, 465-466, 470-472, 492-518, 548, 550, 557-558, 564-565, 571, 574, 576, 580, 588-594, 602-625, 630-639, 646-672, 679-723, 732, 752-759, 764, 769-775, 780-786, 791-817, 826-843, 848-854, 868, 871, 889-901, 909-921, 967, 976-988, 1014, 1040-1066, 1074, 1077-1082, 1087, 1100-1148, 1158-1160, 1165-1168, 1179-1186, 1199-1202, 1213, 1215-1218 |
| constants.py | 39 | 59% | 179-186, 193-203 |
| main_thread.py | 89 | 45% | 61-82, 87-112, 117-128, 147, 172-173 |
| settings_dialog.py | 131 | 45% | 86-88, 101-102, 108-189, 206-209, 215-220 |
| uno_context.py | 47 | 45% | 63-65, 70-79, 84-85, 90-93, 98-104 |
| worker_pool.py | 106 | 36% | 81-82, 99-113, 117, 121-147, 153-165, 168-177, 180-186, 190-198 |
| image_tools.py | 196 | 29% | 33-43, 50-62, 82, 107-111, 120-137, 146-159, 167-207, 215-228, 238-281, 284-311 |

### Poorly Covered (< 30%)
| Module | Stmts | Cover | Missing |
|--------|-------|-------|---------|
| format.py | 63 | 0% | 19-117 |
| pricing.py | 65 | 0% | 17-105 |
| legacy_ui.py | 323 | 1% | 31-420 |
| document.py | 574 | 11% | 29-34, 42-44, 54-56, 61-85, 90-131, 136-139, 169-174, 183-217, 222-229, 234-257, 262-274, 283-293, 301-326, 332-355, 361-424, 429-467, 472-530, 538-549, 560-565, 570-586, 591-628, 633-679, 684-717, 727, 730, 734, 737-739, 747, 754-775, 779-795, 799, 803, 807, 811, 815, 819, 823-826 |
| dialogs.py | 503 | 9% | 59-77, 87-125, 135-209, 217-250, 258-270, 275-285, 290-299, 304-315, 323-371, 389-462, 470-512, 527-533, 542-547, 552-561, 571-643, 651-656, 664-668, 673-681, 689-699, 707-718, 724-732, 738-746, 753, 757-761, 771-783, 791-800, 808-816, 828-829, 833 |
| smol_model.py | 41 | 27% | 22-23, 38-100 |
| default_models.py | 25 | 16% | 23-30, 35-40, 56-68 |

## Critical Gaps

### High Impact (Used by many modules)
1. **dialogs.py** (9%): Used by all UI dialogs. Needs tests for `add_dialog_button`, `add_dialog_label`, `add_dialog_edit`, `add_dialog_hyperlink`, `translate_dialog`.
2. **document.py** (11%): Core document manipulation. Needs tests for `get_document_context_for_chat`, `get_selection_range`, `get_document_length`, etc.
3. **constants.py** (59%): Prompt templates. Needs tests for `get_chat_system_prompt_for_document`, `get_greeting_for_document`.
4. **auth.py** (87%): Auth logic. Needs tests for `resolve_auth_for_config`, `build_auth_headers`.

### Medium Impact (Used by specific features)
1. **format.py** (0%): FormatService. Needs tests for `export_as_text`, `export_as_html`, `import_from_html`.
2. **settings_dialog.py** (45%): Settings UI. Needs tests for `get_settings_field_specs`, `apply_settings_result`.
3. **image_tools.py** (29%): Image tools. Needs tests for `get_selected_image_base64`, `insert_image`, `replace_image_in_place`.

### Low Impact (Utility/Data)
1. **pricing.py** (0%): Pricing utils. Used only by tests.
2. **legacy_ui.py** (1%): Deprecated UI code.
3. **default_models.py** (16%): Data-only module.
4. **smol_model.py** (27%): Smolagents wrapper. Used only by web research.

## Recommendations

### Quick Wins (High Coverage Gain)
1. **dialogs.py**: Add unit tests with mocked UNO controls. Can reach ~80% coverage.
2. **constants.py**: Add tests for prompt builders. Can reach ~90% coverage.
3. **auth.py**: Add tests for auth resolution. Can reach ~95% coverage.

### Medium Effort
1. **document.py**: Add integration tests with mock UNO documents. Target ~60% coverage.
2. **format.py**: Add tests for FormatService. Target ~80% coverage.
3. **settings_dialog.py**: Add tests for settings logic. Target ~70% coverage.

### Low Priority
1. **pricing.py**: Add tests if pricing logic becomes more complex.
2. **legacy_ui.py**: Deprecated; tests not urgent.
3. **default_models.py**: Data-only; no tests needed.

## How to Improve Coverage

### For dialogs.py
```bash
# Create test file
write_file(path="plugin/tests/test_dialogs.py", content="""
from unittest.mock import Mock
import pytest
from plugin.framework.dialogs import add_dialog_button, add_dialog_label

def test_add_dialog_button():
    dlg_model = Mock()
    mock_control = Mock()
    dlg_model.createInstance.return_value = mock_control
    mock_control_model = Mock()
    mock_control.getModel.return_value = mock_control_model

    add_dialog_button(dlg_model, "btn1", "Click Me", 10, 20, 80, 24)

    dlg_model.createInstance.assert_called_once_with("com.sun.star.awt.UnoControlButtonModel")
    mock_control_model.PositionX.assert_called_once_with(10)
    mock_control_model.Label.assert_called_once_with("Click Me")

def test_add_dialog_label():
    dlg_model = Mock()
    mock_control = Mock()
    dlg_model.createInstance.return_value = mock_control
    mock_control_model = Mock()
    mock_control.getModel.return_value = mock_control_model

    add_dialog_label(dlg_model, "lbl1", "Hello", 10, 20, 100, 12)

    dlg_model.createInstance.assert_called_once_with("com.sun.star.awt.UnoControlFixedTextModel")
    mock_control_model.Label.assert_called_once_with("Hello")
""")

# Run tests
. .venv/bin/activate.fish && pytest plugin/tests/test_dialogs.py -v
```

### For constants.py
```bash
# Add tests for prompt builders
write_file(path="plugin/tests/test_constants.py", content="""
from unittest.mock import Mock
from plugin.framework.constants import get_chat_system_prompt_for_document

def test_get_chat_system_prompt_for_document():
    mock_model = Mock()
    mock_model.supportsService.return_value = True
    result = get_chat_system_prompt_for_document(mock_model, "test instructions")
    assert "test instructions" in result
""")

. .venv/bin/activate.fish && pytest plugin/tests/test_constants.py -v
```

### For auth.py
```bash
# Add tests for auth resolution
write_file(path="plugin/tests/test_auth.py", content="""
from unittest.mock import patch
from plugin.framework.auth import resolve_auth_for_config, build_auth_headers

def test_resolve_auth_for_config():
    config = {"endpoint": "https://openrouter.ai", "api_key": "test_key"}
    result = resolve_auth_for_config(config)
    assert result["provider"] == "openrouter"
    assert result["header_style"] == "bearer"

def test_build_auth_headers():
    auth_info = {"header_style": "bearer", "api_key": "test_key"}
    headers = build_auth_headers(auth_info)
    assert headers["Authorization"] == "Bearer test_key"
""")

. .venv/bin/activate.fish && pytest plugin/tests/test_auth.py -v
```

## Summary
- **Overall coverage**: 43% (1999/4607 lines)
- **Critical gaps**: dialogs.py (9%), document.py (11%), constants.py (59%), auth.py (87%)
- **Quick wins**: Add tests for dialogs.py, constants.py, auth.py to reach ~55-60% overall coverage.

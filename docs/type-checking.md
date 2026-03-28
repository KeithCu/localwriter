# Static type checking (`ty`)

WriterAgent uses [Astral’s `ty`](https://docs.astral.sh/ty/) on the `plugin/` tree. This document covers **what changed in the code** (especially UNO and extension patterns), **where** it landed, and the **minimum tooling** needed to run the checker. Quick-reference annotation rules live in [§21 of `AGENTS.md`](../AGENTS.md#21-static-type-checking-ty).

---

## Outcome

| Stage | Notes |
|--------|--------|
| Initial | On the order of **1000+** diagnostics before scoping (including vendored `plugin/contrib` and noisy test-only code). |
| After narrowing | Excluding **`plugin/contrib`** and **`plugin/tests`** via `pyproject.toml` focused work on application code; one documented pass fixed on the order of **~141** categorized issues in that scope. |
| Final | **`ty check`** reports **no errors** for the configured include set (`make ty` / `make check`). |

Static checking does **not** prove LibreOffice runtime behavior: UNO remains highly dynamic. The goal is consistent annotations, usable stubs, and fewer accidental mistakes in Python code.

---

## Tooling (short)

- **`pyproject.toml`** — `[tool.ty.src]`: `include = ["plugin"]`, `exclude = ["plugin/contrib", "plugin/tests"]`.
- **`Makefile`** — `make ty`: ensures `import uno` (via `make fix-uno` if needed), then `python -m ty check --exclude plugin/contrib/`.
- **Dev dependency**: **`types-unopy`** (LibreOffice API stubs). **`make fix-uno`** links system UNO into `.venv` so `uno` and `com.sun.star` resolve; without that, the checker cannot see extension types.

---

## UNO and extension-heavy patterns (what actually changed)

These are the recurring themes that dominated the cleanup, beyond “add `str | None` everywhere.”

### 1. `com.sun.star` imports and optional UNO

Many modules import constants from `com.sun.star.*`. Stubs or resolution can fail; some code paths must run **without** LibreOffice (tests, analysis). The pattern is: **try real imports**, else **`cast(Any, …)`** integer stand-ins so the rest of the module still type-checks.

See [`plugin/modules/calc/error_detector.py`](../plugin/modules/calc/error_detector.py) (and similarly analyzer/inspector): `CellContentType`, `FormulaResult`, and a fallback branch with `cast(Any, 0)` … `cast(Any, 4)`.

Some imports stay as `# type: ignore[unresolved-import]` where the checker still cannot resolve a particular `com.sun.star` module path.

### 2. Structs, `Any`, and callbacks

`uno.createUnoStruct("com.sun.star.beans.PropertyValue")` and similar return values that stubs treat loosely. The codebase uses **`cast(Any, …)`** where a struct is built and passed through (e.g. [`plugin/modules/writer/format_support.py`](../plugin/modules/writer/format_support.py)).

[`plugin/framework/queue_executor.py`](../plugin/framework/queue_executor.py) passes **`uno.Any("void", None)`** into UNO callbacks; that line is explicitly ignored where the stub contract does not match pyuno’s usage.

### 3. Listener / interface overrides: **parameter names matter**

`types-unopy` expects **the same parameter names as the `.pyi` stubs**. Implementations of `XActionListener`, `XEventListener`, etc. must use names like **`rEvent`** and **`Source`**, not arbitrary `ev` / `e`, or `ty` raises **`invalid-method-override`**.

Examples: [`plugin/framework/dialogs.py`](../plugin/framework/dialogs.py) (`TabListener`: `actionPerformed(self, rEvent)`, `disposing(self, Source)`), [`plugin/modules/chatbot/panel_resize.py`](../plugin/modules/chatbot/panel_resize.py) (`on_window_resized(self, rEvent)` and use of `rEvent.Source`).

### 4. `queryInterface` and dynamic objects

Runtime UNO uses **`queryInterface`** heavily; return types are often opaque. Class-based `queryInterface` can be unreliable under pyuno (see `AGENTS.md`); typing-wise, code may need **`# type: ignore[attr-defined]`** or narrow casts after a successful query. Draw/Writer code that obtains `XSelectionSupplier` and similar follows this pattern.

### 5. Mixins: **`Protocol` for the host**

`ToolCallingMixin` and send handlers are mixed into large panel classes. **`ToolLoopHost`** in [`plugin/modules/chatbot/tool_loop.py`](../plugin/modules/chatbot/tool_loop.py) and **`SendHandlerHost`** in [`plugin/modules/chatbot/send_handlers.py`](../plugin/modules/chatbot/send_handlers.py) declare the attributes and methods the mixin expects so `self` is checkable without circular imports.

### 6. `TYPE_CHECKING` imports

Heavy or circular imports (e.g. `LlmClient`, `ChatSession`) are imported under **`if TYPE_CHECKING:`** at the top of the mixin modules so runtime import order stays unchanged but static analysis sees the types.

### 7. Dynamic attributes on events / worker glue

When attaching extra fields to objects (e.g. approval flows on events), the code uses **`setattr` / `getattr`** so the analyzer does not treat unknown attributes as errors—see tool-loop paths that set things like `query_override` on events ([`plugin/modules/chatbot/tool_loop.py`](../plugin/modules/chatbot/tool_loop.py)).

### 8. Context and services

[`plugin/framework/i18n.py`](../plugin/framework/i18n.py) uses **`cast(Any, ctx).getServiceManager()`** (or similar) because the UNO context type surface does not always expose what we need cleanly in stubs.

### 9. Targeted `# type: ignore` codes

Prefer **specific** ignore codes (`attr-defined`, `override`, `unresolved-import`, …) over blanket ignores. Reserve them for **pyuno/UNO boundaries**, third-party quirks, or legacy hotspots—not for silencing ordinary Python mistakes.

---

## Other recurring fixes (non-UNO)

- **Explicit generics**: `list[str]`, `dict[str, Any]`, `str | None` instead of untyped collections.
- **Narrowing**: `if x is not None` before use; avoid forcing the checker to assume values are defined.
- **`cast(Iterable, …)`** for generators that `ty` does not infer as iterable (see §21).
- **Registry / service construction**: dynamic class registration may need small ignores where instantiation is reflection-like ([`plugin/framework/service_registry.py`](../plugin/framework/service_registry.py)).

---

## Diagnostic breakdown (one historical pass)
---

## Files touched (representative list from the cleanup)

Roughly **40+** files were edited; groupings below match the original tracking notes.

**Framework**

- [`plugin/framework/errors.py`](../plugin/framework/errors.py), [`image_utils.py`](../plugin/framework/image_utils.py), [`legacy_ui.py`](../plugin/framework/legacy_ui.py), [`logging.py`](../plugin/framework/logging.py), [`service_registry.py`](../plugin/framework/service_registry.py), [`settings_dialog.py`](../plugin/framework/settings_dialog.py), [`smol_model.py`](../plugin/framework/smol_model.py), [`state.py`](../plugin/framework/state.py), [`tool_registry.py`](../plugin/framework/tool_registry.py)

**Entry / backends**

- [`plugin/main.py`](../plugin/main.py), [`plugin/modules/agent_backend/builtin.py`](../plugin/modules/agent_backend/builtin.py)

**Calc**

- [`plugin/modules/calc/analyzer.py`](../plugin/modules/calc/analyzer.py), [`error_detector.py`](../plugin/modules/calc/error_detector.py), [`formulas.py`](../plugin/modules/calc/formulas.py), [`inspector.py`](../plugin/modules/calc/inspector.py), [`legacy.py`](../plugin/modules/calc/legacy.py), [`manipulator.py`](../plugin/modules/calc/manipulator.py)

**Chatbot / sidebar**

- Panel, factory, wiring, resize, state machine, send handlers, tool loop, web research, history, audio paths, etc. under [`plugin/modules/chatbot/`](../plugin/modules/chatbot/)

**Writer / HTTP / infra**

- Writer tools and format paths; HTTP client/errors; plus build/docs updates (`Makefile`, `AGENTS.md`, locales where relevant).

---

## Code examples (patterns from the old notes)

**Narrow ignores at UNO boundaries**

```python
obj.method_call()  # type: ignore[attr-defined]
```

**Explicit annotations where the body is still dynamic**

```python
def process_data(data: Any) -> Any:
    return data.process()  # type: ignore[no-any-return]
```

**Unions and optional values**

```python
variable: str | int | None = get_value()
if obj is not None:
    obj.method()
```

**Override compatibility with stubs**

```python
def actionPerformed(self, rEvent: ActionEvent) -> None:  # type: ignore[override]
    ...
```

(Prefer matching stub **parameter names** exactly so `ignore[override]` is unnecessary when possible.)

---

## Lessons learned

1. **Incremental fixes** (small batches + `ty check`) beat large single dumps.
2. **Many errors share one pattern** (especially overrides and `com.sun.star` imports).
3. **UNO needs explicit boundaries**: ignores and casts at pyuno edges, not scattered through pure Python logic.
4. **Keep stub names** for listeners/interfaces aligned with `types-unopy`.

---

## What developers should run

1. **`make fix-uno`** when `import uno` fails in the venv.
2. **`make ty`** or **`make check`** before substantive merges.
3. When adding features, follow §21 in `AGENTS.md` and the UNO patterns above.


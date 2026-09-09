# Native UNO test lifecycle (Draw flakes / URP `DisposedException`)

**Not a product fix.** This page is the diagnostic contract for intermittent
`DisposedException` on `desktop.loadComponentFromURL` in the native runner
(`plugin/testing_runner.py`, `make test-uno`). Do not treat a green soak as
proof that LibreOffice or WriterAgent is healthy.

Related: [archive/test_architecture_analysis.md](../archive/test_architecture_analysis.md)
(TEST start/end lines, Darwin URP abort, keeper document).

## What the fixture actually does

| Path | Reuse? | Open | Close |
|------|--------|------|-------|
| Calc `@with_native_doc` | Yes (wipe-and-reuse pool) | Factory only on first use / dead pool | Close only if reset fails |
| Writer `@with_native_doc` | No (unless `reuse=True`) | Factory each test | `close_doc` (`gc.collect` then `close`) |
| Draw / Impress | **Never** | Factory each test (`private:factory/sdraw`) | Always `close_doc` |

`create_native_doc` is a thin `loadComponentFromURL`. Draw tests do **not**
share a pooled document. A keeper hidden Writer is opened once in
`run_all_tests` so Windows bootstraps do not shut down when a suite closes
its last hidden Draw doc.

`_ensure_live_ctx` only runs **between suites**, and only if
`getServiceManager()` already fails. Inside a suite, the next
`@with_native_doc` open is the first place a dead bridge is noticed.

`close_doc` still swallows most errors (a failed close must not hide the
test body). Dispose during close is now **logged** (`LIFECYCLE close_doc dispose`).
After a non-pooled close, the harness probes `desktop.getComponents()` and
prints `LIFECYCLE office dead after close` if URP is already gone.

**Harness-only attribution (not a product fix):** if a test body returns OK
but the office already aborted, the runner fails *that* test instead of
letting the next factory open be the named victim:

- `Unspecified Application Error` on office/Python stderr (VCL `SalAbort`)
- harness soffice `Popen.poll()` already exited
- `getServiceManager` disposed (`LIFECYCLE office dead after TEST returned`)

`create_native_doc` probes before load (`pre_open=disposed` skips the load
and still raises a URP-shaped error). No office auto-restart. No skip/xfail.

Headless/user-profile bootstrap now `PIPE`s soffice **stderr** and drains it
on a dedicated thread so the SalAbort line is not only inherited onto the
terminal. `TEST end … OK` also prints `exit=` (`-` while the child lives).

## Findings: Unspecified Application Error

QA soak (`make test-uno-soak PAIR=dup-move REPEAT=20`): mid
`test_duplicate_slide_copies_shapes` stderr prints `Unspecified Application
Error`, the test still returns OK, then `test_duplicate_rename_move_slide`
fails `Binary URP bridge already disposed` (pids gone). `PAIR=tree-math`:
same Error during `test_get_draw_tree_marks_blank_and_label_hint` (OK), then
the next soak iter dies at `_ensure_live_ctx`.

**This is not a Draw assertion flake.** Python finished the killer; soffice
did not.

The exact string is **not** a WriterAgent message. LibreOffice VCL
`SalAbort` (`vcl/source/app/salplug.cxx`) prints it when the abort text is
empty, then `abort()` or `_exit(1)`:

```
if (rErrorText.isEmpty())
    std::fprintf(stderr, "Unspecified Application Error\n");
```

So the Error **is** office death (empty-text SalAbort).

### gdb catch (box QA on this branch)

Attached gdb to soak `soffice.bin` during solo
`FILTER=test_duplicate_slide_copies_shapes`. Faulting `cppu_threadpool`
thread:

`Application::Abort` ← signal handler ← `SfxItemSet::ClearSingleItem_PrepareRemove`
← `ClearAllItemsImpl` / `~SfxItemSet` ← `~SdrObject` ← `~SdrRectObj` ←
`~SvxShape` ← `OWeakAggObject::release` ← URP / `uno_Environment_invoke`.

**Reading:** SalAbort during **SvxShape / SdrRectObj destruction** while
clearing an `SfxItemSet` on a URP release thread after close — same general
family as the historical octagon `SfxItemPool::unregisterNameOrIndex` abort
on rect teardown. Exact LO invariant still needs dbgsyms / source mapping;
product fixes are parked until Chief/Keith pick next steps.

Full write-up: [salabort-svxshape-close.md](salabort-svxshape-close.md).
`#687`'s post-OK `getServiceManager` probe can miss the race: SalAbort can
print while URP still answers, then the process exits before the next open.

### Ranked hypotheses

1. **VCL SalAbort during Draw UNO or `close_doc`, URP lags** (best fit).
   Confirm: fail-closed names the killer; `soffice_exit=` is `1`; stderr
   tail has `terminate called after…` or a real abort text; pids gone at
   that TEST end.
2. **`XDrawPageDuplicator.duplicate` (`doc.duplicate`) headless crash**
   (`PAIR=dup-move` body). Confirm: isolate `duplicate_slide` only; Error
   during the tool call vs during teardown; `activate=False` vs `True`.
   Does **not** explain the blank/label killer.
3. **Draw `TextShape` create / empty `getString` / `get_draw_tree` property
   walk** (`test_get_draw_tree_marks_blank_and_label_hint`). Confirm: soak
   that test alone; Error during `shape_upsert` vs `get_draw_tree` vs close.
4. **`--pair tree-math` prefix bleed** (harness fact, now fixed). Filter
   `test_get_draw_tree` also matched `test_get_draw_tree_marks_blank_and_label_hint`.
   QA’s tree-math Error on the blank test may be that extra test, not
   `test_get_draw_tree` → math OLE. `--pair` is now exact; `FILTER=` still
   prefix-matches.
5. **`close_doc` / `gc.collect` + Draw model teardown** (shared by both
   killers: factory `sdraw` + always-close). Confirm: Error after body
   return / `LIFECYCLE close_doc` vs during the tool call.
6. **Use-after-close or stale page/shape proxy** (weaker). Confirm: Error
   only when the body still holds `page.getByIndex` / `getString` across
   duplicate; not when the body is a no-op close.
7. **Headless VCL / hidden controller (`setCurrentPage`)** (weaker; would
   be more deterministic). Confirm: `--visible` soak vs headless.
8. **Heap corruption / delayed abort** (historical Arch glibc
   `test_get_draw_tree` → math). Confirm: malloc/`terminate` line before
   SalAbort; Arch-only. Do not require Arch to hunt this.

What the two killer tests do (no product change):

- `test_duplicate_slide_copies_shapes`: `shape_upsert` rectangle + text,
  `duplicate_slide(page=0, activate=False)` → `DrawBridge.duplicate_slide`
  → `self.doc.duplicate(source)`, then `getString` on the copy.
- `test_duplicate_rename_move_slide` (usual victim): `duplicate_slide`
  (activate default True), `rename_slide`, `move_slide` (`remove` +
  `insertByIndex`).
- `test_get_draw_tree_marks_blank_and_label_hint`: two `TextShape`s
  (label + empty named blank), `get_draw_tree` → `build_shape_tree`
  (`getString`, geometry, `FillColor` / `CustomShapeGeometry`).

## What the breadcrumb prints

On every native **FAIL**, stderr `TEST end … FAIL` includes:

```
previous=<suite.test> result=OK|FAIL|SKIP|- end_pids=<soffice at that end>
last_ok=<last successful TEST> dt_ms=<ms from that end to this start>
current=<victim> start_pids=… now_pids=… pids_changed=0|1
bridge=alive|disposed|no_probe|error:…
```

`bridge=` is `ctx.getServiceManager()` at **TEST start** (same check as
`_ensure_live_ctx`). Factory-open failures also include `pre_open=` from a
probe immediately before `loadComponentFromURL`:

- `pre_open=disposed` — office was already dead; the previous TEST end is the
  killer (hypothesis confirmed for that fail).
- `pre_open=alive` then dispose on load — died *during* this open (less like
  “previous close toasted the bridge”).

A URP dispose also prints `LIFECYCLE URP dispose at <victim> previous=…`.
SalAbort / child exit after an OK body prints
`LIFECYCLE application error after TEST returned` (or
`office death before TEST call` for the gap). That is harness attribution,
not a product retry.

Grep: `LIFECYCLE`, `previous=`, `Unspecified Application Error`, `soffice_exit=`.
The victim is `current=`; the likely killer is `previous=` / `last_ok=` when
`result=OK`.

Native tests do **not** run under pytest. `format_lifecycle_breadcrumb` /
`probe_uno_bridge` / `collect_post_test_death` in `plugin/testing_runner.py`
are the hook. Unit tests: `tests/framework/test_testing_runner.py`,
`tests/scripts/test_testing_runner_cli.py`, `tests/test_testing_utils.py`.

## Soak / reproduce (same soffice, no new framework)

Tight loop in **one** office process (this is the lifecycle under test):

```bash
# Full Draw UNO suite, 20 rounds (default)
make test-uno-soak

# More rounds
make test-uno-soak REPEAT=50

# Historical pair (tree → math OLE factory open). Exact names only.
make test-uno-soak PAIR=tree-math REPEAT=50

# CI victim + its predecessor in file order
make test-uno-soak PAIR=dup-move REPEAT=50

# FILTER still prefix-matches: test_get_draw_tree also selects
# test_get_draw_tree_marks_blank_and_label_hint. Prefer PAIR= for isolation.
make test-uno-soak FILTER="test_get_draw_tree test_insert_math_draw" REPEAT=50
```

Equivalent without the Make target:

```bash
WRITERAGENT_UNO_SOAK=20 make test-uno FILTER=test_draw_uno
python -m plugin.testing_runner --repeat 20 test_draw_uno
python -m plugin.testing_runner --repeat 50 --pair tree-math
```

Look for `SOAK iter i/N`, then the first `LIFECYCLE` / `previous=` /
`application error` on FAIL. Outer `for i in …; do make test-uno …; done`
restarts soffice each time and is a **weaker** repro for “bridge died
between two tests.”

`test-uno-soak` is not in default CI. Invoke it from a CI note or a
workflow_dispatch job when hunting this flake.

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

**Harness-only attribution (same PR, not a product fix):** if a test body
returns OK but `getServiceManager` is already disposed, the runner fails
*that* test (`LIFECYCLE office dead after TEST returned`) instead of letting
the next factory open be the named victim. `create_native_doc` probes before
`loadComponentFromURL` (`pre_open=disposed` skips the load and still raises
a URP-shaped error). No office auto-restart. No skip/xfail.

## Hypothesis (unproven)

CI flake on `test_duplicate_rename_move_slide` (Draw UNO, PR #685 victim):
failure at `create_native_doc` / `loadComponentFromURL` with URP
`DisposedException`. That pattern matches **“previous test toasted soffice /
the bridge; this open is the named victim”** more than a bug inside
duplicate/rename/move.

Historical Arch glibc double-free: `test_get_draw_tree` still printed OK,
then `test_insert_math_draw` died on the next factory load. Same class of
gap: TEST end OK does not prove the office survived teardown.

Math OLE (`insert_math` → `OLE2Shape` + Math CLSID) is a plausible *stressor*
for that second pair. It does **not** explain a flake whose victim is
`test_duplicate_rename_move_slide` (earlier in the file, before math).
No skip/xfail and no office auto-restart: those would hide the killer.

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
If a test body + `@with_native_doc` teardown **returns OK** but
`getServiceManager` is already disposed, the runner **fails that test**
(`LIFECYCLE office dead after TEST returned`) so the killer is named instead
of the next open. That is harness attribution, not a product retry.

Grep: `LIFECYCLE` and `previous=`. The victim is `current=`; the likely
killer is `previous=` / `last_ok=` when `result=OK`.

Native tests do **not** run under pytest. `format_lifecycle_breadcrumb` /
`probe_uno_bridge` in `plugin/testing_runner.py` are the hook. Unit tests:
`tests/framework/test_testing_runner.py`, `tests/scripts/test_testing_runner_cli.py`,
`tests/test_testing_utils.py`.

## Soak / reproduce (same soffice, no new framework)

Tight loop in **one** office process (this is the lifecycle under test):

```bash
# Full Draw UNO suite, 20 rounds (default)
make test-uno-soak

# More rounds
make test-uno-soak REPEAT=50

# Historical pair (tree → math OLE factory open)
make test-uno-soak PAIR=tree-math REPEAT=50

# CI victim + its predecessor in file order
make test-uno-soak PAIR=dup-move REPEAT=50

# Same pairs without the alias
make test-uno-soak FILTER="test_get_draw_tree test_insert_math_draw" REPEAT=50
```

Equivalent without the Make target:

```bash
WRITERAGENT_UNO_SOAK=20 make test-uno FILTER=test_draw_uno
python -m plugin.testing_runner --repeat 20 test_draw_uno
python -m plugin.testing_runner --repeat 50 --pair tree-math
```

Look for `SOAK iter i/N`, then the first `LIFECYCLE` / `previous=` on FAIL.
Outer `for i in …; do make test-uno …; done` restarts soffice each time and
is a **weaker** repro for “bridge died between two tests.”

`test-uno-soak` is not in default CI. Invoke it from a CI note or a
workflow_dispatch job when hunting this flake.

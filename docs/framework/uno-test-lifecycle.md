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
prints `LIFECYCLE office dead after close` if URP is already gone. That is
instrumentation, not a retry.

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
current=<victim> start_pids=<soffice at TEST start> now_pids=<soffice now>
```

A URP dispose also prints a dedicated line:

```
LIFECYCLE URP dispose at <victim> previous=… result=… …
```

Factory open maps the same trail onto the exception message
(`LIFECYCLE native_doc open FAIL` + `Binary URP bridge disposed during call`
so the runner still aborts remaining suites).

Grep: `LIFECYCLE` and `previous=`. The victim is `current=`; the likely
killer is `previous=` (last successful TEST end when `result=OK`).

Native tests do **not** run under pytest. There is no pytest hook for this
trail; `record_test_start` / `record_test_end` / `format_lifecycle_breadcrumb`
in `plugin/testing_runner.py` are the hook. Unit tests live in
`tests/scripts/test_testing_runner_cli.py` and `tests/test_testing_utils.py`.

## Soak / reproduce (same soffice, no new framework)

Tight loop in **one** office process (this is the lifecycle under test):

```bash
# Full Draw UNO suite, 20 rounds (default)
make test-uno-soak

# More rounds
make test-uno-soak REPEAT=50

# Historical pair (tree → math OLE factory open)
make test-uno-soak FILTER="test_get_draw_tree test_insert_math_draw" REPEAT=50

# CI victim + its predecessor in file order
make test-uno-soak FILTER="test_duplicate_slide_copies_shapes test_duplicate_rename_move_slide" REPEAT=50
```

Equivalent without the Make target:

```bash
# env form
WRITERAGENT_UNO_SOAK=20 make test-uno FILTER=test_draw_uno

# runner CLI (LibreOffice Python)
python -m plugin.testing_runner --repeat 20 test_draw_uno
```

Look for `SOAK iter i/N`, then the first `LIFECYCLE` / `previous=` on FAIL.
Outer `for i in …; do make test-uno …; done` restarts soffice each time and
is a **weaker** repro for “bridge died between two tests.”

`test-uno-soak` is not in default CI. Invoke it from a CI note or a
workflow_dispatch job when hunting this flake.

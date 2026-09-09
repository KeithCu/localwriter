# SalAbort during SvxShape / SdrRectObj teardown (gdb)

**Not a product fix.** Box QA catch on PR `#694` branch
(`cursor/uno-application-error-diag-6477`), 2026-09-08 evening (America/Detroit).
Raw dump: captured as `/workspace/draw-urp-soak/gdb/native-stack.txt` on the QA box
(not committed). Summary for morning review.

## Catch

| Item | Value |
|------|--------|
| LO | 25.2.3.2 520(Build:2) |
| Method | Attach `gdb -p` to soak `soffice.bin` after `connected=True`; break `Application::Abort` |
| Trigger soak | `make test-uno-soak FILTER="test_duplicate_slide_copies_shapes" REPEAT=40` |
| When | After TEST returned OK → stderr `Unspecified Application Error` → `soffice_exit=134` |
| Symbols | Partial dynamic only (no `libreoffice-*-dbgsym` in apt on the box) |

## Faulting thread (`cppu_threadpool`)

SEGV (or equivalent) during Draw shape teardown → signal handler → empty-text
`Application::Abort` → VCL `SalAbort` prints **Unspecified Application Error**
→ `abort()` (soak uses `--norestore`).

```
#0  Application::Abort(rtl::OUString const&)     libmergedlo.so
#1  ??                                           libmergedlo.so
#2  ??                                           libmergedlo.so
#3  ??                                           libuno_sal.so.3
#4  <signal handler called>
#5  ??                                           libmergedlo.so
#6  SfxItemSet::ClearSingleItem_PrepareRemove(SfxPoolItem const*)
#7  SfxItemSet::ClearAllItemsImpl()
#8  SfxItemSet::~SfxItemSet()
#9–10 ??                                         libmergedlo.so
#11 SdrObject::~SdrObject()
#12 SdrRectObj::~SdrRectObj()
#13 SvxShape::~SvxShape()
#14 ??                                           libmergedlo.so
#15 cppu::OWeakAggObject::release()
… uno_Environment_invoke / binaryurp / cppu_threadpool
```

Main thread was idle in `Application::Execute` / `ImplSVMain`.

## Reading

1. The stderr string is VCL `SalAbort` with **empty** abort text (see
   `uno-test-lifecycle.md`) — office is dying, not a WriterAgent log line.
2. Death is on a **URP / cppu_threadpool** thread releasing an `SvxShape` that
   wraps an `SdrRectObj`, while clearing an `SfxItemSet` (item pool).
3. Fits the QA timeline: Python `doc.close(True)` **returns**, then async
   shape/model teardown aborts soffice; the next open sees
   `Binary URP bridge already disposed`.
4. **Kinship with the octagon Draw abort:** same general family —
   `SfxItemPool` / item-set destruction while destroying a rect/shape
   (`SfxItemPool::unregisterNameOrIndex` on octagon vs
   `SfxItemSet::ClearSingleItem_PrepareRemove` here). Not proven identical
   root cause without dbgsyms / LO source line mapping.
5. Hottest harness repro remains solo
   `test_duplicate_slide_copies_shapes` (rectangle + text then
   `duplicate_slide`). Blank/label TextShape soak also fires SalAbort at a
   lower rate — not exclusive to `duplicate_slide`, but that path is hottest.

## Morning next steps (parked until Chief/Keith pick)

- Optional: install LO dbgsyms and re-catch for resolved `??` frames.
- Product / harness hardening (e.g. `close_doc` drain, shape-proxy release
  order) — **do not start** until explicitly asked after reviewing this stack.

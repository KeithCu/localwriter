# SalAbort during SvxShape / SdrRectObj teardown (gdb)

**Not a product fix.** Box QA catch on PR `#694` branch
(`cursor/uno-application-error-diag-6477`), 2026-09-08 evening (America/Detroit).
Raw dump: `/workspace/draw-urp-soak/gdb/native-stack.txt` on the QA box (not committed).
dbgsym resolve: `/workspace/draw-urp-soak/gdb-dbgsym/STACK-DBGSYM.md` (local).

## Catch

| Item | Value |
|------|--------|
| LO | 25.2.3.2 520(Build:2) (`libreoffice-core` 4:25.2.3-2+deb13u6) |
| Method | Attach `gdb -p` after `connected=True`; break `Application::Abort` |
| Trigger soak | `make test-uno-soak FILTER="test_duplicate_slide_copies_shapes" REPEAT=40` |
| When | After TEST returned OK → stderr `Unspecified Application Error` → `soffice_exit=134` |
| First catch symbols | Partial dynamic only |
| Follow-up | Installed Debian `trixie-debug` `libreoffice-*-dbgsym`; offline `addr2line` on the saved stack (live gdb+DWARF freezes the soak) |

## Faulting thread (`cppu_threadpool`) — resolved with dbgsyms

SEGV during Draw shape teardown → VCL signal hook → empty-text
`Application::Abort` → VCL `SalAbort` prints **Unspecified Application Error**
→ `abort()` (soak uses `--norestore`).

```
#0  Application::Abort(rtl::OUString const&)
#1  desktop::Desktop::Exception(ExceptionCategory)
#2  VCLExceptionSignal_impl(void*, oslSignalInfo*)
#3  (SAL signal trampoline)
#4  <signal handler called>
#5  SfxItemPool::unregisterNameOrIndex(SfxPoolItem const&) [clone .cold]   ← SEGV site
#6  SfxItemSet::ClearSingleItem_PrepareRemove(SfxPoolItem const*)
#7  SfxItemSet::ClearAllItemsImpl()
#8  SfxItemSet::~SfxItemSet()
#9  sdr::properties::AttributeProperties::~AttributeProperties()
#10 sdr::properties::RectangleProperties::~RectangleProperties()
#11 SdrObject::~SdrObject()
#12 SdrRectObj::~SdrRectObj()
#13 SvxShape::~SvxShape()
#14 SvxShapeRect::~SvxShapeRect()
#15 cppu::OWeakAggObject::release()
… uno_Environment_invoke / binaryurp / cppu_threadpool
```

Main thread was idle in `Application::Execute` / `ImplSVMain`.

Debian LO dbgsyms give solid **function** names; `file:line` is mostly unavailable (LTO).

## Reading

1. The stderr string is VCL `SalAbort` with **empty** abort text (see
   `uno-test-lifecycle.md`) — office is dying, not a WriterAgent log line.
2. Death is on a **URP / cppu_threadpool** thread releasing an **`SvxShapeRect`**
   (rectangle shape UNO wrapper → `SdrRectObj`), while clearing the shape's
   `SfxItemSet` / item pool.
3. The faulting frame is **`SfxItemPool::unregisterNameOrIndex` (.cold)** —
   same family as the historical octagon Draw abort (previously only
   hypothesized for this path).
4. Fits the QA timeline: Python `doc.close(True)` **returns**, then async
   shape/model teardown aborts soffice; the next open sees
   `Binary URP bridge already disposed`.
5. Hottest harness repro remains solo
   `test_duplicate_slide_copies_shapes` (rectangle + text then
   `duplicate_slide`). Blank/label TextShape soak also fires SalAbort at a
   lower rate — not exclusive to `duplicate_slide`, but that path is hottest.

## dbgsyms on Debian trixie (box note)

`main` alone has no `*-dbgsym`. Add:

```
Types: deb
URIs: http://deb.debian.org/debian-debug
Suites: trixie-debug
Components: main
```

then `apt-get install libreoffice-core-dbgsym libreoffice-draw-dbgsym ure-dbgsym uno-libs-private-dbgsym`
(~588 MB). Prefer offline `addr2line` against the `.build-id` debug file rather
than attaching gdb with full DWARF during a soak.

## Morning next steps (parked until Chief/Keith pick)

- Product / harness hardening (e.g. `close_doc` drain, shape-proxy release
  order) — **do not start** until explicitly asked after reviewing this stack.

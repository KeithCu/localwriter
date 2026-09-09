# Notes — Long Writer pack (native)

Purpose: **harness debug** for **one** long Writer document that needs a
table of contents, named heading styles, and review comments together.
Eval-2 is not a multi-model benchmark yet.

This sibling is **WriterAgent-native**. There is no HF gold tree and no
`prompt.gdpval.txt`. See [`SOURCE.md`](SOURCE.md) for the gold-subset
scan that did not yield a clean TOC + styles + comments pack.

## How it differs from existing siblings

| Sibling | Why it is not this slot |
|---------|-------------------------|
| Tenant / Cadaver | Short memo / mini proposal; no TOC + comments pack |
| GMP | Form + memo pair; compliance packet |
| Slot 7 | Headed **template** fidelity (PARKED); not a long pack |

One open Writer document. No peer required for v1.

## WriterAgent prompt

The user message is [`prompt.writeragent.txt`](prompt.writeragent.txt).
It remaps “attach a new Word file” to this open document and names the
two staged research titles. It does **not** name product internals.

## Oracle v1

Soft fail-closed checks live in [`rubric.eval2.md`](rubric.eval2.md):
pack present, fixture identity, TOC field **or** a Contents index at
the start, at least three named heading styles (not bold Default), at
least one non-empty review comment, husk ban. Exact heading wording
and comment authors are **soft / later**. Do not fail on Word vs ODT.

## Not changed

- Slot 7 (`writer-headed-template/`) stays **PARKED**
- Slots 5 / 6 / 8 / 9 stay stubs
- `docs/eval/gdpval/` — no new tree (none fit; add-only if one had)

# Notes — Calc-primary model (not sampling)

Purpose: **harness debug** stub for a Calc-primary workbook whose
**formulas must be right**. Miss modes should differ from AFC: wrong
factor, pinned formula, empty `create_sheet` — not sample-flag / SSC
math.

Eval-2 is not a multi-model benchmark yet. This folder is a **stub**, not a
headed-ready gold.

## How it differs from existing siblings

| Sibling | Why it is not this slot |
|---------|-------------------------|
| AFC | Sampling / variance / flags. Same miss class we already score. |
| Cadaver | Writer proposal; budget is research-only (no model write). |
| Tenant / GMP | Writer-primary (GMP adds a Draw form). |

Forecast, allocation, branch profitability, or collective-bargaining
compensation models belong here. One open Calc workbook is enough for v1.
No Writer peer required.

## Miss modes to keep distinct from AFC

1. **Wrong factor** — rate / weight / WACC-like input applied to the
   wrong column or period.
2. **Pinned formula** — one formula string stamped down a column with
   no relative adjust (same actuation bug AFC saw, new claim).
3. **Empty create_sheet** — a new tab exists and looks like the
   deliverable; no schedules populated.

Soft oracles later. Do **not** put those tool names or “don’t invent
rates” into the product prompt.

## Not ready

No in-repo gold package, no fixtures, no headed `--task`, no oracle CLI.
See [`SOURCE.md`](SOURCE.md).

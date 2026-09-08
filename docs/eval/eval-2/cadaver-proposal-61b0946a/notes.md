# Notes — what changed vs gold

Purpose: **harness debug** for a Writer-primary GDPval sibling. AFC
(`afc-sample-83d10b06`) is Calc / in-workbook. Tenant Retention is a
Writer memo plus two refs. This task is a mini proposal in the **open**
Writer document; the budget workbook is research-only. Eval-2 is not a
multi-model benchmark yet (that comes when ~10 siblings exist).

Intentional delta vs [`prompt.gdpval.txt`](prompt.gdpval.txt) (byte-identical
to gold `prompt.txt`):

1. `aggregate the findings into a word document, save as "Collaborative Cadaver Program Proposal", and attach.` → `write the mini proposal in this open Writer document.` Gold assumes a new Microsoft Word file; the trial assumes a blank Writer doc is already open in the clean trial dir.
2. `use the department's "Cadaver Budget.xlsx" file attached` → `use the spreadsheet titled ‘Cadaver Budget’ in this folder` so the name matches the staged basename without pinning `.xlsx` vs `.ods`.

No smoother-path remaps. Required sections stay gold: introduction that
leads with cost savings (plus graph **or** a labeled 1–4 savings table),
ethical / anatomical assignment, and procedure-count ranges by
participation and complexity (no mixing). Do **not** add a one-liner that
says “don’t invent budget numbers” — v1 fail-closes on line-item names
and the locked constraint bands, not exact dollars.

## Oracle v1 (Eliyezer-locked)

Fail-closed checks live in [`rubric.eval2.md`](rubric.eval2.md). They
come from the gold rubric + budget line names, not a Tenant letter-shift.
Exact dollars, lab-fee share, per-dept ranges, and chart aesthetics are
**soft / later**. Do not fail on Word vs ODT. Do not edit the budget
(research-only). No dual deliverable.

ODT scoring reads `text:h` and `text:p` in document order so a headed
title still counts.

## Gold vs fixture (do not “fix” gold)

- Gold rubric mentions a **Costs** tab and “per-cadaver cost … category
  named Cadaver”. The HF sheet is **`Sheet1`**. Category `Cadaver` is
  rows 2–5 (cadaver $2,000 + shipping $112.50 + preservation $137.50 +
  cremation $750 = **$3,000 per cadaver**). Line `Annual Cadaver Lab Fee`
  is **$1,000** (D17). Supplies and Education are excluded.
- Expert gold proposal uses the **$3,000** bundle + $1,000 fee →
  **$13,000** baseline, hospital name **Silverview** (prompt is Hope
  Hospital), standard-only counts at **2 per cycle** (20–24) rather than
  the locked **20–36**, and says mixing is possible. Eval-2 scores the
  **saved trial proposal**, not that gold file. V1 does **not** fail-close
  on Hope Hospital or exact dollars.

## Not changed

- Introduction + cost-savings lead-in + two required sections
- Four departments: General Surgery, Thoracic Surgery, Otolaryngology,
  Orthopedic Surgery
- Include lab fee; exclude supplies and education
- Freeze/thaw 10–12, 3-hour thawed window, simple / standard / complex
- “Does not account for mixing complexity”
- Gold rubric, `task.json`, `meta.txt`, `prompt.gdpval.txt`, gold
  proposal bytes
- `docs/eval/gdpval/` contents (this PR only **adds** this task id)
- `prompt.writeragent.txt` (Eli reviews; deltas stay the two lines above)

Harness pass/fail for this variant is [`rubric.eval2.md`](rubric.eval2.md),
not a letter-shift of `rubric_pretty.txt`.

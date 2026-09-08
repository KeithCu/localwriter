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
leads with cost savings (plus graph + methodology), ethical / anatomical
assignment, and procedure-count ranges by participation and complexity
(no mixing). Do **not** add a one-liner that says “don’t invent budget
numbers” — the oracle fail-closes on fixture cells instead.

## Gold vs fixture (do not “fix” gold)

- Gold rubric mentions a **Costs** tab and “per-cadaver cost … category
  named Cadaver”. The HF sheet is **`Sheet1`**. Category `Cadaver` is
  rows 2–5 (cadaver $2,000 + shipping $112.50 + preservation $137.50 +
  cremation $750 = **$3,000 per cadaver**). Line `Annual Cadaver Lab Fee`
  is **$1,000** (D17). Supplies and Education are excluded.
- Expert gold proposal uses the **$3,000** bundle + $1,000 fee →
  **$13,000** baseline for 4 cadavers, hospital name **Silverview**
  (prompt is **Hope Hospital**), and standard-only counts at **2 per
  cycle** (20–24) rather than the rubric’s 2–3 → 20–36. Eval-2 scores
  the **saved trial proposal**, not that gold file. Fail-close on
  **Hope Hospital** and the fixture cells / gold-hard ranges
  (`$2,000` **or** `$3,000`, `$1,000`, 4 cadavers, 40–48 simple,
  10–12 cycles). Gold also omits the required “does not account for
  mixing complexity” disclaimer (it says mixing is possible). Wrong
  budget analysis = FAIL.

## Not changed

- Introduction + cost-savings graph request + two required sections
- Four departments: General Surgery, Thoracic Surgery, Otolaryngology,
  Orthopedic Surgery
- Include lab fee; exclude supplies and education
- Freeze/thaw 10–12, 3-hour thawed window, simple / standard / complex
- “Does not account for mixing complexity”
- Gold rubric, `task.json`, `meta.txt`, `prompt.gdpval.txt`, gold
  proposal bytes
- `docs/eval/gdpval/` contents (this PR only **adds** this task id)

Harness pass/fail for this variant is [`rubric.eval2.md`](rubric.eval2.md),
not a letter-shift of `rubric_pretty.txt`.

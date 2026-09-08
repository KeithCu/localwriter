# Notes — what changed vs gold

Purpose: **harness debug** for a Writer-primary GDPval sibling. AFC
(`afc-sample-83d10b06`) is Calc / in-workbook. This task is a 1–2 page
memo in the open Writer document. Eval-2 is not a multi-model benchmark
yet (that comes when ~10 siblings exist).

Intentional delta vs [`prompt.gdpval.txt`](prompt.gdpval.txt) (byte-identical
to gold `prompt.txt`):

1. `Prepare a "Tenant Retention Strategy" as a concise, 1-2 page business memo, in Microsoft Word.` → `…memo in this open Writer document.` Gold assumes a new Microsoft Word file; the trial assumes a blank Writer doc is already open in the clean trial dir.
2. `based on analysis of the provided reference files` → `based on analysis of the files in this folder` (same “already in session” shape as AFC’s attached → this spreadsheet).
3. `The Excel file attached ("Exit Survey Feedback.xlsx")` → `The spreadsheet titled ‘Exit Survey Feedback’` so the name matches the staged basename without pinning `.xlsx` vs `.ods`.
4. `You may reference the attached ("Current Renewal Letter.docx")` → `You may reference the Current Renewal Letter in this folder` (staged as `.odt`).

No smoother-path remaps. Survey comments and the letter’s 60-day /
one-size-fits-all wording stay as gold. Do **not** add a one-liner that
says “don’t invent survey stats” — the oracle fail-closes on the gold-hard
counts instead.

## Gold spelling

Gold deliverable basename is `Tenant Rentention Strategy.docx` (typo).
Gold tree and `gold/` keep that spelling. Eval-2 notes, the blank open
memo (`Tenant Retention Strategy.odt`), and the oracle use correct
spelling. **Do not fail the oracle on the gold typo.**

## Gold memo vs eval-2 oracle

Gold `rubric_pretty.txt` already requires Harborview Flats / Stamford,
+10% / 6 months, **9/20 (45%)** rent increase, **5/20 (25%)** lack of
community/disconnected, 90/60/M2M, 90/60/30 emails, and two events.
The expert gold memo states 45% / 25% but omits Stamford and the 9/20
and 5/20 counts. Eval-2 scores the **saved trial memo**, not that gold
file, and fail-closes on the counts (wrong analysis = FAIL).

## Not changed

- Four required sections and the 1–2 page memo length
- Early-bird 90d / standard 60d / month-to-month premium
- 90/60/30 communication touchpoints and two next-quarter events
- Permission to use web examples for events (oracle does not require cites)
- Gold rubric, `task.json`, `meta.txt`, `prompt.gdpval.txt`, gold memo bytes
- `docs/eval/gdpval/` contents (this PR only **adds** this task id)

Harness pass/fail for this variant is [`rubric.eval2.md`](rubric.eval2.md),
not a letter-shift of `rubric_pretty.txt`.

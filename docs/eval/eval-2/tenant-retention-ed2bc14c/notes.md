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

## Oracle format soften (headed-memo false-FAIL)

A real Gemini headed memo (~1476 words; Harborview/Stamford; +10%/6mo;
early-bird 90d / 60d / M2M; 90/60/30; two events; table cells `9` /
`45.0%` and `5` / `25.0%`; section titles in ODT `text:h`) false-failed
the v1 structural oracle on **format**, not substance. Soften (do **not**
weaken Harborview Flats, Stamford, 10% retention, 6 months, or the
husk/`Error:` ban; do **not** change `prompt.writeragent.txt`):

1. Extract walks `text:h` as well as `text:p` (heading titles were invisible).
2. Percents accept `45%` / `45.0%` / `45 percent` (same for 25).
3. Counts pass on literal `9/20` / `9 out of 20` / `9 of 20`, **or**
   digit `9` near the rent-increase theme plus survey N=`20` somewhere
   (same for community `5`).
4. Section titles allow a short synonym OR list (secondary; `text:h`
   extract is the main fix).
5. Word max is **1800** (min stays 180) so table-heavy 1–2 page memos pass.

If `runs/20260908-0121-gemini-3.8-flash-r200/final_memo.odt` is on disk,
re-score it after this soften — substance checks should **PASS** (or only
fail on a genuine content gap). That artifact is not committed here.

## Not changed

- Four required section themes (titles may be synonyms / `text:h`)
- Early-bird 90d / standard 60d / month-to-month premium
- 90/60/30 communication touchpoints and two next-quarter events
- Permission to use web examples for events (oracle does not require cites)
- Gold rubric, `task.json`, `meta.txt`, `prompt.gdpval.txt`, gold memo bytes
- Writer prompt (`prompt.writeragent.txt`)
- `docs/eval/gdpval/` contents (this PR only **adds** this task id)

Harness pass/fail for this variant is [`rubric.eval2.md`](rubric.eval2.md),
not a letter-shift of `rubric_pretty.txt`.

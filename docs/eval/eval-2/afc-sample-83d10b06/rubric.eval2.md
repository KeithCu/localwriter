# rubric.eval2 — fail-closed in-workbook oracle

Derived from the **Population fixture** plus **`prompt.writeragent.txt`**, not by
letter-shifting gold [`rubric_pretty.txt`](rubric_pretty.txt). Gold is a
separate `Sample` workbook (variance in I, flags in J, tab named
`Sample Size`). This variant scores sheets **in the open workbook**.

Leave [`docs/eval/gdpval/`](../../gdpval/) untouched.

## What is scored

The harness opens the saved trial artifact (`final_workbook.ods`, or `.xlsx`
if that is what was saved). **Chat Ready / STREAM_DONE is ignored.** An empty
Sample that ended Ready still fails.

| Check | Source | Fail closed |
|-------|--------|-------------|
| Sheets named `Sample` and `Sample Size Calculation` exist | Writer prompt step 4 (case-insensitive, surrounding spaces ignored) | Missing either sheet |
| Sample data rows > 0 | Fixture is a header + data table | Header-only / blank Sample |
| S = count of flag=`1` on Sample ≥ R, and R ≥ 1 | Writer prompt: flags in **column K**. R is the integer the **Sample Size Calculation** tab reports (`Sample size`, `R`, or `R = N`) — same in-workbook source as the gold rubric, not a recomputed Cochran/FPC | Unparseable or `R < 1` (muse-style FPC→0); `S < R` |
| Ban dominant husks in Sample data cells | Observed residue on Ready-empty trials | ≥ 50% of non-empty Sample data cells match `#DIV/0!`, `Err:507`, `Error:`, `_deal_*` / `DEAL_*`, or `PYTHONFUNCTION`-shaped text |

`__Anonymous_Sheet_DB__*` is a conversion artifact, not a deliverable sheet.

## Column assumptions (minimal, fixture-aligned)

The Population fixture is A–H (`G` = Q3 2024 KRI, `H` = Q2 2024 KRI). This
oracle does **not** check variance math in J (prompt §2.6 / fill-down are
out of scope). It only needs K to count flags.

## What this is not

- Not a full gold-rubric grader (entity coverage, 90%/10% prose, formatting).
- Not a product Ready predicate and not a repeated-error brake.
- Not a reason to raise `chatbot.max_tool_rounds` (headed helper stays at 50
  for live trials only).

CLI: `scripts/eval_2_ods_oracle.py` or `scripts/eval_2_headed.py --score`.

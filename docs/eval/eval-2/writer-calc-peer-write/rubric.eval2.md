# rubric.eval2 — soft Writer + Calc peer-write outline (stub)

Not a headed oracle. Derive the later CLI from **fixture + Writer prompt**,
not by letter-shifting a gold `rubric_pretty.txt`. Leave
[`docs/eval/gdpval/`](../../gdpval/) untouched until a new gold id is added.

## Criteria themes (not brittle regex)

| Theme | Pass idea | Fail closed |
|-------|-----------|-------------|
| Pair present | Saved Writer body + Calc workbook both non-empty | Missing either file; Ready-only husk |
| Calc was written | Workbook cells / sheets changed vs the staged start | Research-only; source tabs copied unchanged |
| Writer cites the workbook | Memo / email names the budget or transaction workbook | Writer-only prose with no workbook cite |
| Identity anchors | Occupies the gold names once materials land (program, account, period) | Invented entities that contradict the fixture |
| Two-turn peer | Calc write happened on the open workbook, not a new untitled file | Spawned a third workbook as the “deliverable” |
| Husk ban | No dominant `Error:` / `#DIV/0!` residue | Body or cells are husks |

Soft / later: exact gold dollars, email microcopy, sheet tab cosmetics,
Word vs ODT vs ODS.

## Non-goals (v1 stub)

- A `--score` CLI or a product Ready predicate.
- Inventing helper `--task` flags.
- Scoring AFC sampling flags or GMP form `fld_*` boxes.

# rubric.eval2 — soft Calc-primary model outline (stub)

Not a headed oracle. Derive later checks from **fixture + Writer prompt**.
Do not letter-shift AFC `rubric.eval2.md` (no Sample / SSC / column K).

## Criteria themes (not brittle regex)

| Theme | Pass idea | Fail closed |
|-------|-----------|-------------|
| Workbook present | Saved ODS/XLSX opens; at least one populated schedule sheet | Missing file; header-only / blank tabs |
| Formulas exist | Amount columns use formulas (relative refs), not a pasted constant column | All values hardcoded with no formula trail |
| Factor / rate | Named rate or factor from the fixture is applied on the right series | Wrong factor, wrong column, wrong period |
| Fill vs pin | Relative refs adjust down the column | Identical formula text on every row |
| Create ≠ populate | If a new sheet is required, it has rows | Empty `create_sheet` tab as the “model” |
| Husk ban | No dominant `Error:` / `#DIV/0!` residue | Ready-empty husk |

Soft / later: dropdown cosmetics, exact gold NPV, chart styling.

## Non-goals

- AFC sampling / flag-count oracles.
- A `--score` CLI in this stub.

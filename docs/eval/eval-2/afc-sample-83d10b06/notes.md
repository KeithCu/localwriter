# Notes — what changed vs gold

Intentional delta vs [`prompt.gdpval.txt`](prompt.gdpval.txt) (byte-identical to gold `prompt.txt`):

1. `The attached spreadsheet titled ‘Population’` → `This spreadsheet titled ‘Population’` so the trial assumes the Population workbook is already open in Calc.
2. Step 4 only: instead of creating a **separate** spreadsheet file titled ‘Sample’ with two tabs, produce sheets **in this open workbook**:
   - sheet titled ‘Sample’
   - sheet titled ‘Sample Size Calculation’
3. Step 2 parenthetical: gold says “columns H and I” (I is not on Population). Writer prompt uses fixture axes plus the in-workbook oracle: Q2 is in H, Q3 is in G; variance = (G−H)/H into J; flags in K.

## In-workbook axes (fixture + oracle, not gold letters)

Population headers are A–H only: **G = Q3 2024 KRI**, **H = Q2 2024 KRI**. QoQ variance is (Q3−Q2)/Q2 = (G−H)/H. Eval-2 writes that into **J** and sample flags into **K** (already the writer prompt / harness convention).

Gold `Sample v2` is a **different** deliverable (variance in **I**, flags in **J**). `rubric_pretty.txt` is not a letter-shift of that layout (S-total wording even points at **K** while other lines treat **J** as variance or as the flag). Do not rewrite gold rubric letters for eval-2.

## Not changed

- Entity list (CB Cash Italy, CB Correspondent Banking Greece, IB Debt Markets Luxembourg, CB Trade Finance Brazil, PB EMEA UAE)
- Metrics A1 / C1, zero-both-quarters, Trade Finance / Correspondent Banking, Cayman Islands / Pakistan / UAE
- Coverage across all Divisions and sub-Divisions
- Sample-size parameters (90% confidence, 10% tolerable error)
- Step 1 wording (“second tab titled ‘Sample Size Calculation’”)
- Gold rubric, `task.json`, `meta.txt`, `prompt.gdpval.txt`, Population fixture, Sample gold workbook
- `docs/eval/gdpval/`

The gold rubric still describes a separate Excel file named `Sample`. This variant is for iterating WriterAgent/Calc in-workbook behavior; do not treat gold rubric items about a separate deliverable filename as automatically rewritten.

Harness pass/fail for this variant is [`rubric.eval2.md`](rubric.eval2.md) (fixture + in-workbook oracle), not a letter-shift of `rubric_pretty.txt`.

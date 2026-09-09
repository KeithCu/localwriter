# Source

This directory is a **WriterAgent variant**, not a gold rewrite.

| Field | Value |
|-------|--------|
| Gold task id | `c3525d4d-2012-45df-853e-2d2a0e902991` |
| Untouched gold tree | [`docs/eval/gdpval/c3525d4d-2012-45df-853e-2d2a0e902991/`](../../gdpval/c3525d4d-2012-45df-853e-2d2a0e902991/) |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |
| Short label | Floorstand holiday budget |

Gold files here (`prompt.gdpval.txt`, `rubric_pretty.txt`, `rubric.json`, `meta.txt`, `task.json`, `gold/Deliverable Holiday Floorstand Budget.xlsx`, `gold/Final Email Deliverable.docx`) are copies of that tree / HF row.

## Fixture conversions

| File | Provenance |
|------|------------|
| `fixtures/Email Trail Floorstands.docx` | Byte copy of gold reference |
| `fixtures/Email Trail Floorstands.odt` | Writer-friendly sibling. Gold DOCX failed `soffice --convert-to odt` (“source file could not be loaded”). Rewritten with `python-docx` then converted. Key anchors match gold (1228 stores, $17.69/unit, $5.65 / $2.24 / $1.89, 5% overage, $22,802.41). |
| `fixtures/Holiday Floorstand Store List Original.xlsx` | Byte copy of gold reference |
| `fixtures/Holiday Floorstand Store List Original.ods` | `soffice --convert-to ods` of that xlsx (sheet title stays gold `Store List`) |
| `fixtures/Holiday Matrix final count.xlsx` | Byte copy of gold reference |
| `fixtures/Holiday Matrix final count.ods` | `soffice --convert-to ods` of that xlsx (sheet title stays gold `FINAL`) |
| `fixtures/Holiday Floorstand Budget.ods` | Empty two-tab Calc scaffold (Cost Comparison + Final Store List). Built by `write_floorstand_budget_ods` in `scripts/eval_2_headed.py`. **Write target.** Not a copy of the gold deliverable. |

Do not edit the gold tree when iterating on this experiment. The headed helper stages **only** the email-trail `.odt`, the two store-list `.ods` files, and the budget scaffold into a clean trial dir (plus a blank open email). Prompt, rubric, gold, notes, and the gold deliverable xlsx/docx stay outside that folder so `document_research` cannot list them.

Two open documents per session (v1 pre-open cheat): the Writer draft is the email deliverable; the Calc scaffold is the budget write target. Email trail + store lists are research / read-only.

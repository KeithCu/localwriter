# Source

This directory is a **WriterAgent variant**, not a gold rewrite.

| Field | Value |
|-------|--------|
| Gold task id | `4520f882-715a-482d-8e87-1cb3cbdfe975` |
| Untouched gold tree | [`docs/eval/gdpval/4520f882-715a-482d-8e87-1cb3cbdfe975/`](../../gdpval/4520f882-715a-482d-8e87-1cb3cbdfe975/) |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |
| Short label | Theatre CBA |

Gold files here (`prompt.gdpval.txt`, `rubric_pretty.txt`, `rubric.json`, `meta.txt`, `task.json`, `gold/Theatre CBA.xlsx`) are copies of that tree / HF row.

## Fixture conversions

| File | Provenance |
|------|------------|
| `fixtures/CBA excerpt.docx` | Byte copy of gold reference |
| `fixtures/CBA excerpt.odt` | Writer-friendly sibling. Gold DOCX failed `soffice --convert-to odt` (“source file could not be loaded”). Rewritten with `python-docx` then converted. Paragraph and wage-table text match gold (`ARTICLE 4`, `$251.06`, `$2008.50`, `$55.67`, `$76.59`, `$137.87`). |
| `fixtures/Sample roster and schedule.xlsx` | Byte copy of gold reference (sheet title stays gold `Sheet1`) |
| `fixtures/Sample roster and schedule.ods` | `soffice --convert-to ods` of that xlsx |

Do not edit the gold tree when iterating on this experiment. The headed helper stages **only** the CBA excerpt `.odt` and roster `.xlsx` into a clean trial dir (plus a blank open `Theatre CBA.ods`). Prompt, rubric, gold, notes, and fixture siblings stay outside that folder so `document_research` cannot list them.

One writable document per session: the open Calc workbook is the deliverable. `CBA excerpt.odt` is research / read-only. The sample roster is a folder ref.

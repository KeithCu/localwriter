# Source

This directory is a **WriterAgent variant**, not a gold rewrite.

| Field | Value |
|-------|--------|
| Gold task id | `5f6c57dd-feb6-4e70-b152-4969d92d1608` |
| Untouched gold tree | [`docs/eval/gdpval/5f6c57dd-feb6-4e70-b152-4969d92d1608/`](../../gdpval/5f6c57dd-feb6-4e70-b152-4969d92d1608/) |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |
| Short label | Branch profitability |

Gold files here (`prompt.gdpval.txt`, `rubric_pretty.txt`, `rubric.json`, `meta.txt`, `task.json`) are copies of that tree / HF row. HF has a reference workbook only (no `deliverable_files`).

## Fixture conversions

| File | Provenance |
|------|------------|
| `fixtures/Raw Data for Branch Profitability Final.xlsx` | Byte copy of gold reference |
| `fixtures/Raw Data for Branch Profitability Final.ods` | `soffice --convert-to ods` of that xlsx. Sheet title stays gold `Raw Data`. |

Do not edit the gold tree when iterating on this experiment. The headed helper stages **only** the ODS into a clean trial dir and opens that copy. Prompt, rubric, notes, and the xlsx sibling stay outside that folder so `document_research` cannot list them.

One editable document per session: the open Calc workbook is both the raw data and the write target (in-workbook, like AFC). No Writer peer.

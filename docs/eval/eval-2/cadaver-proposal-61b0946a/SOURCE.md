# Source

This directory is a **WriterAgent variant**, not a gold rewrite.

| Field | Value |
|-------|--------|
| Gold task id | `61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0` |
| Untouched gold tree | [`docs/eval/gdpval/61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0/`](../../gdpval/61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0/) |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

Gold files here (`prompt.gdpval.txt`, `rubric_pretty.txt`, `rubric.json`, `meta.txt`, `task.json`, `gold/Collaborative Cadaver Program Proposal.docx`) are copies of that tree / HF row.

## Fixture conversions

| File | Provenance |
|------|------------|
| `fixtures/Cadaver Budget.xlsx` | Byte copy of gold reference (sheet title stays gold `Sheet1`) |
| `fixtures/Cadaver Budget.ods` | `soffice --convert-to ods` of that xlsx |

Do not edit the gold tree when iterating on this experiment. The headed helper stages **only** the budget `.xlsx` into a clean trial dir (plus a blank open proposal). Prompt, rubric, gold, notes, and fixture siblings stay outside that folder so `document_research` cannot list them.

One editable document per session: the open Writer proposal is the deliverable. `Cadaver Budget.xlsx` is research / read-only via `document_research` / Calc tools — not a second write.

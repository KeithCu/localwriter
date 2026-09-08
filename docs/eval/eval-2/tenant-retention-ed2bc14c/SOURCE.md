# Source

This directory is a **WriterAgent variant**, not a gold rewrite.

| Field | Value |
|-------|--------|
| Gold task id | `ed2bc14c-99ac-4a2a-8467-482a1a5d67f3` |
| Untouched gold tree | [`docs/eval/gdpval/ed2bc14c-99ac-4a2a-8467-482a1a5d67f3/`](../../gdpval/ed2bc14c-99ac-4a2a-8467-482a1a5d67f3/) |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

Gold files here (`prompt.gdpval.txt`, `rubric_pretty.txt`, `rubric.json`, `meta.txt`, `task.json`, `gold/Tenant Rentention Strategy.docx`) are copies of that tree / HF row. Keep the gold deliverable basename spelling (`Rentention`).

## Fixture conversions

| File | Provenance |
|------|------------|
| `fixtures/Current Renewal Letter.docx` | Byte copy of gold reference |
| `fixtures/Current Renewal Letter.odt` | Writer-friendly sibling. Gold DOCX is an incomplete OPC package (`soffice --convert-to odt` fails with “source file could not be loaded”). Rewritten with `python-docx` then converted with `soffice --convert-to odt`. Paragraph text matches gold. |
| `fixtures/Exit Survey Feedback.xlsx` | Byte copy of gold reference (sheet title stays gold `Suvery Comments`) |
| `fixtures/Exit Survey Feedback.ods` | `soffice --convert-to ods` of that xlsx |

Do not edit the gold tree when iterating on this experiment. The headed helper stages **only** the letter `.odt` and survey `.xlsx` into a clean trial dir (plus a blank open memo). Prompt, rubric, gold, notes, and fixture siblings stay outside that folder so `document_research` cannot list them.

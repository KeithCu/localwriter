# Source

This directory is a **WriterAgent variant**, not a gold rewrite.

| Field | Value |
|-------|--------|
| Gold task id | `8a7b6fca-60cc-4ae3-b649-971753cbf8b9` |
| Untouched gold tree | [`docs/eval/gdpval/8a7b6fca-60cc-4ae3-b649-971753cbf8b9/`](../../gdpval/8a7b6fca-60cc-4ae3-b649-971753cbf8b9/) |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |
| Short label | Process flow map |

Gold files here (`prompt.gdpval.txt`, `rubric_pretty.txt`, `rubric.json`, `meta.txt`, `task.json`, `gold/Process Flow Map.pdf`) are copies of that tree / HF row. No `reference_files` in the HF row.

## Fixture conversions

| File | Provenance |
|------|------------|
| `gold/Process Flow Map.pdf` | Byte copy of HF deliverable. **Not staged.** Not the write target. |
| `fixtures/Process Flow Map.odg` | Editable Draw stand-in (title-only canvas). Built by `write_draw_primary_odg` in `scripts/eval_2_headed.py`. |

Do not edit the gold tree when iterating on this experiment. The headed helper stages **only** the Draw stand-in into a clean trial dir. Prompt, rubric, gold, notes, and the gold PDF stay outside that folder so `document_research` cannot list them.

One editable document per session: the open Draw canvas **is** the deliverable. Writer is optional or absent. Invert GMP (where Draw was a side form).

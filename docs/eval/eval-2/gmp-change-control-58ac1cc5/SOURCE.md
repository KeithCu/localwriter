# Source

This directory is a **WriterAgent variant**, not a gold rewrite.

| Field | Value |
|-------|--------|
| Gold task id | `58ac1cc5-5754-4580-8c9c-8c67e1a9d619` |
| Untouched gold tree | [`docs/eval/gdpval/58ac1cc5-5754-4580-8c9c-8c67e1a9d619/`](../../gdpval/58ac1cc5-5754-4580-8c9c-8c67e1a9d619/) |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

Gold files here (`prompt.gdpval.txt`, `rubric_pretty.txt`, `rubric.json`, `meta.txt`, `task.json`, `gold/MR_Risk Assessment Summary Report.docx`, `gold/Change Control Form Filled.pdf`) are copies of that tree / HF row.

## Fixture conversions

| File | Provenance |
|------|------------|
| `fixtures/Anti foam COA_MR.pdf` | Byte copy of gold reference |
| `fixtures/Material Spec_MR.docx` | Byte copy of gold reference |
| `fixtures/Material Spec_MR.odt` | Writer-friendly sibling. Gold DOCX failed `soffice --convert-to odt` (“source file could not be loaded”). Rewritten with `python-docx` then converted. Key cells match gold (RMS-3333, CompCello, QY-GEL, `< 1 EU/ml`, lot `00004515`). |
| `fixtures/Change Control Form.pdf` | Byte copy of gold blank Form-920. **Not staged.** Not the write target. |
| `fixtures/Change Control Form.odg` | Editable Draw stand-in (labels + empty `fld_*` text boxes). Built by `write_gmp_change_control_odg` in `scripts/eval_2_headed.py`. |

Do not edit the gold tree when iterating on this experiment. The headed helper stages **only** the COA PDF, Material Spec `.odt`, and Draw stand-in into a clean trial dir (plus a blank open memo). Prompt, rubric, gold, notes, the gold filled PDF, and the blank gold PDF stay outside that folder so `document_research` cannot list them.

Two open documents per session (v1 pre-open cheat): the Writer memo is the textual deliverable; the Draw stand-in is the form write target. COA / spec are research / read-only.

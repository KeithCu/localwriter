# Source

This directory is a **WriterAgent variant**, not a gold rewrite.

| Field | Value |
|-------|--------|
| Gold task id | `83d10b06-26d1-4636-a32c-23f92c57f30b` |
| Untouched gold tree | [`docs/eval/gdpval/83d10b06-26d1-4636-a32c-23f92c57f30b/`](../../gdpval/83d10b06-26d1-4636-a32c-23f92c57f30b/) |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

Gold files here (`prompt.gdpval.txt`, `rubric_pretty.txt`, `rubric.json`, `meta.txt`, `task.json`, `gold/Sample v2.xlsx`) are copies of that tree / HF row. Optional `.ods` siblings were converted with `soffice --convert-to ods` for Calc convenience; they are not extra HF artifacts.

Eval-2 `fixtures/Population v2.xlsx` / `.ods` started as that gold Population copy; the data sheet tab is now `Population` (gold tree still uses `Sheet1`). See [`SMOOTHER_CHANGES.md`](SMOOTHER_CHANGES.md). Do not edit the gold tree when iterating on this experiment.

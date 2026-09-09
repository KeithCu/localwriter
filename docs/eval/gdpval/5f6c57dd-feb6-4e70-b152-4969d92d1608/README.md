# GDPval gold task port: `5f6c57dd-feb6-4e70-b152-4969d92d1608`

Faithful one-task package from [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
(OpenAI GDPval gold subset). No harness redesign — materials only.

| Field | Value |
|-------|--------|
| Task id | `5f6c57dd-feb6-4e70-b152-4969d92d1608` |
| Sector | Finance and Insurance |
| Occupation | Financial Managers |
| Deliverables | branch / regional profitability workbook |

## Contents

- `prompt.txt` — exact gold prompt
- `task.json` — HF row metadata (refs, deliverables, rubric)
- `rubric.json` / `rubric_pretty.txt` — gold rubric
- `reference_files/52dfa090145b2077b0434571f616f4b1/Raw Data for Branch Profitability Final.xlsx` — gold reference
- (no deliverable files in HF row)
- `meta.txt` — short provenance

## License / attribution

Source: Hugging Face `openai/gdpval`. See the [dataset card](https://huggingface.co/datasets/openai/gdpval)
and OpenAI GDPval terms before redistributing or scoring. This tree is a
straight copy of one gold item for WriterAgent eval experimentation.

## Next (not in this PR)

Eval-2 WriterAgent variant (prompt delta, fixtures, oracle), peer/Draw multi-doc
port, and headed trials will be separate work.

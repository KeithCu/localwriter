# GDPval gold task port: `4520f882-715a-482d-8e87-1cb3cbdfe975`

Faithful one-task package from [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
(OpenAI GDPval gold subset). No harness redesign — materials only.

| Field | Value |
|-------|--------|
| Task id | `4520f882-715a-482d-8e87-1cb3cbdfe975` |
| Sector | Finance and Insurance |
| Occupation | Financial Managers |
| Deliverables | theatre CBA payroll calculator |

## Contents

- `prompt.txt` — exact gold prompt
- `task.json` — HF row metadata (refs, deliverables, rubric)
- `rubric.json` / `rubric_pretty.txt` — gold rubric
- `reference_files/4d6d96f2061fc75357419dba98993b90/Sample roster and schedule.xlsx` — gold reference
- `reference_files/4e2deede441818560dc6da2a5a98bd1d/CBA excerpt.docx` — gold reference
- `deliverable_files/9b5f97b8e386f6d87dcd42fe683d77b2/Theatre CBA.xlsx` — expert gold deliverable
- `meta.txt` — short provenance

## License / attribution

Source: Hugging Face `openai/gdpval`. See the [dataset card](https://huggingface.co/datasets/openai/gdpval)
and OpenAI GDPval terms before redistributing or scoring. This tree is a
straight copy of one gold item for WriterAgent eval experimentation.

## Next (not in this PR)

Eval-2 WriterAgent variant (prompt delta, fixtures, oracle), peer/Draw multi-doc
port, and headed trials will be separate work.

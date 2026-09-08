# GDPval gold task port: `61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0`

Faithful one-task package from [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
(OpenAI GDPval gold subset). No harness redesign — materials only.

| Field | Value |
|-------|--------|
| Task id | `61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0` |
| Sector | Health Care and Social Assistance |
| Occupation | Medical and Health Services Managers |
| Deliverable | Word proposal `Collaborative Cadaver Program Proposal.docx` |

## Contents

- `prompt.txt` — exact gold prompt
- `task.json` — HF row metadata (refs, deliverables, rubric)
- `rubric.json` / `rubric_pretty.txt` — gold rubric
- `reference_files/.../Cadaver Budget.xlsx` — General Surgery cadaver cost sheet
- `deliverable_files/.../Collaborative Cadaver Program Proposal.docx` — expert gold proposal
- `meta.txt` — short provenance

## License / attribution

Source: Hugging Face `openai/gdpval`. See the [dataset card](https://huggingface.co/datasets/openai/gdpval)
and OpenAI GDPval terms before redistributing or scoring. This tree is a
straight copy of one gold item for WriterAgent eval experimentation.

## Next (not in this PR)

Wiring into the eval runner, short-prompt/cwd layouts, and pairwise grading
will be discussed separately.

# GDPval gold task port: `ed2bc14c-99ac-4a2a-8467-482a1a5d67f3`

Faithful one-task package from [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
(OpenAI GDPval gold subset). No harness redesign — materials only.

| Field | Value |
|-------|--------|
| Task id | `ed2bc14c-99ac-4a2a-8467-482a1a5d67f3` |
| Sector | Real Estate and Rental and Leasing |
| Occupation | Property, Real Estate, and Community Association Managers |
| Deliverable | Word memo `Tenant Rentention Strategy.docx` (gold basename spelling) |

## Contents

- `prompt.txt` — exact gold prompt
- `task.json` — HF row metadata (refs, deliverables, rubric)
- `rubric.json` / `rubric_pretty.txt` — gold rubric
- `reference_files/.../Current Renewal Letter.docx` — current 60-day renewal letter
- `reference_files/.../Exit Survey Feedback.xlsx` — 20 exit-survey comments
- `deliverable_files/.../Tenant Rentention Strategy.docx` — expert gold memo
- `meta.txt` — short provenance

## License / attribution

Source: Hugging Face `openai/gdpval`. See the [dataset card](https://huggingface.co/datasets/openai/gdpval)
and OpenAI GDPval terms before redistributing or scoring. This tree is a
straight copy of one gold item for WriterAgent eval experimentation.

## Next (not in this PR)

Wiring into the eval runner, short-prompt/cwd layouts, and pairwise grading
will be discussed separately.

# GDPval gold task port: `a46d5cd2-55fe-48fa-a4c6-6aaf6b9991b5`

Faithful one-task package from [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
(OpenAI GDPval gold subset). No harness redesign — materials only.

| Field | Value |
|-------|--------|
| Task id | `a46d5cd2-55fe-48fa-a4c6-6aaf6b9991b5` |
| Sector | Retail Trade |
| Occupation | Private Detectives and Investigators |
| Deliverables | letterhead supervisor report (PARKED for headed) |

## Contents

- `prompt.txt` — exact gold prompt
- `task.json` — HF row metadata (refs, deliverables, rubric)
- `rubric.json` / `rubric_pretty.txt` — gold rubric
- `reference_files/f4c7bfae38d21c8ad4f4b624d194aab4/Photographs.zip` — gold reference
- `reference_files/339003d010f40f9ed1411a68395cfb33/Company Letterhead 1.pdf` — gold reference
- `reference_files/39e66e0812071bbee3079f25d4c5e50d/Field investigator A.docx` — gold reference
- `reference_files/9d504ee569fe60c6cd7f2a4f3fe6a6ee/Field investigator B.docx` — gold reference
- `deliverable_files/10a37e57e35f2108b159d5c5ddf6f89a/Supervisor_report.pdf` — expert gold deliverable
- `meta.txt` — short provenance

## License / attribution

Source: Hugging Face `openai/gdpval`. See the [dataset card](https://huggingface.co/datasets/openai/gdpval)
and OpenAI GDPval terms before redistributing or scoring. This tree is a
straight copy of one gold item for WriterAgent eval experimentation.

## Next (not in this PR)

Eval-2 WriterAgent variant (prompt delta, fixtures, oracle), peer/Draw multi-doc
port, and headed trials will be separate work.

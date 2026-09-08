# GDPval gold task port: `58ac1cc5-5754-4580-8c9c-8c67e1a9d619`

Faithful one-task package from [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
(OpenAI GDPval gold subset). No harness redesign — materials only.

| Field | Value |
|-------|--------|
| Task id | `58ac1cc5-5754-4580-8c9c-8c67e1a9d619` |
| Sector | Professional, Scientific, and Technical Services |
| Occupation | Project Management Specialists |
| Deliverables | Word risk assessment `MR_Risk Assessment Summary Report.docx` + filled PDF `Change Control Form Filled.pdf` |

## Contents

- `prompt.txt` — exact gold prompt
- `task.json` — HF row metadata (refs, deliverables, rubric)
- `rubric.json` / `rubric_pretty.txt` — gold rubric
- `reference_files/.../Change Control Form.pdf` — blank change-control form (opens in Draw)
- `reference_files/.../Anti foam COA_MR.pdf` — certificate of analysis
- `reference_files/.../Material Spec_MR.docx` — material specification
- `deliverable_files/.../MR_Risk Assessment Summary Report.docx` — expert gold risk report
- `deliverable_files/.../Change Control Form Filled.pdf` — expert gold filled form
- `meta.txt` — short provenance

## License / attribution

Source: Hugging Face `openai/gdpval`. See the [dataset card](https://huggingface.co/datasets/openai/gdpval)
and OpenAI GDPval terms before redistributing or scoring. This tree is a
straight copy of one gold item for WriterAgent eval experimentation.

## Next (not in this PR)

Eval-2 WriterAgent variant (prompt delta, fixtures, oracle), peer/Draw multi-doc
port, and headed trials will be separate work.

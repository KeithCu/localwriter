# GDPval gold task port: `c3525d4d-2012-45df-853e-2d2a0e902991`

Faithful one-task package from [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
(OpenAI GDPval gold subset). No harness redesign — materials only.

| Field | Value |
|-------|--------|
| Task id | `c3525d4d-2012-45df-853e-2d2a0e902991` |
| Sector | Wholesale Trade |
| Occupation | Order Clerks |
| Deliverables | floorstand budget (Writer email + holiday budget workbook) |

## Contents

- `prompt.txt` — exact gold prompt
- `task.json` — HF row metadata (refs, deliverables, rubric)
- `rubric.json` / `rubric_pretty.txt` — gold rubric
- `reference_files/0d79e0cdd2e811609e73dcadc34d682f/Email Trail Floorstands.docx` — gold reference
- `reference_files/123c0b1cf9e9b6ecfccc06501a205384/Holiday Floorstand Store List Original.xlsx` — gold reference
- `reference_files/8548106161db37c37ff079eb0eec6ff9/Holiday Matrix final count.xlsx` — gold reference
- `deliverable_files/242d24d95a28c9597ff7ddff19d31e6a/Deliverable Holiday Floorstand Budget.xlsx` — expert gold deliverable
- `deliverable_files/3dcb8a9db76ff416cf0c731cd312d910/Final Email Deliverable.docx` — expert gold deliverable
- `meta.txt` — short provenance

## License / attribution

Source: Hugging Face `openai/gdpval`. See the [dataset card](https://huggingface.co/datasets/openai/gdpval)
and OpenAI GDPval terms before redistributing or scoring. This tree is a
straight copy of one gold item for WriterAgent eval experimentation.

## Next (not in this PR)

Eval-2 WriterAgent variant (prompt delta, fixtures, oracle), peer/Draw multi-doc
port, and headed trials will be separate work.

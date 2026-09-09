# GDPval gold task port: `8a7b6fca-60cc-4ae3-b649-971753cbf8b9`

Faithful one-task package from [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
(OpenAI GDPval gold subset). No harness redesign — materials only.

| Field | Value |
|-------|--------|
| Task id | `8a7b6fca-60cc-4ae3-b649-971753cbf8b9` |
| Sector | Manufacturing |
| Occupation | Industrial Engineers |
| Deliverables | process flow map (Draw-primary) |

## Contents

- `prompt.txt` — exact gold prompt
- `task.json` — HF row metadata (refs, deliverables, rubric)
- `rubric.json` / `rubric_pretty.txt` — gold rubric
- `deliverable_files/70fc7c97c4f41c368c2aeb0227a194e0/Process Flow Map.pdf` — expert gold deliverable
- (no reference files in HF row)
- `meta.txt` — short provenance

## License / attribution

Source: Hugging Face `openai/gdpval`. See the [dataset card](https://huggingface.co/datasets/openai/gdpval)
and OpenAI GDPval terms before redistributing or scoring. This tree is a
straight copy of one gold item for WriterAgent eval experimentation.

## Next (not in this PR)

Eval-2 WriterAgent variant (prompt delta, fixtures, oracle), peer/Draw multi-doc
port, and headed trials will be separate work.

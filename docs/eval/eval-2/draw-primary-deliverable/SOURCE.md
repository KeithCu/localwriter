# Source

**Needs gold materials.** No Draw-primary package exists under
[`docs/eval/gdpval/`](../../gdpval/). GMP’s gold PDF form is a **Writer
side form**, not this slot.

| Field | Value |
|-------|--------|
| Gold task id | TODO — not in-repo |
| Untouched gold tree | TODO |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

## In-tree search (`docs/eval/gdpval/`)

`58ac1cc5-…` is the only Draw-adjacent gold (Change Control PDF). Eval-2
already ports that as Writer+Draw **form fill**. Do not duplicate it.

## HF shortlist (not copied here)

| Candidate id | Occupation | Why it fits | Gold refs / dels (HF names) |
|--------------|------------|-------------|-----------------------------|
| **`8a7b6fca-60cc-4ae3-b649-971753cbf8b9`** (preferred Draw product) | Industrial Engineers | Process flow map is the deliverable | (no refs in the HF row) → `Process Flow Map.pdf` |
| `c44e9b62-7cd8-4f72-8ad9-f8fbddb94083` | Administrative Services Managers | Revised **organizational chart** (plus FTE workbook + briefing note) | `Organizational Chart Administrative Support Services Branch.pdf`, FTE xlsx, Budget Planning Principles.pdf → chart PDF + FTE xlsx + briefing DOCX |

Eval-2 v1 should score the **Draw tree** (nodes, connectors, labels),
not pixel-match a gold PDF. The org-chart gold is mixed-app; take the
chart as the Draw-primary slice and leave FTE/briefing off v1 unless a
later sibling wants them.

Floorstand **layout** (physical display) is not the same HF row as
floorstand **budget** (`c3525d4d-…`, slot 5). Do not reuse that budget
task here.

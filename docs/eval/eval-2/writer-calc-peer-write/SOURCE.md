# Source

**Needs gold materials.** No package for this sibling exists under
[`docs/eval/gdpval/`](../../gdpval/). Do not invent fixture files. When a
gold lands, **add** a new untouched gold id there; do not edit the four
existing trees.

| Field | Value |
|-------|--------|
| Gold task id | TODO — not in-repo |
| Untouched gold tree | TODO |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

## In-tree search (`docs/eval/gdpval/`)

The four shipped golds do **not** fit this slot:

| Id | Why not |
|----|---------|
| `ed2bc14c-…` Tenant | Writer memo; spreadsheet is a read ref |
| `61b0946a-…` Cadaver | Writer proposal; budget is research-only |
| `83d10b06-…` AFC | Calc-only sampling; no Writer peer write |
| `58ac1cc5-…` GMP | Writer + Draw form; not Calc write |

## HF shortlist (not copied here)

Search the gold subset for Writer **plus** a workbook the agent must
**write**, not merely read.

| Candidate id | Occupation | Why it fits | Gold refs / dels (HF names) |
|--------------|------------|-------------|-----------------------------|
| **`c3525d4d-2012-45df-853e-2d2a0e902991`** (preferred) | Order Clerks | Floorstand budget: Writer email + **written** holiday budget workbook | `Email Trail Floorstands.docx`, `Holiday Floorstand Store List Original.xlsx`, `Holiday Matrix final count.xlsx` → `Deliverable Holiday Floorstand Budget.xlsx`, `Final Email Deliverable.docx` |
| `4c18ebae-dfaa-4b76-b10c-61fcdf26734c` | Compliance Officers | SAR: Writer report + supporting transactions workbook | `Transactions Final.xlsx` → `Suspicious Activity Report (SAR).docx`, `Transactions Final Output.xlsx` |

Prefer floorstand if the trial must prove **Calc write** as the second
deliverable. SAR is the same shape (Writer start, workbook write) with a
compliance claim.

Port later: copy the HF row into a new `docs/eval/gdpval/<id>/` tree, then
stage Writer-friendly / ODS siblings in this stub’s `fixtures/`.

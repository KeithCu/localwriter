# Source

**Needs gold materials.** No reverse-Tenant package exists under
[`docs/eval/gdpval/`](../../gdpval/).

| Field | Value |
|-------|--------|
| Gold task id | TODO — not in-repo |
| Untouched gold tree | TODO |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

## In-tree search (`docs/eval/gdpval/`)

`ed2bc14c-…` is Tenant **forward** (Writer memo; letter + survey reads).
Do not port that tree into this folder. Cadaver is the same polarity
(Writer write, sheet read). AFC has no Writer brief.

## HF shortlist (not copied here)

Look for a **Writer/DOCX brief** plus a **Calc deliverable**.

| Candidate id | Occupation | Why it fits | Gold refs / dels (HF names) |
|--------------|------------|-------------|-----------------------------|
| **`4520f882-715a-482d-8e87-1cb3cbdfe975`** (preferred) | Financial Managers | `CBA excerpt.docx` is the instructions sibling; roster xlsx is data; **Theatre CBA.xlsx** is the product | `CBA excerpt.docx`, `Sample roster and schedule.xlsx` → `Theatre CBA.xlsx` |

`b39a5aa7-…` (orchestra CBA) is Calc-only (roster xlsx → model) — better
as a slot 6 alternate than as reverse Tenant.

If theatre CBA is taken for slot 6 instead, this stub still needs a
different gold with a Writer brief. Leave SOURCE TODO rather than
double-claiming one id.

Port later: new `docs/eval/gdpval/<id>/` tree; stage `.odt` + `.ods` here.
The headed helper should open **Calc last**.

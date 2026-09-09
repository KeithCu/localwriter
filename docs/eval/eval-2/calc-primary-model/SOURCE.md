# Source

**Needs gold materials.** No package for this sibling exists under
[`docs/eval/gdpval/`](../../gdpval/). Do not invent a fake workbook.

| Field | Value |
|-------|--------|
| Gold task id | TODO — not in-repo |
| Untouched gold tree | TODO |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

## In-tree search (`docs/eval/gdpval/`)

`83d10b06-…` (AFC Population / Sample) is the only Calc gold in-tree, and
it is **sampling**. Do not reuse it. The other three golds are Writer
memos / a Writer+Draw form.

## HF shortlist (not copied here)

Prefer a **workbook deliverable** with real formulas. Skip sampling and
PDF-only investment memos.

| Candidate id | Occupation | Why it fits | Gold refs / dels (HF names) |
|--------------|------------|-------------|-----------------------------|
| **`5f6c57dd-feb6-4e70-b152-4969d92d1608`** (preferred) | Financial Managers | Branch / regional profitability schedules in one workbook | `Raw Data for Branch Profitability Final.xlsx` (HF also lists `Raw Data - Branch Profitability (Redacted).xlsx` in forks) |
| `b39a5aa7-cd1b-47ad-b249-90afd22f8f21` | Financial Managers | Orchestra CBA compensation **model** | `Orchestra assumptions and roster.xlsx` → `Orchestra_Compensation.xlsx` |
| `4520f882-715a-482d-8e87-1cb3cbdfe975` | Financial Managers | Theatre CBA payroll calculator (also a **reverse-Tenant** candidate) | `CBA excerpt.docx`, `Sample roster and schedule.xlsx` → `Theatre CBA.xlsx` |

Not this slot: Tiny-Rod Hit (`b78fd844-…`) is a narrative investment
report (PDF/DOCX), not a formula model. AFC (`83d10b06-…`) is sampling.

Port later: new `docs/eval/gdpval/<id>/` tree, then ODS fixture here.

# Source

**Needs gold materials.** No TOC + styles + comments pack exists under
[`docs/eval/gdpval/`](../../gdpval/).

| Field | Value |
|-------|--------|
| Gold task id | TODO — not in-repo |
| Untouched gold tree | TODO |
| Upstream | [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) on Hugging Face |

## In-tree search (`docs/eval/gdpval/`)

Tenant, Cadaver, and GMP are Writer-adjacent and already used. None ask
for TOC + named styles + comments in one long document. AFC is Calc.

## HF shortlist (not copied here)

A scan of the gold subset did **not** yield a clean “long Word pack”
with TOC + styles + comments as the product:

| Looked at | Why it is not this slot |
|-----------|-------------------------|
| `62f04c2f-e0f7-4710-876c-54ee9c2e8256` Gravon exchange overview | One-page overview + xlsx form — too short; form half is GMP-adjacent |
| `8314d1b1-5b0f-42a4-b5d5-91c0867b0913` draft legal memo | Memo, not a structured pack |
| `85d95ce5-b20c-41e2-834e-e788ce9622b6` social-history template | Form template; too close to a fill packet |
| Impress / PPTX golds | Peer v1 rejects `PresentationDocument` |

Keep searching HF for a long DOCX with Heading styles and an index. If
none is suitable, build a **WriterAgent-native** fixture later (see
[`docs/eval/ideas.md`](../../ideas.md) Writer #2 styles, #3 comments,
#8 TOC) and leave this SOURCE as TODO — do not invent a fake GDPval id.

# Source

This directory is a **WriterAgent-native** headed experiment, not a
GDPval gold rewrite. There is **no** task id and **no** new tree under
[`docs/eval/gdpval/`](../../gdpval/). Do not invent a fake GDPval id.
Do **not** download from Hugging Face for this slot — decision used
only the nine gold trees already in this repo.

| Field | Value |
|-------|--------|
| Gold task id | none — WriterAgent-native fixture |
| Untouched gold tree | none (no in-repo tree is a TOC + styles + comments pack; add-only if one lands later) |
| Upstream | n/a — harness debug pack for TOC + named styles + comments |

## Why not an in-repo GDPval gold

The local catalog is nine trees. None ask for a table of contents,
named heading styles, and review comments in one long Writer pack:

| Local tree | Why it is not this slot |
|------------|-------------------------|
| `ed2bc14c-…` Tenant Retention | Short memo; already Ready (slot 1) |
| `61b0946a-…` Cadaver proposal | Mini proposal; already Ready (slot 2) |
| `83d10b06-…` AFC sample | Calc / sampling workbook; already Ready (slot 3) |
| `58ac1cc5-…` GMP change control | Form + memo pair; already Ready (slot 4) |
| `c3525d4d-…` Floorstand / SAR | Writer email + Calc budget; slot 5 stub |
| `5f6c57dd-…` Branch profitability | Calc-primary workbook; slot 6 stub |
| `a46d5cd2-…` Company letterhead | Headed **template** fidelity; slot 7 **PARKED** |
| `8a7b6fca-…` Process flow map | Draw-primary PDF; slot 8 stub |
| `4520f882-…` Theatre CBA | Calc deliverable; slot 9 stub |

No other gold ids exist under `docs/eval/gdpval/` in this checkout.
Do not invent a fake GDPval id. Do not download from Hugging Face.

## Native fixtures

| File | Provenance |
|------|------------|
| `fixtures/Northhaven Library Program Facts.odt` | WriterAgent-native research note (site, project code, budget, hours) |
| `fixtures/Northhaven Decision Log.odt` | WriterAgent-native open decisions (annex siting, funding split, weekend staffing) |

`--launch` stages **only** those two research ODTs into a clean trial
dir and writes a blank `Northhaven Civic Library Capital Brief.odt`.
Prompt, rubric, notes, and fixture siblings stay outside that folder so
folder listing cannot see them.

One editable document per session: the open Writer brief is the
deliverable. The two research files are read-only. No peer. No second
form or deck.

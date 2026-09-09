# Source

This directory is a **WriterAgent-native** headed experiment, not a
GDPval gold rewrite. There is **no** Hugging Face task id and **no**
tree under [`docs/eval/gdpval/`](../../gdpval/). Do not invent a fake
GDPval id.

| Field | Value |
|-------|--------|
| Gold task id | none — WriterAgent-native fixture |
| Untouched gold tree | none (add-only rule: no new `gdpval/<uuid>/` because no HF row fits) |
| Upstream | n/a — harness debug pack for TOC + named styles + comments |

## Why not a GDPval gold

A rescan of the 220-row [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
gold subset (2026-09-09) still did **not** yield one Word deliverable
that needs a table of contents **and** named heading styles **and**
review comments in a single long pack:

| Looked at | Why it is not this slot |
|-----------|-------------------------|
| `8314d1b1-5b0f-42a4-b5d5-91c0867b0913` Clarivon legal memo | TOC appears only as a word-count exclusion; 3.5k memo, not a pack |
| `0353ee0c-18b5-4ad3-88e8-e001d223e1d7` PACT Act guide | Long structured guide, but the deliverable is PDF |
| `c2e8f271-7858-412f-b460-472463ad81d9` Coding Standards | “Comments” are code-review opinions; no TOC; ≤6 pages |
| `5d0feb24-e8b6-4ace-b64f-d5cd1a8b563d` TRAPPIST-1 edit | Word comments + track changes on an existing draft; no new pack / TOC |
| `c9bf9801-9640-45fa-8166-1ab01f2d98e4` OIIDP mentorship guide | Multi-file pack; “style” is CDC branding, not named Writer styles |
| `85d95ce5-b20c-41e2-834e-e788ce9622b6` social-history template | Form / template; too close to parked slot 7 |
| `62f04c2f-e0f7-4710-876c-54ee9c2e8256` Gravon exchange overview | One-page overview + xlsx form |
| `46b34f78-6c06-4416-87e2-77b6d8b20ce9` Energy trading strategy | ≤10pp memo; “index” is a market index |
| Impress / PPTX golds | Peer v1 rejects `PresentationDocument` |

Tenant, Cadaver, and GMP are already used Writer-adjacent golds. None
ask for TOC + named styles + comments together.

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

# eval-2 — WriterAgent hard-task variants

**Eval-2 is for debugging the harness.** Iterate here. Do **not** edit
`docs/eval/gdpval/` gold trees except by **adding** a new untouched gold
id. A multi-model benchmark comes later, when ~10 siblings exist.

Each subdirectory is one experiment. **Ready** means headed helper +
oracle exist. **Stub** means fixture notes only — not headed-ready gold.

| # | Experiment | App | Status | Gold / source |
|---|------------|-----|--------|----------------|
| 1 | [`tenant-retention-ed2bc14c/`](tenant-retention-ed2bc14c/) | Writer + folder read | Ready | `ed2bc14c-99ac-4a2a-8467-482a1a5d67f3` |
| 2 | [`cadaver-proposal-61b0946a/`](cadaver-proposal-61b0946a/) | Writer + budget research | Ready | `61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0` |
| 3 | [`afc-sample-83d10b06/`](afc-sample-83d10b06/) | Calc / sampling-style | Ready | `83d10b06-26d1-4636-a32c-23f92c57f30b` |
| 4 | [`gmp-change-control-58ac1cc5/`](gmp-change-control-58ac1cc5/) | Writer + Draw form, peer fill | Ready | `58ac1cc5-5754-4580-8c9c-8c67e1a9d619` |
| 5 | [`writer-calc-peer-write/`](writer-calc-peer-write/) | Writer → Calc write (Floorstand budget) | Ready | `c3525d4d-2012-45df-853e-2d2a0e902991` |
| 6 | [`calc-primary-model/`](calc-primary-model/) | Calc-primary model (not sampling) | Stub | `5f6c57dd-feb6-4e70-b152-4969d92d1608` gold tree in-repo; fixtures/oracle TBD |
| 7 | [`writer-headed-template/`](writer-headed-template/) | Writer on a real template | Stub / **PARKED** | `a46d5cd2-55fe-48fa-a4c6-6aaf6b9991b5` gold tree in-repo; **PARKED** (headed letterhead) |
| 8 | [`draw-primary-deliverable/`](draw-primary-deliverable/) | Draw-primary (org chart / process map) | Stub | `8a7b6fca-60cc-4ae3-b649-971753cbf8b9` gold tree in-repo; fixtures/oracle TBD |
| 9 | [`reverse-tenant/`](reverse-tenant/) | Calc deliverable; Writer brief sibling | Stub | `4520f882-715a-482d-8e87-1cb3cbdfe975` gold tree in-repo; fixtures/oracle TBD |
| 10 | [`long-writer-pack/`](long-writer-pack/) | Long Writer pack (TOC + styles + comments) | Headed-ready (native fixture) | WriterAgent-native; no HF gold |

Headed helper: `scripts/eval_2_headed.py` writes `chatbot.max_tool_rounds`
to **50** (AFC / Tenant / Cadaver / Long Writer pack) or **150** (GMP
Change Control / Writer→Calc Floorstand) and restores when done.
Everyday default stays **15**. Schema **max is 200** so a trial can
temporarily set 80 or 200 without clamp.
Do not hand-edit `writeragent.json`. Do not open `fixtures/` or the task
directory — `--launch` stages a clean trial dir so `document_research`
cannot list prompt/rubric/gold.

Stubs **6–9 are not wired** into `--task` / `--launch` / `--score`. Slot
**7 stays PARKED**. Do not invent helper flags for those stubs. See each
stub `run.md`.

```bash
# Calc / AFC (default)
.venv/bin/python scripts/eval_2_headed.py --launch
.venv/bin/python scripts/eval_2_headed.py --score docs/eval/eval-2/afc-sample-83d10b06/runs/<stamp>/final_workbook.ods

# Writer / Tenant Retention
.venv/bin/python scripts/eval_2_headed.py --task tenant-retention --launch
.venv/bin/python scripts/eval_2_headed.py --task tenant-retention --score docs/eval/eval-2/tenant-retention-ed2bc14c/runs/<stamp>/final_memo.odt

# Writer / Collaborative Cadaver Program Proposal
.venv/bin/python scripts/eval_2_headed.py --task cadaver-proposal --launch
.venv/bin/python scripts/eval_2_headed.py --task cadaver-proposal --score docs/eval/eval-2/cadaver-proposal-61b0946a/runs/<stamp>/final_proposal.odt

# Writer + Draw / GMP Change Control
.venv/bin/python scripts/eval_2_headed.py --task gmp-change-control --launch
.venv/bin/python scripts/eval_2_headed.py --task gmp-change-control --score docs/eval/eval-2/gmp-change-control-58ac1cc5/runs/<stamp>/final_memo.odt

# Writer + Calc / Floorstand holiday budget
.venv/bin/python scripts/eval_2_headed.py --task writer-calc-peer-write --launch
.venv/bin/python scripts/eval_2_headed.py --task writer-calc-peer-write --score docs/eval/eval-2/writer-calc-peer-write/runs/<stamp>/final_memo.odt

# Writer / Long Writer pack (native TOC + styles + comments)
.venv/bin/python scripts/eval_2_headed.py --task long-writer-pack --launch
.venv/bin/python scripts/eval_2_headed.py --task long-writer-pack --score docs/eval/eval-2/long-writer-pack/runs/<stamp>/final_pack.odt
```

AFC `--launch` still copies **only** `Population v2.ods` into
`$TMP/writeragent-eval2-afc`. Tenant `--launch` copies the renewal letter
`.odt` + exit-survey `.xlsx` into `$TMP/writeragent-eval2-tenant` and
opens a blank `Tenant Retention Strategy.odt`. Cadaver `--launch` copies
`Cadaver Budget.xlsx` into `$TMP/writeragent-eval2-cadaver` and opens a
blank `Collaborative Cadaver Program Proposal.odt` (budget is
research-only). GMP `--launch` copies the COA PDF + Material Spec `.odt`
+ Draw form stand-in into `$TMP/writeragent-eval2-gmp`, writes a blank
`MR Risk Assessment Summary.odt`, and opens **both** the Draw stand-in
and that memo (Writer last). The gold PDF is not the write target.
Floorstand `--launch` copies the email-trail `.odt` + original store-list
`.ods` + final-matrix `.ods` + empty budget scaffold into
`$TMP/writeragent-eval2-writer-calc`, writes a blank
`Draft Floorstand Email.odt`, and opens **both** the Calc scaffold and
that email (Writer last). The gold deliverable xlsx is not the write
target. Store lists are research-only.
Long Writer `--launch` copies the two native research ODTs into
`$TMP/writeragent-eval2-long-writer` and opens a blank
`Northhaven Civic Library Capital Brief.odt` (no peer).

Oracles: [`scripts/eval_2_ods_oracle.py`](../../scripts/eval_2_ods_oracle.py)
(AFC workbook),
[`scripts/eval_2_tenant_oracle.py`](../../scripts/eval_2_tenant_oracle.py)
(Writer memo),
[`scripts/eval_2_cadaver_oracle.py`](../../scripts/eval_2_cadaver_oracle.py)
(Writer proposal),
[`scripts/eval_2_gmp_oracle.py`](../../scripts/eval_2_gmp_oracle.py)
(Writer memo + Draw form),
[`scripts/eval_2_floorstand_oracle.py`](../../scripts/eval_2_floorstand_oracle.py)
(Writer email + Calc budget), and
[`scripts/eval_2_long_writer_oracle.py`](../../scripts/eval_2_long_writer_oracle.py)
(Writer pack: TOC / styles / comments). Rubrics:
[`afc-sample-83d10b06/rubric.eval2.md`](afc-sample-83d10b06/rubric.eval2.md),
[`tenant-retention-ed2bc14c/rubric.eval2.md`](tenant-retention-ed2bc14c/rubric.eval2.md),
[`cadaver-proposal-61b0946a/rubric.eval2.md`](cadaver-proposal-61b0946a/rubric.eval2.md),
[`gmp-change-control-58ac1cc5/rubric.eval2.md`](gmp-change-control-58ac1cc5/rubric.eval2.md),
[`writer-calc-peer-write/rubric.eval2.md`](writer-calc-peer-write/rubric.eval2.md),
[`long-writer-pack/rubric.eval2.md`](long-writer-pack/rubric.eval2.md).
Stub rubric outlines live in each `6–9` folder; no CLI scorer yet.

# eval-2 — WriterAgent hard-task variants

**Eval-2 is for debugging the harness.** Iterate here. Do **not** edit
`docs/eval/gdpval/` gold trees except by **adding** a new untouched gold
id. A multi-model benchmark comes later, when ~10 siblings exist.

Each subdirectory is one experiment:

| Experiment | App | Gold task | Trial |
|------------|-----|-----------|-------|
| [`afc-sample-83d10b06/`](afc-sample-83d10b06/) | Calc | `83d10b06-26d1-4636-a32c-23f92c57f30b` | [`run.md`](afc-sample-83d10b06/run.md) |
| [`tenant-retention-ed2bc14c/`](tenant-retention-ed2bc14c/) | Writer | `ed2bc14c-99ac-4a2a-8467-482a1a5d67f3` | [`run.md`](tenant-retention-ed2bc14c/run.md) |

Headed helper: `scripts/eval_2_headed.py` writes `chatbot.max_tool_rounds`
to **50** and restores when done. Everyday default stays **15**. Schema
**max is 200** so a trial can temporarily set 80 or 200 without clamp.
Do not hand-edit `writeragent.json`. Do not open `fixtures/` or the task
directory — `--launch` stages a clean trial dir so `document_research`
cannot list prompt/rubric/gold.

```bash
# Calc / AFC (default)
.venv/bin/python scripts/eval_2_headed.py --launch
.venv/bin/python scripts/eval_2_headed.py --score docs/eval/eval-2/afc-sample-83d10b06/runs/<stamp>/final_workbook.ods

# Writer / Tenant Retention
.venv/bin/python scripts/eval_2_headed.py --task tenant-retention --launch
.venv/bin/python scripts/eval_2_headed.py --task tenant-retention --score docs/eval/eval-2/tenant-retention-ed2bc14c/runs/<stamp>/final_memo.odt
```

AFC `--launch` still copies **only** `Population v2.ods` into
`$TMP/writeragent-eval2-afc`. Tenant `--launch` copies the renewal letter
`.odt` + exit-survey `.xlsx` into `$TMP/writeragent-eval2-tenant` and
opens a blank `Tenant Retention Strategy.odt`.

Oracles: [`scripts/eval_2_ods_oracle.py`](../../scripts/eval_2_ods_oracle.py)
(AFC workbook) and
[`scripts/eval_2_tenant_oracle.py`](../../scripts/eval_2_tenant_oracle.py)
(Writer memo). Rubrics:
[`afc-sample-83d10b06/rubric.eval2.md`](afc-sample-83d10b06/rubric.eval2.md),
[`tenant-retention-ed2bc14c/rubric.eval2.md`](tenant-retention-ed2bc14c/rubric.eval2.md).

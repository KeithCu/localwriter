# eval-2 — WriterAgent hard-task variants

Iterate here. Do **not** edit `docs/eval/gdpval/` gold trees.

Each subdirectory is one experiment. First: `afc-sample-83d10b06/` (GDPval auditor sample, minimal prompt delta for in-workbook deliverable).

See each task’s `run.md` for how to execute a trial.

Headed GDPval/AFC: run `scripts/eval_2_headed.py --launch` (writes `chatbot.max_tool_rounds` to 50, restores when done). `--launch` copies **only** `Population v2.ods` into a clean trial dir (`$TMP/writeragent-eval2-afc` by default) and opens that copy — prompt/rubric/gold and fixture siblings stay out of the folder `document_research` can list. Do not open `fixtures/` or the task directory. Do not hand-edit `writeragent.json`. Everyday default stays 15.

After a trial, score the saved workbook (not chat Ready):

```bash
.venv/bin/python scripts/eval_2_headed.py --score docs/eval/eval-2/afc-sample-83d10b06/runs/<stamp>/final_workbook.ods
```

Oracle: [`scripts/eval_2_ods_oracle.py`](../../scripts/eval_2_ods_oracle.py). Rubric: [`afc-sample-83d10b06/rubric.eval2.md`](afc-sample-83d10b06/rubric.eval2.md).

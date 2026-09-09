# Run — Reverse Tenant (Theatre CBA) trial

Manual Calc chat trial with a Writer brief sibling. Not wired into
`dataset.py` / `run_eval`. Harness debug, not a multi-model benchmark.

## Setup

1. From the repo root, **deploy** the extension the headed session will
   load (`make deploy`). Then start the headed helper **with
   `--task reverse-tenant --launch`**. It **writes**
   `"chatbot.max_tool_rounds": 150` into `writeragent.json` and restores
   the previous value (or removes the key) on Enter / Ctrl-C. Do not edit
   the JSON by hand.

   ```bash
   .venv/bin/python scripts/eval_2_headed.py --task reverse-tenant --launch
   ```

   `--launch` copies **only** `fixtures/CBA excerpt.odt` and
   `fixtures/Sample roster and schedule.xlsx` into
   `$TMP/writeragent-eval2-reverse-tenant` (override with `--trial-dir`),
   writes a blank `Theatre CBA.ods` there, and opens **both** the Writer
   brief and that blank workbook (Calc last, so chat focus is the
   deliverable). Prompt, rubric, gold, notes, and fixture siblings stay
   outside that folder so `document_research` cannot list them. Do
   **not** open `fixtures/` or this task directory. Do **not** treat the
   Writer excerpt as a second write target.

   Headed start is **150** rounds (complex CBA payroll model + Writer
   brief read; 200 is fine if a trial stalls; schema max is **200**). Do
   not raise the everyday default (15). Trailing args run a command as
   the session and skip staging — use that only if the workbook and
   brief are already in a clean dir with the roster beside them. Confirm
   in the debug log: `Tool-calling loop START (max 150 rounds)`.
2. Use the **Calc** sidebar for the user prompt. The Writer document is
   already open for research; do not paste the prompt there.
3. Set the chat model to `openai/gpt-oss-120b:nitro`.
4. Paste the full contents of `prompt.writeragent.txt` as the user
   message. Do not paste `prompt.gdpval.txt`.
5. Watch the UNO message box and `writeragent_debug.log` (next to
   `writeragent.json`) for tool-loop START.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` (example: `runs/20260909-1530-gpt-oss-120b/`) and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent (should match `prompt.writeragent.txt`) |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_workbook.ods` | Calc deliverable after the agent finished (the staged trial-dir workbook, not `gold/`) |
| `notes.txt` | Observer notes: brief unread, Writer overwritten, empty sheets, rubric mismatches, timing |

Then score the saved workbook. Ready / STREAM_DONE is ignored — an empty
model fails even if the brief was read:

```bash
.venv/bin/python scripts/eval_2_headed.py --task reverse-tenant --score runs/<stamp>-gpt-oss-120b/final_workbook.ods
```

See [`rubric.eval2.md`](rubric.eval2.md). Leave gold under `gold/` and this `run.md` unchanged when adding a trial.

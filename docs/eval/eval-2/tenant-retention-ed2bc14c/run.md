# Run — Tenant Retention trial

Manual Writer chat trial. Not wired into `dataset.py` / `run_eval`.
Harness debug, not a multi-model benchmark.

## Setup

1. From the repo root, start the headed helper **with `--task tenant-retention --launch`**. It **writes** `"chatbot.max_tool_rounds": 50` into `writeragent.json` and restores the previous value (or removes the key) on Enter / Ctrl-C. Do not edit the JSON by hand.

   ```bash
   .venv/bin/python scripts/eval_2_headed.py --task tenant-retention --launch
   ```

   `--launch` copies **only** `fixtures/Current Renewal Letter.odt` and
   `fixtures/Exit Survey Feedback.xlsx` into `$TMP/writeragent-eval2-tenant`
   (override with `--trial-dir`), writes a blank
   `Tenant Retention Strategy.odt` there, and opens that blank memo in
   Writer. Prompt, rubric, gold, notes, the gold-typo deliverable, and
   fixture siblings stay outside that folder so `document_research` cannot
   list them. Do **not** open `fixtures/` or this task directory.

   Headed start is **50** rounds (80 is fine if a trial stalls; schema max
   is **200** so a temporary `writeragent.json` bump will not clamp). Do
   not raise the everyday default (15). Trailing args run a command as the
   session (`-- soffice --writer memo.odt`) and skip staging — use that
   only if the memo is already in a clean dir with the two refs beside it.
   Confirm in the debug log: `Tool-calling loop START (max 50 rounds)`.
2. Set the chat model to `openai/gpt-oss-120b:nitro`.
3. Paste the full contents of `prompt.writeragent.txt` as the user message. Do not paste `prompt.gdpval.txt`.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` (example: `runs/20260908-1530-gpt-oss-120b/`) and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent (should match `prompt.writeragent.txt`) |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_memo.odt` | Writer doc after the agent finished (the staged trial-dir memo, not `gold/`) |
| `notes.txt` | Observer notes: failures, extra files created, rubric mismatches, timing |

Then score the saved memo. Ready / STREAM_DONE is ignored — an empty body fails:

```bash
.venv/bin/python scripts/eval_2_headed.py --task tenant-retention --score runs/<stamp>-gpt-oss-120b/final_memo.odt
```

See [`rubric.eval2.md`](rubric.eval2.md). Leave gold under `gold/` and this `run.md` unchanged when adding a trial.

# Run — Long Writer pack trial

Manual Writer chat trial. Not wired into `dataset.py` / `run_eval`.
Harness debug, not a multi-model benchmark.

WriterAgent-native fixture (no in-repo GDPval gold). See
[`SOURCE.md`](SOURCE.md). Do not download from Hugging Face for this
slot.

## Setup

1. From the repo root, start the headed helper **with `--task long-writer-pack --launch`**. It **writes** `"chatbot.max_tool_rounds": 50` into `writeragent.json` and restores the previous value (or removes the key) on Enter / Ctrl-C. Do not edit the JSON by hand.

   ```bash
   .venv/bin/python scripts/eval_2_headed.py --task long-writer-pack --launch
   ```

   `--launch` copies **only** `fixtures/Northhaven Library Program Facts.odt`
   and `fixtures/Northhaven Decision Log.odt` into
   `$TMP/writeragent-eval2-long-writer` (override with `--trial-dir`),
   writes a blank `Northhaven Civic Library Capital Brief.odt` there, and
   opens that blank brief in Writer. Prompt, rubric, notes, and fixture
   siblings stay outside that folder so folder listing cannot see them.
   Do **not** open `fixtures/` or this task directory. The two research
   files are read-only — do not treat them as a second writable
   deliverable. No peer.

   Headed start is **50** rounds (80 is fine if a long pack stalls;
   schema max is **200** so a temporary `writeragent.json` bump will not
   clamp). Do not raise the everyday default (15). Trailing args run a
   command as the session (`-- soffice --writer brief.odt`) and skip
   staging — use that only if the brief is already in a clean dir with
   the two research ODTs beside it. Confirm in the debug log:
   `Tool-calling loop START (max 50 rounds)`.
2. Set the chat model to `openai/gpt-oss-120b:nitro`.
3. Paste the full contents of `prompt.writeragent.txt` as the user message.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` (example: `runs/20260909-1200-gpt-oss-120b/`) and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent (should match `prompt.writeragent.txt`) |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_pack.odt` | Writer doc after the agent finished (the staged trial-dir brief) |
| `notes.txt` | Observer notes: missing TOC, style drift, no comments |

Then score the saved pack. Ready / STREAM_DONE is ignored — a body
without TOC / styles / comments fails:

```bash
.venv/bin/python scripts/eval_2_headed.py --task long-writer-pack --score runs/<stamp>-gpt-oss-120b/final_pack.odt
```

See [`rubric.eval2.md`](rubric.eval2.md).

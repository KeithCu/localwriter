# Run — Draw-primary process flow map trial

Manual Draw chat trial. Not wired into `dataset.py` / `run_eval`.
Harness debug, not a multi-model benchmark.

## Setup

1. From the repo root, **deploy** the extension the headed session will
   load (`make deploy`). Then start the headed helper **with
   `--task draw-primary --launch`**. It **writes**
   `"chatbot.max_tool_rounds": 50` into `writeragent.json` and restores
   the previous value (or removes the key) on Enter / Ctrl-C. Do not edit
   the JSON by hand.

   ```bash
   .venv/bin/python scripts/eval_2_headed.py --task draw-primary --launch
   ```

   `--launch` copies **only** `fixtures/Process Flow Map.odg` into
   `$TMP/writeragent-eval2-draw` (override with `--trial-dir`) and opens
   that Draw canvas. Prompt, rubric, gold, notes, and the gold
   `Process Flow Map.pdf` stay outside that folder so
   `document_research` cannot list them. Do **not** open `fixtures/` or
   this task directory. Do **not** File→Open the gold PDF as the write
   target. Do **not** open Impress.

   Headed start is **50** rounds (80 is fine if a trial stalls; schema
   max is **200**). Do not raise the everyday default (15). Trailing args
   run a command as the session and skip staging — use that only if the
   Draw canvas is already in a clean dir. Confirm in the debug log:
   `Tool-calling loop START (max 50 rounds)`.
2. **Open the Draw sidebar** (WriterAgent deck on the process-map
   document). This Draw document **is** the deliverable — invert GMP
   (no Writer memo required).
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
| `final_drawing.odg` | Draw doc after the agent finished (the staged trial-dir canvas, not `gold/`) |
| `notes.txt` | Observer notes: missing connectors, label gaps, extra files, timing |

Then score the saved drawing. Ready / STREAM_DONE is ignored — a
title-only page fails. A trial directory works too:

```bash
.venv/bin/python scripts/eval_2_headed.py --task draw-primary --score runs/<stamp>-gpt-oss-120b/final_drawing.odg
```

See [`rubric.eval2.md`](rubric.eval2.md). Leave gold under `gold/` and this `run.md` unchanged when adding a trial.

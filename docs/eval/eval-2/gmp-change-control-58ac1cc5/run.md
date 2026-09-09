# Run — GMP Change Control trial

Manual Writer + Draw chat trial. Not wired into `dataset.py` / `run_eval`.
Harness debug, not a multi-model benchmark.

## Setup

1. From the repo root, **deploy** the extension the headed session will
   load (`make deploy`). Then start the headed helper **with
   `--task gmp-change-control --launch`**. It **writes**
   `"chatbot.max_tool_rounds": 150` into `writeragent.json` and restores
   the previous value (or removes the key) on Enter / Ctrl-C. Do not edit
   the JSON by hand.

   ```bash
   .venv/bin/python scripts/eval_2_headed.py --task gmp-change-control --launch
   ```

   `--launch` copies **only** `fixtures/Anti foam COA_MR.pdf`,
   `fixtures/Material Spec_MR.odt`, and
   `fixtures/Change Control Form.odg` into
   `$TMP/writeragent-eval2-gmp` (override with `--trial-dir`), writes a
   blank `MR Risk Assessment Summary.odt` there, and opens **both** the
   Draw stand-in and that blank memo (Writer last, so chat focus is the
   memo). Prompt, rubric, gold, notes, the gold filled PDF, and the blank
   gold PDF stay outside that folder so `document_research` cannot list
   them. Do **not** open `fixtures/` or this task directory. Do **not**
   File→Open the gold `Change Control Form.pdf` as the write target.

   Headed start is **150** rounds (200 is fine if a trial stalls; schema
   max is **200**). Do not raise the everyday default (15). Trailing args
   run a command as the session and skip staging — use that only if the
   memo and form are already in a clean dir with the COA + spec beside
   them. Confirm in the debug log:
   `Tool-calling loop START (max 150 rounds)`.
2. **Open the Draw sidebar once** (WriterAgent deck on the form
   document) so the stand-in is a live peer. Then use the **Writer**
   sidebar for the user prompt.
3. Set the chat model to `openai/gpt-oss-120b:nitro`.
4. Paste the full contents of `prompt.writeragent.txt` as the user
   message. Do not paste `prompt.gdpval.txt`.
5. Watch the UNO message box and `writeragent_debug.log` (next to
   `writeragent.json`) for peer inject / tool-loop START.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` (example: `runs/20260909-1530-gpt-oss-120b/`) and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent (should match `prompt.writeragent.txt`) |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_memo.odt` | Writer doc after the agent finished (the staged trial-dir memo, not `gold/`) |
| `final_form.odg` | Draw stand-in after fill (not the gold PDF) |
| `notes.txt` | Observer notes: failures, extra files created, rubric mismatches, timing |

Then score the saved pair. Ready / STREAM_DONE is ignored — an empty
memo or blank form fails. The memo path looks for a sibling
`final_form.odg` or `Change Control Form.odg`; a trial directory works
too:

```bash
.venv/bin/python scripts/eval_2_headed.py --task gmp-change-control --score runs/<stamp>-gpt-oss-120b/final_memo.odt
```

See [`rubric.eval2.md`](rubric.eval2.md). Leave gold under `gold/` and this `run.md` unchanged when adding a trial.

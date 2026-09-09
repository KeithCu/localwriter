# Run — Writer → Calc peer-write (Floorstand) trial

Manual Writer + Calc chat trial. Not wired into `dataset.py` / `run_eval`.
Harness debug, not a multi-model benchmark.

## Setup

1. From the repo root, **deploy** the extension the headed session will
   load (`make deploy`). Then start the headed helper **with
   `--task writer-calc-peer-write --launch`**. It **writes**
   `"chatbot.max_tool_rounds": 150` into `writeragent.json` and restores
   the previous value (or removes the key) on Enter / Ctrl-C. Do not edit
   the JSON by hand.

   ```bash
   .venv/bin/python scripts/eval_2_headed.py --task writer-calc-peer-write --launch
   ```

   `--launch` copies **only** `fixtures/Email Trail Floorstands.odt`,
   `fixtures/Holiday Floorstand Store List Original.ods`,
   `fixtures/Holiday Matrix final count.ods`, and
   `fixtures/Holiday Floorstand Budget.ods` into
   `$TMP/writeragent-eval2-writer-calc` (override with `--trial-dir`),
   writes a blank `Draft Floorstand Email.odt` there, and opens **both**
   the scaffold workbook and that blank email (Writer last, so chat
   focus is the email). Prompt, rubric, gold, notes, and the gold
   deliverable xlsx/docx stay outside that folder so `document_research`
   cannot list them. Do **not** open `fixtures/` or this task directory.
   Do **not** File→Open the gold `Deliverable Holiday Floorstand Budget.xlsx`
   as the write target.

   Headed start is **150** rounds (200 is fine if a trial stalls; schema
   max is **200**). Do not raise the everyday default (15). Trailing args
   run a command as the session and skip staging — use that only if the
   email and budget workbook are already in a clean dir with the email
   trail + store lists beside them. Confirm in the debug log:
   `Tool-calling loop START (max 150 rounds)`.
2. **Open the Calc sidebar once** (WriterAgent deck on the budget
   workbook) so the workbook is a live peer. Then use the **Writer**
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
| `final_memo.odt` | Writer email after the agent finished (the staged trial-dir draft, not `gold/`) |
| `final_workbook.ods` | Calc budget after the peer write (not the gold xlsx, not a store-list copy) |
| `notes.txt` | Observer notes: failures, extra files created, rubric mismatches, timing |

Then score the saved pair. Ready / STREAM_DONE is ignored — an empty
email or an untouched scaffold workbook fails. The memo path looks for a
sibling `final_workbook.ods` or `Holiday Floorstand Budget.ods`; a trial
directory works too:

```bash
.venv/bin/python scripts/eval_2_headed.py --task writer-calc-peer-write --score runs/<stamp>-gpt-oss-120b/final_memo.odt
```

See [`rubric.eval2.md`](rubric.eval2.md). Leave gold under `gold/` and this `run.md` unchanged when adding a trial.

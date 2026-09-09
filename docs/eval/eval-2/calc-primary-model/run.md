# Run — Calc-primary model (placeholder)

Stub. Not wired into `scripts/eval_2_headed.py` `--task` / `--launch` /
`--score`. Do **not** pass an unregistered `--task` name.

Harness debug, not a multi-model benchmark.

## Setup (when materials exist)

1. From the repo root, **deploy** the extension (`make deploy`).
2. Do **not** call `--launch` for this stub. Copy **only** the staged
   workbook into a clean trial dir. Prompt, rubric, notes, and gold stay
   outside that folder.
3. Open that workbook in Calc. Single-doc Calc trials in the existing
   helper use **50** rounds (AFC). Schema **max is 200**. Everyday default
   stays **15**. Do not hand-edit `writeragent.json`.
4. Set the chat model to `openai/gpt-oss-120b:nitro`.
5. Paste the full contents of `prompt.writeragent.txt` as the user
   message.

Confirm in the debug log: `Tool-calling loop START (max 50 rounds)` once
the helper is wired. Ready / STREAM_DONE is ignored — empty sheets fail.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_workbook.ods` | Workbook after the agent finished |
| `notes.txt` | Observer notes: wrong factor, pinned formula, empty tabs |

No `--score` path yet. See [`rubric.eval2.md`](rubric.eval2.md).

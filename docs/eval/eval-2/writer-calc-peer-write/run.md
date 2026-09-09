# Run — Writer → Calc peer-write (placeholder)

Stub. Not wired into `scripts/eval_2_headed.py` `--task` / `--launch` /
`--score`. Not wired into `dataset.py` / `run_eval`. Do **not** pass an
unregistered `--task` name.

Harness debug, not a multi-model benchmark.

## Setup (when materials exist)

1. From the repo root, **deploy** the extension the headed session will
   load (`make deploy`).
2. Do **not** call `--launch` for this stub (it would stage AFC / Tenant /
   Cadaver / GMP). Stage a **clean trial directory** by hand: Writer brief
   + Calc workbook only. Prompt, rubric, notes, and gold stay outside that
   folder.
3. Pre-open **both** documents (Writer last). Open the **Calc sidebar
   once** so the workbook is a live peer.
4. Two-turn peer trials in the existing helper use **150** rounds (GMP).
   Schema **max is 200**. Everyday default stays **15**. Do not hand-edit
   `writeragent.json`. A future `--task` for this sibling should reuse that
   150-round write/restore — do not invent a new flag here.
5. Set the chat model to `openai/gpt-oss-120b:nitro`.
6. Paste the full contents of `prompt.writeragent.txt` in the **Writer**
   sidebar. Do not paste a gold HF prompt until a WriterAgent delta exists.

Confirm in the debug log: `Tool-calling loop START (max 150 rounds)` once
the helper is wired. Ready / STREAM_DONE is ignored — an untouched
workbook fails.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_memo.odt` | Writer doc after the agent finished |
| `final_workbook.ods` | Calc workbook after the peer write |
| `notes.txt` | Observer notes: failures, extra files, timing |

No `--score` path yet. See [`rubric.eval2.md`](rubric.eval2.md).

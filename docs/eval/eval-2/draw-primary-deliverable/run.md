# Run — Draw-primary deliverable (placeholder)

Stub. Not wired into `scripts/eval_2_headed.py` `--task` / `--launch` /
`--score`. Do **not** pass an unregistered `--task` name. Do **not** open
Impress (peer v1 rejects `PresentationDocument`).

Harness debug, not a multi-model benchmark.

## Setup (when materials exist)

1. `make deploy`.
2. Do **not** call `--launch` for this stub (GMP `--launch` stages the
   change-control form, not this canvas). Stage a clean trial dir with
   the Draw document only (plus research refs if any).
3. Open the Draw document. Open the **Draw sidebar once**.
4. Single-doc trials in the existing helper use **50** rounds. A later
   Draw-primary `--task` can follow that 50-round write/restore. Schema
   **max is 200**. Everyday default stays **15**. Do not hand-edit
   `writeragent.json`.
5. Model: `openai/gpt-oss-120b:nitro`.
6. Paste `prompt.writeragent.txt` in the Draw sidebar.

Ready / STREAM_DONE is ignored — an empty page fails.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_drawing.odg` | Draw doc after the agent finished |
| `notes.txt` | Observer notes: missing connectors, label gaps |

No `--score` path yet. See [`rubric.eval2.md`](rubric.eval2.md).

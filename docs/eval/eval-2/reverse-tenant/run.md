# Run — Reverse Tenant (placeholder)

Stub. Not wired into `scripts/eval_2_headed.py` `--task` / `--launch` /
`--score`. Do **not** pass an unregistered `--task` name.

Harness debug, not a multi-model benchmark.

## Setup (when materials exist)

1. `make deploy`.
2. Do **not** call `--launch` for this stub (Tenant `--launch` opens a
   **blank memo**). Stage a clean trial dir with the **workbook** plus the
   Writer instructions sibling only.
3. Open both; **Calc last** so chat focus is the deliverable. The `.odt`
   is research / read-only.
4. Calc + folder-ref trials can follow the existing **50**-round helper
   write (AFC / Tenant / Cadaver). Schema **max is 200**. Everyday default
   stays **15**. Do not hand-edit `writeragent.json`.
5. Model: `openai/gpt-oss-120b:nitro`.
6. Paste `prompt.writeragent.txt` in the **Calc** sidebar.

Ready / STREAM_DONE is ignored — an empty model fails even if the brief
was read.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_workbook.ods` | Calc deliverable after the agent finished |
| `notes.txt` | Observer notes: brief unread, Writer overwritten, empty sheets |

No `--score` path yet. See [`rubric.eval2.md`](rubric.eval2.md).

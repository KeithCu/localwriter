# Run — Long Writer pack (placeholder)

Stub. Not wired into `scripts/eval_2_headed.py` `--task` / `--launch` /
`--score`. Do **not** pass an unregistered `--task` name.

Harness debug, not a multi-model benchmark.

## Setup (when materials exist)

1. `make deploy`.
2. Do **not** call `--launch` for this stub. Stage a clean trial dir with
   the open Writer pack only (plus any research refs).
3. Open that Writer document (blank long pack or seeded body).
4. Existing Writer-only helper trials use **50** rounds. A long pack may
   stall; schema **max is 200** so a temporary bump will not clamp.
   Everyday default stays **15**. Do not hand-edit `writeragent.json`.
5. Model: `openai/gpt-oss-120b:nitro`.
6. Paste `prompt.writeragent.txt` as the user message.

Ready / STREAM_DONE is ignored — a body without TOC / styles / comments
fails the later oracle even if chat says Ready.

## After the run

Create `runs/<stamp>-gpt-oss-120b/` and save:

| File | Contents |
|------|----------|
| `prompt_used.txt` | Exact text sent |
| `thinking_and_tools.md` | Model thinking plus tool calls |
| `final_pack.odt` | Writer doc after the agent finished |
| `notes.txt` | Observer notes: missing TOC, style drift, no comments |

No `--score` path yet. See [`rubric.eval2.md`](rubric.eval2.md).

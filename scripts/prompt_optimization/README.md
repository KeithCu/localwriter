# Writer prompt optimization with DSPy

This folder implements the DSPy-based optimization of `DEFAULT_CHAT_SYSTEM_PROMPT` for LocalWriter (see plan in repo).

## Setup

```bash
cd scripts/prompt_optimization
pip install -r requirements.txt
```

**Defaults: OpenRouter** with **qwen/qwen3-coder-next** (cheap and fast). Set your key:

- `OPENROUTER_API_KEY` or `OPENAI_API_KEY` – required for OpenRouter

Override model or endpoint via env or CLI:

- `OPENAI_API_BASE` – default `https://openrouter.ai/api/v1`
- `OPENAI_MODEL` – default `qwen/qwen3-coder-next`
- Or: `python run_optimize.py --model google/gemini-2.0-flash-001` / `--api-base ...` / `--api-key ...`

## Run

**Eval only (see per-example success without optimizing):**

```bash
export OPENROUTER_API_KEY="your-key"
python run_eval.py              # all examples
python run_eval.py -e table_from_mess   # one task_id
python run_eval.py -n 2         # first 2 examples
python run_eval.py -v          # verbose: print every tool call as it runs
```

Shows for each example: task_id, expected_contains / reject_contains pass or miss, correctness, tokens, score, and a short doc snippet. Use `-v`/`--verbose` to print each tool call (e.g. `get_document_content`, `apply_document_content`) so you see progress during long runs.

**Full optimization (MIPROv2):**

```bash
export OPENROUTER_API_KEY="your-key"
python run_optimize.py
```

Pick a different model:

```bash
python run_optimize.py --model google/gemini-2.0-flash-001
python run_optimize.py -m qwen/qwen3-coder-next -k sk-...
```

This runs MIPROv2 in **0-shot instruction-only** mode: it proposes alternative system prompts and keeps the one that scores best on the metric (correctness minus token penalty). Output is saved to `optimized_writer_prompt.json`.

- **`-j N`** / **`--jobs N`**: parallel evals (default 4).
- **`--auto light|medium|heavy`**: exploration level (default `light`). Use `medium` or `heavy` for more tries when your prompt is complicated.
- **`-t N`** / **`--trials N`**: explicit number of Bayesian optimization trials (overrides `--auto`; uses more exploration).

## Metric

- **Correctness**: Each example can define `expected_contains` and `reject_contains`; the final document (after mock tool calls) is checked.
- **Token penalty**: `score -= 0.01 * (total_tokens / 1000)` so fewer tokens improve the score. Tune in `metric.TOKEN_PENALTY_LAMBDA` if needed.

## Dataset

`dataset.py` defines 8 fixed examples: table-from-mess, reformat-resume, table-engineering, bulk-cleanup, logical-rewriting, format-preservation, style-application, bullet-consistency. Each has fixed `document_content` and `user_question` so runs are comparable.

## Tool subset

Mock tools in `tools_mock.py` implement `get_document_content`, `apply_document_content`, and `find_text` on an in-memory string. You can pass `tool_names` to `build_program()` to restrict which tools the model sees (for “how many tools is too many” sweeps).

## Applying the result

After a run, open `optimized_writer_prompt.json` and copy the optimized instruction text into `core/constants.py` as `DEFAULT_CHAT_SYSTEM_PROMPT` (or merge with `FORMAT_RULES` as in the current prompt). Then test in LocalWriter with the same evaluation tasks.

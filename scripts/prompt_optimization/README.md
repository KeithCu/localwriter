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
python run_eval.py                          # all examples
python run_eval.py -e table_from_mess       # one task_id
python run_eval.py -n 2                     # first 2 examples
python run_eval.py -v                       # verbose: print every tool call as it runs
python run_eval.py --compare-with optimized_writer_prompt.json   # compare current vs optimized
python run_eval.py --no-bust-cache   # disable cache-busting (default: on)
```

Shows for each example: task_id, expected_contains / reject_contains pass or miss, correctness, tokens, score, and a short doc snippet. Use `-v`/`--verbose` to print each tool call. Use `--compare-with` to run both the current prompt and the prompt from a DSPy JSON file, then report which scores higher. Cache-busting is enabled by default (unique suffix per example) to avoid OpenRouter prompt cache; use `--no-bust-cache` to disable.

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

## Multi-model evaluation (intelligence per dollar)

You can also run the same fixed dataset and current system prompt across **multiple models** and compare their performance and estimated cost.

Models and prices live in `model_configs.py` (one `ModelConfig` per model with context window and list prices in USD per 1M input/output tokens).

```bash
export OPENROUTER_API_KEY="your-key"

# Run all default models from model_configs.get_default_models()
python run_eval_multi.py

# Restrict to a subset of models by OpenRouter id
python run_eval_multi.py --models openai/gpt-oss-120b,openai/gpt-4o-mini

# Fewer examples (faster, cheaper)
python run_eval_multi.py -n 2

# 8 models in parallel (default); use -j 1 for sequential with verbose output
python run_eval_multi.py -j 8
```

For each model, `run_eval_multi.py` reports:

- **Average correctness** and **average score** (correctness minus token penalty).
- **Total tokens** used across all examples.
- **Estimated dollar cost**, based on per-million token prices.
- An **“intelligence per dollar”** figure: average correctness divided by total cost (higher is better).

Use `--out path.json` or `--out path.csv` to write results (format by extension). Results are written after each model completes so partial data is saved if the run is interrupted. The final file is sorted by intelligence-per-dollar.

### Eval framework (summary)

- **Dataset** (`dataset.py`): Fixed Writer tasks (document + user_question), each with optional `expected_contains` / `reject_contains` for pass/fail.
- **Program** (`program.py`): DSPy `WriterAssistant` (ReAct) with mock `get_document_content`, `apply_document_content`, `find_text`) and current `DEFAULT_CHAT_SYSTEM_PROMPT` from `core/constants.py`.
- **Metric**: Per-example **correctness** (0–1 from expected/reject), then **score** = correctness − 0.01×(tokens/1000). No judge model; tasks are objective checks only.
- **Single-model**: `run_eval.py` (one model, optional `--compare-with` for prompt A vs B).
- **Multi-model**: `run_eval_multi.py` runs the same eval across all models in `model_configs.py`, estimates cost from list prices, and ranks by **Corr/USD** (avg correctness ÷ total $).

### Benchmark results (best models, combined runs)

From multi-model runs on the default 8-evaluation Writer set, ranked by **Corr/USD** (avg correctness ÷ total cost; higher = better value) and/or **correctness**:

- **openai/gpt-oss-120b** — Top value in run 1 (346.8 Corr/USD, 1.0 correctness, ~$0.003 total).
- **google/gemini-3-flash-preview** — Strong value (161.7 Corr/USD, 0.925 correctness).
- **nvidia/nemotron-3-nano-30b-a3b** — Best value in run 2 (131.2 Corr/USD; 0.725 correctness, very cheap).
- **allenai/olmo-3.1-32b-instruct** — High correctness (0.963) and good value (84.1 Corr/USD).
- **openai/gpt-4o-mini** — Good balance (98.8 Corr/USD, 0.938 correctness).
- **nex-agi/deepseek-v3.1-nex-n1** — Solid (58.9 Corr/USD, 0.925 correctness).

Re-run with different model sets by editing `model_configs.py` (and uncommenting the block you want). Failed runs (0 tokens) usually mean a wrong OpenRouter id or API error; check stderr or logs.

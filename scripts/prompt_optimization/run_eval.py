#!/usr/bin/env python3
"""
Run the Writer assistant on the dataset (no optimization).
Shows per-example: task_id, expected/reject checks, correctness, tokens, score, and doc snippet.

Usage:
  export OPENROUTER_API_KEY="your-key"   # or OPENAI_API_KEY
  cd scripts/prompt_optimization
  python run_eval.py                    # run all examples
  python run_eval.py --example table_from_mess   # run one task_id
  python run_eval.py -n 2               # run first 2 examples only
  python run_eval.py -v                 # verbose: print every tool call
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dspy

from dataset import ALL_EXAMPLES, to_dspy_examples
from program import build_program
from metric import writer_assistant_metric, TOKEN_PENALTY_LAMBDA
import tools_mock

DEFAULT_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1.5"


def _correctness_breakdown(example, final_document: str) -> tuple[float, list[str], list[str]]:
    """Return (score, list of missing expected, list of bad reject found)."""
    expected = getattr(example, "expected_contains", []) or []
    reject = getattr(example, "reject_contains", []) or []
    score = 1.0
    missing = []
    for s in expected:
        if s not in (final_document or ""):
            score -= 0.2
            missing.append(s)
    found_reject = []
    for s in reject:
        if s in (final_document or ""):
            score -= 0.3
            found_reject.append(s)
    return max(0.0, min(1.0, score)), missing, found_reject


def main():
    p = argparse.ArgumentParser(description="Eval Writer assistant on dataset (no MIPROv2).")
    p.add_argument("--model", "-m", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    p.add_argument("--api-base", default=os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE))
    p.add_argument("--api-key", "-k", default=os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY", ""))
    p.add_argument("--example", "-e", metavar="TASK_ID", help="Run only this task_id (e.g. table_from_mess).")
    p.add_argument("-n", type=int, default=None, help="Run only first N examples.")
    p.add_argument("--verbose", "-v", action="store_true", help="Print every tool call as it runs.")
    args = p.parse_args()

    api_key = args.api_key
    api_base = args.api_base
    model = args.model
    if "openrouter" in api_base.lower() and not model.startswith("openrouter/"):
        model = "openrouter/" + model

    if not api_key and "openrouter" in api_base.lower():
        print("Warning: OPENROUTER_API_KEY (or OPENAI_API_KEY) not set.", file=sys.stderr)

    print(f"Model: {model} @ {api_base}\n")
    lm = dspy.LM(model=model, api_key=api_key, api_base=api_base, model_type="chat")
    dspy.configure(lm=lm)

    examples = to_dspy_examples(ALL_EXAMPLES, with_inputs=True)
    if args.example:
        examples = [ex for ex in examples if getattr(ex, "task_id", "") == args.example]
        if not examples:
            print(f"No example with task_id={args.example!r}. Valid: {[getattr(e, 'task_id', '') for e in to_dspy_examples(ALL_EXAMPLES)]}")
            return 1
    if args.n is not None:
        examples = examples[: args.n]

    tools_mock.VERBOSE = args.verbose
    program = build_program(instruction=None, tool_names=None)

    n = len(examples)
    print(f"Running {n} example(s). Each can take 15–60+ seconds (multiple API calls). Total often 2–10 min.\n")
    sys.stdout.flush()

    scores = []
    with dspy.settings.context(lm=lm, track_usage=True, cache=False):
        for i, ex in enumerate(examples):
            task_id = getattr(ex, "task_id", "") or f"example_{i}"
            doc = getattr(ex, "document_content", "")
            question = getattr(ex, "user_question", "")
            print(f"--- [{i+1}/{n}] {task_id} ---")
            print(f"  Q: {question[:80]}{'...' if len(question) > 80 else ''}")
            print("  Calling model (may take 15–60s)...", flush=True)

            try:
                pred = program(document_content=doc, user_question=question)
                final = getattr(pred, "final_document", "") or ""
                correct, missing, found_reject = _correctness_breakdown(ex, final)
                tokens = 0
                try:
                    usage = pred.get_lm_usage()
                    if usage:
                        for v in usage.values() if isinstance(usage, dict) else []:
                            if isinstance(v, dict) and "total_tokens" in v:
                                tokens = int(v["total_tokens"])
                                break
                except Exception:
                    pass
                penalty = TOKEN_PENALTY_LAMBDA * (tokens / 1000.0)
                score = max(0.0, correct - penalty)
                scores.append(score)

                if missing:
                    print(f"  expected_contains MISSING: {missing}")
                else:
                    print(f"  expected_contains: ok")
                if found_reject:
                    print(f"  reject_contains FOUND (bad): {found_reject}")
                else:
                    print(f"  reject_contains: ok")
                print(f"  correctness={correct:.2f}  tokens={tokens}  score={score:.3f}")
                snippet = (final[:300] + "...") if len(final) > 300 else final
                print(f"  doc snippet: {snippet!r}")
            except Exception as e:
                print(f"  ERROR: {e}")
                scores.append(0.0)
            print()

    if scores:
        print(f"Average score: {sum(scores)/len(scores):.3f} ({len(scores)} examples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Metric for DSPy prompt optimization: correctness + token penalty.
Higher score = better. Use with track_usage=True so we can read token counts.
"""
from __future__ import annotations

from typing import Any, Optional

# Token penalty weight: score -= LAMBDA * (total_tokens / 1000)
TOKEN_PENALTY_LAMBDA = 0.01


def _correctness_score(example: Any, final_document: str) -> float:
    """
    Return a score in [0, 1] based on expected_contains and reject_contains.
    final_document is the document content after the model's tool calls.
    """
    if not final_document:
        return 0.0
    score = 1.0
    expected = getattr(example, "expected_contains", []) or []
    reject = getattr(example, "reject_contains", []) or []
    for s in expected:
        if s not in final_document:
            score -= 0.2
    for s in reject:
        if s in final_document:
            score -= 0.3
    return max(0.0, min(1.0, score))


def _get_total_tokens(pred: Any) -> int:
    """Extract total tokens from prediction (DSPy get_lm_usage)."""
    try:
        usage = pred.get_lm_usage()
        if usage and isinstance(usage, dict):
            for model_data in usage.values():
                if isinstance(model_data, dict) and "total_tokens" in model_data:
                    return int(model_data["total_tokens"])
            for model_data in usage.values():
                if isinstance(model_data, dict):
                    p = int(model_data.get("prompt_tokens", 0))
                    c = int(model_data.get("completion_tokens", 0))
                    if p or c:
                        return p + c
    except Exception:
        pass
    return 0


def writer_assistant_metric(
    example: Any,
    pred: Any,
    trace: Optional[Any] = None,
    token_penalty_lambda: float = TOKEN_PENALTY_LAMBDA,
) -> float:
    """
    Metric for Writer prompt optimization.
    - Correctness: 0–1 from expected_contains / reject_contains in final document.
    - Token penalty: subtract token_penalty_lambda * (total_tokens / 1000).
    Higher is better.
    """
    final_doc = getattr(pred, "final_document", None) or ""
    correct = _correctness_score(example, final_doc)
    total_tokens = _get_total_tokens(pred)
    penalty = token_penalty_lambda * (total_tokens / 1000.0)
    score = correct - penalty
    return max(0.0, score)

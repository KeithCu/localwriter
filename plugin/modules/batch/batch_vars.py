"""Batch variable resolution: $last, $step.N, $last.bookmark, $step.N.bookmark.

Used by execute_batch to chain tool results. Paragraph indices and bookmark
names extracted from tool results flow into subsequent steps.
"""

import re

# Regex for all $var forms
_VAR_RE = re.compile(
    r'\$(?:'
    r'last\.bookmark'                 # $last.bookmark
    r'|last(?:([+-])(\d+))?'          # $last, $last+1, $last-2
    r'|step\.(\d+)\.bookmark'         # $step.1.bookmark
    r'|step\.(\d+)(?:([+-])(\d+))?'   # $step.1, $step.2+1
    r')')


def extract_step_info(result):
    """Extract paragraph_index and bookmark from a tool result.

    Returns (para_index: int|None, bookmark: str|None).
    """
    if not isinstance(result, dict):
        return None, None
    pi = result.get("paragraph_index")
    if pi is None:
        pi = result.get("para_index")
    if pi is not None:
        pi = int(pi)
    bm = result.get("bookmark")
    return pi, bm


def _resolve_var(match, batch_vars):
    """Replace a single $var match with its resolved value."""
    full = match.group(0)

    # $last.bookmark
    if full == "$last.bookmark":
        bm = batch_vars.get("$last.bookmark")
        return ("bookmark:%s" % bm) if bm else full

    # $step.N.bookmark
    if ".bookmark" in full:
        m = re.match(r'\$step\.(\d+)\.bookmark', full)
        if m:
            bm = batch_vars.get("$step.%s.bookmark" % m.group(1))
            return ("bookmark:%s" % bm) if bm else full
        return full

    # $last, $last+N, $last-N
    if full.startswith("$last"):
        base = batch_vars.get("$last")
        if base is None:
            return full
        sign = match.group(1)
        offset_str = match.group(2)
        offset = int(offset_str) if offset_str else 0
        if sign == '-':
            offset = -offset
        return str(base + offset)

    # $step.N, $step.N+M
    step_num = match.group(4)
    if step_num is not None:
        key = "$step.%s" % step_num
        base = batch_vars.get(key)
        if base is None:
            return full
        sign = match.group(5)
        offset_str = match.group(6)
        offset = int(offset_str) if offset_str else 0
        if sign == '-':
            offset = -offset
        return str(base + offset)

    return full


def resolve_batch_vars(args, batch_vars):
    """Recursively resolve $last / $step.N in args dict.

    String values that are EXACTLY a variable (e.g. "$last") become
    integers.  Strings containing a variable within text
    (e.g. "paragraph:$last") get string substitution.
    """
    if not batch_vars:
        return args
    if isinstance(args, dict):
        return {k: resolve_batch_vars(v, batch_vars)
                for k, v in args.items()}
    if isinstance(args, list):
        return [resolve_batch_vars(v, batch_vars) for v in args]
    if isinstance(args, str) and '$' in args:
        # Pure variable reference -> return as int
        pure = _VAR_RE.fullmatch(args)
        if pure:
            resolved = _resolve_var(pure, batch_vars)
            try:
                return int(resolved)
            except ValueError:
                return resolved
        # Embedded variable -> string substitution
        return _VAR_RE.sub(
            lambda m: _resolve_var(m, batch_vars), args)
    return args

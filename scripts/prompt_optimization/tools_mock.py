"""
Mock Writer tools for DSPy prompt optimization.
Operate on an in-memory document state so we can run without LibreOffice.
State is set per-example by the program before each run.
"""
from __future__ import annotations

import json
from typing import Optional

# Per-run document state. Set by program.forward() before calling the predictor.
_mock_doc_state = {"content": ""}

# When True, print each tool call to stdout (set by run_eval.py --verbose).
VERBOSE = False


def _log_tool(name: str, **kwargs) -> None:
    if VERBOSE:
        parts = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        print(f"    [tool] {name}({parts})", flush=True)


def set_document(content: str) -> None:
    """Set the mock document content for this run. Call at start of each example."""
    _mock_doc_state["content"] = content if isinstance(content, str) else ""


def get_content() -> str:
    """Return current document content (for metric)."""
    return _mock_doc_state["content"]


def get_document_content(scope: str = "full", max_chars: Optional[int] = None, start: Optional[int] = None, end: Optional[int] = None) -> str:
    """Mock get_document_content. Returns JSON like the real tool."""
    _log_tool("get_document_content", scope=scope, max_chars=max_chars, start=start, end=end)
    content = _mock_doc_state["content"]
    doc_len = len(content)
    if scope == "range" and (start is None or end is None):
        return json.dumps({"status": "error", "message": "scope 'range' requires start and end parameters"})
    if scope == "range":
        start = max(0, int(start))
        end = min(doc_len, int(end))
        content = content[start:end]
    if max_chars is not None and len(content) > max_chars:
        content = content[: max_chars]
    return json.dumps({
        "status": "ok",
        "content": content,
        "document_length": doc_len,
        "scope": scope,
    })


def apply_document_content(
    content: str,
    target: str,
    start: Optional[int] = None,
    end: Optional[int] = None,
    search: Optional[str] = None,
    all_matches: bool = False,
    case_sensitive: bool = True,
) -> str:
    """Mock apply_document_content. Mutates _mock_doc_state."""
    c = str(content)[:60]
    if len(str(content)) > 60:
        c += "…"
    _log_tool("apply_document_content", target=target, content_preview=c)
    if isinstance(content, list):
        content = "\n".join(str(x) for x in content)
    doc = _mock_doc_state["content"]
    if target == "full":
        _mock_doc_state["content"] = content
        return json.dumps({"status": "ok", "message": "Applied to full document."})
    if target == "search" and search is not None:
        if not case_sensitive:
            idx = doc.lower().find(search.lower())
            if idx == -1:
                return json.dumps({"status": "error", "message": "search not found"})
            doc = doc[:idx] + content + doc[idx + len(search):]
        else:
            if all_matches:
                doc = doc.replace(search, content)
            else:
                idx = doc.find(search)
                if idx == -1:
                    return json.dumps({"status": "error", "message": "search not found"})
                doc = doc[:idx] + content + doc[idx + len(search):]
        _mock_doc_state["content"] = doc
        return json.dumps({"status": "ok", "message": "Replaced."})
    if target == "range" and start is not None and end is not None:
        start, end = int(start), int(end)
        doc = doc[:start] + content + doc[end:]
        _mock_doc_state["content"] = doc
        return json.dumps({"status": "ok", "message": "Applied to range."})
    if target == "beginning":
        _mock_doc_state["content"] = content + doc
        return json.dumps({"status": "ok", "message": "Inserted at beginning."})
    if target == "end":
        _mock_doc_state["content"] = doc + content
        return json.dumps({"status": "ok", "message": "Inserted at end."})
    return json.dumps({"status": "error", "message": f"Unsupported target: {target}"})


def find_text(search: str, start: int = 0, limit: Optional[int] = None, case_sensitive: bool = True) -> str:
    """Mock find_text. Returns JSON with ranges."""
    s = str(search)
    _log_tool("find_text", search=(s[:40] + "…") if len(s) > 40 else s, start=start, limit=limit)
    doc = _mock_doc_state["content"]
    if not case_sensitive:
        doc_lower = doc.lower()
        needle = search.lower()
        ranges = []
        pos = start
        while True:
            idx = doc_lower.find(needle, pos)
            if idx == -1:
                break
            ranges.append({"start": idx, "end": idx + len(search), "text": doc[idx : idx + len(search)]})
            pos = idx + 1
            if limit is not None and len(ranges) >= limit:
                break
    else:
        ranges = []
        pos = start
        while True:
            idx = doc.find(search, pos)
            if idx == -1:
                break
            ranges.append({"start": idx, "end": idx + len(search), "text": search})
            pos = idx + 1
            if limit is not None and len(ranges) >= limit:
                break
    return json.dumps({"status": "ok", "ranges": ranges})


def get_tools_subset(names: Optional[list[str]] = None):
    """Return a list of mock tool callables for DSPy. If names is None, return the core three."""
    all_tools = {
        "get_document_content": get_document_content,
        "apply_document_content": apply_document_content,
        "find_text": find_text,
    }
    if names is None:
        names = list(all_tools.keys())
    return [all_tools[n] for n in names if n in all_tools]

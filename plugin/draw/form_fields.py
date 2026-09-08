# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2026 KeithCu (modifications and relicensing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Paper-form fill helpers and ``fill_draw_fields`` (Draw/Impress).

Two different form problems live in Draw:

- **Paper forms**: empty / near-empty text-capable shapes (TextShapes, blank
  boxes next to labels). GMP Change-Control PDFs opened in Draw look like this.
- **ControlShapes**: live ``com.sun.star.form.component.*`` widgets. Those stay
  on the shared ``form_*`` tools; this module only writes their Text/State when
  ``fill_draw_fields`` resolves one by name/index/label.

This is **not** PDF/AcroForm fill. Do not create ControlShapes here.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from plugin.draw.base import ToolDrawShapeBase

log = logging.getLogger(__name__)

# Placeholder ink on scanned/imported "paper" fields: underscores, dots, dashes.
_NEAR_EMPTY_RE = re.compile(r"^[\s._\-–—•·*]+$")

# Shapes that can hold a string but are not paper-form blanks.
_NON_PAPER_FORM_TYPES = (
    "LineShape",
    "ConnectorShape",
    "GraphicObjectShape",
    "GroupShape",
    "ControlShape",
    "PluginShape",
    "OLE2Shape",
    "MediaShape",
    "TableShape",
)

CONTROL_TYPE_MAP = {
    "checkbox": "com.sun.star.form.component.CheckBox",
    "text": "com.sun.star.form.component.TextField",
    "radio": "com.sun.star.form.component.RadioButton",
    "date": "com.sun.star.form.component.DateField",
    "combobox": "com.sun.star.form.component.ComboBox",
    "button": "com.sun.star.form.component.CommandButton",
    "listbox": "com.sun.star.form.component.ListBox",
}

_STATE_TRUE = frozenset({"1", "true", "yes", "on", "checked", "x"})
_STATE_FALSE = frozenset({"0", "false", "no", "off", "unchecked"})
_STATE_INDETERMINATE = frozenset({"2", "indeterminate"})


def short_shape_type(shape_type: str) -> str:
    return (shape_type or "").replace("com.sun.star.drawing.", "")


def is_paper_form_text_type(shape_type: str) -> bool:
    """True for text-capable drawing shapes that can be a paper-form blank."""
    st = short_shape_type(shape_type)
    return bool(st) and not any(token in st for token in _NON_PAPER_FORM_TYPES)


def is_text_shape_type(shape_type: str) -> bool:
    return "TextShape" in short_shape_type(shape_type)


def is_near_empty_text(text: str | None) -> bool:
    if text is None:
        return True
    stripped = str(text).strip()
    if not stripped:
        return True
    return bool(_NEAR_EMPTY_RE.fullmatch(stripped))


def is_control_shape_type(shape_type: str) -> bool:
    return "ControlShape" in short_shape_type(shape_type)


def readable_control_type(model: Any) -> str:
    """Map a UNO form component back to a short type string."""
    for type_str, service in CONTROL_TYPE_MAP.items():
        try:
            if model.supportsService(service):
                return type_str
        except Exception:
            continue
    return "unknown"


def parse_control_state(value: Any) -> int | None:
    """Parse checkbox/radio State (0/1/2). None if the value is not boolean-ish."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int) and not isinstance(value, bool):
        if value in (0, 1, 2):
            return value
        return None
    if value is None:
        return None
    token = str(value).strip().lower()
    if token in _STATE_TRUE:
        return 1
    if token in _STATE_FALSE:
        return 0
    if token in _STATE_INDETERMINATE:
        return 2
    return None


def snapshot_control(model: Any) -> dict[str, Any]:
    """Current name/type/value/state for a form component (feeds get_draw_tree)."""
    info: dict[str, Any] = {
        "type": readable_control_type(model),
        "name": getattr(model, "Name", "") or "",
    }
    try:
        label = getattr(model, "Label", None)
        if label:
            info["label"] = label
    except Exception:
        pass
    try:
        if hasattr(model, "Text"):
            text = model.Text
            # CheckBox/Radio often expose empty Text; only surface it when used as a value.
            if info["type"] in ("text", "date", "combobox") or (text not in (None, "")):
                info["text"] = text
    except Exception:
        pass
    try:
        if hasattr(model, "State"):
            info["state"] = int(model.State)
    except Exception:
        pass
    try:
        if hasattr(model, "StringItemList") and model.StringItemList is not None:
            info["items"] = list(model.StringItemList)
    except Exception:
        pass
    selected = _selected_control_items(model)
    if selected:
        info["selected"] = selected
    return info


def _selected_control_items(model: Any) -> list[str]:
    try:
        items = list(model.StringItemList) if hasattr(model, "StringItemList") and model.StringItemList is not None else []
        indexes = getattr(model, "SelectedItems", None)
        if indexes is None:
            return []
        out: list[str] = []
        for i in indexes:
            if isinstance(i, int) and 0 <= i < len(items):
                out.append(items[i])
        return out
    except Exception:
        return []


def apply_control_value(model: Any, value: Any) -> dict[str, Any]:
    """Write Text and/or State on a form component. Duck-typed for tests."""
    written: dict[str, Any] = {}
    kind = readable_control_type(model)
    state = parse_control_state(value)
    if state is not None and hasattr(model, "State"):
        model.State = state
        written["state"] = state
    if hasattr(model, "StringItemList"):
        selected = _select_control_item(model, value)
        if selected is not None:
            written["selected"] = selected
    # Text fields / combos keep the string; checkboxes already got State.
    if hasattr(model, "Text") and (kind in ("text", "date", "combobox") or "state" not in written):
        model.Text = "" if value is None else str(value)
        written["text"] = model.Text
    if not written:
        if hasattr(model, "Label"):
            model.Label = "" if value is None else str(value)
            written["label"] = model.Label
        else:
            return {"status": "error", "error": "Control has no Text or State to set"}
    written["status"] = "ok"
    written["kind"] = "control"
    written["control_type"] = kind
    return written


def _select_control_item(model: Any, value: Any) -> str | None:
    if value is None or not hasattr(model, "SelectedItems"):
        return None
    want = str(value).strip()
    if not want:
        return None
    try:
        items = list(model.StringItemList or ())
    except Exception:
        return None
    for i, item in enumerate(items):
        if str(item) == want or str(item).casefold() == want.casefold():
            try:
                model.SelectedItems = (i,)
            except Exception:
                return None
            return str(item)
    return None


def annotate_paper_form_nodes(nodes: list[dict[str, Any]]) -> None:
    """Mark blanks / fillable targets and attach a neighbor ``label_hint``.

    Neighbor heuristic (siblings only, same group level):

    1. Prefer the nearest non-empty text whose box sits **to the left** of the
       target and overlaps it vertically.
    2. Else the nearest non-empty text **above** the target that overlaps it
       horizontally.

    Empty ``TextShape`` nodes are always ``fillable``. Other empty text-capable
    shapes (rectangles, custom shapes) become fillable only when a neighbor
    label exists — so decorative empty boxes stay ``blank`` without becoming
    fill targets. ControlShapes are never paper-form fillable; they get a
    ``label_hint`` only when the widget itself has no Label.
    """
    for node in nodes:
        children = node.get("children")
        if isinstance(children, list):
            annotate_paper_form_nodes(children)

    labeled: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("control"):
            continue
        if not is_paper_form_text_type(str(node.get("type") or "")):
            continue
        text = node.get("text")
        if not is_near_empty_text(text if isinstance(text, str) else None) and text:
            labeled.append(node)

    for node in nodes:
        if node.get("control"):
            continue
        if not is_paper_form_text_type(str(node.get("type") or "")):
            continue
        if "geometry" not in node:
            continue
        text = node.get("text")
        if is_near_empty_text(text if isinstance(text, str) else None):
            node["blank"] = True

    for node in nodes:
        needs_hint = bool(node.get("blank")) or (
            bool(node.get("control")) and not (node.get("control") or {}).get("label")
        )
        if not needs_hint:
            continue
        hint = nearest_label_hint(node, labeled)
        if hint:
            node["label_hint"] = hint
        if node.get("blank") and (is_text_shape_type(str(node.get("type") or "")) or hint):
            node["fillable"] = True


def nearest_label_hint(target: dict[str, Any], labeled: list[dict[str, Any]]) -> str | None:
    tbox = _node_box(target)
    if tbox is None:
        return None
    best_left: tuple[int, int, str] | None = None
    best_above: tuple[int, int, str] | None = None
    for src in labeled:
        if src is target:
            continue
        sbox = _node_box(src)
        if sbox is None:
            continue
        text = str(src.get("text") or "").strip()
        if not text:
            continue
        # Left: candidate's right edge is at or left of target's left; Y overlap.
        if sbox[2] <= tbox[0] and _axis_overlap(sbox[1], sbox[3], tbox[1], tbox[3]):
            gap = tbox[0] - sbox[2]
            vdist = abs(_center(sbox, 1) - _center(tbox, 1))
            cand = (gap, vdist, text)
            if best_left is None or cand < best_left:
                best_left = cand
        # Above: candidate's bottom is at or above target's top; X overlap.
        if sbox[3] <= tbox[1] and _axis_overlap(sbox[0], sbox[2], tbox[0], tbox[2]):
            gap = tbox[1] - sbox[3]
            hdist = abs(_center(sbox, 0) - _center(tbox, 0))
            cand = (gap, hdist, text)
            if best_above is None or cand < best_above:
                best_above = cand
    if best_left:
        return best_left[2]
    if best_above:
        return best_above[2]
    return None


def _node_box(node: dict[str, Any]) -> tuple[int, int, int, int] | None:
    geom = node.get("geometry")
    if not isinstance(geom, dict):
        return None
    try:
        x = int(geom["x"])
        y = int(geom["y"])
        w = int(geom["width"])
        h = int(geom["height"])
    except (KeyError, TypeError, ValueError):
        return None
    return (x, y, x + w, y + h)


def _center(box: tuple[int, int, int, int], axis: int) -> int:
    if axis == 0:
        return (box[0] + box[2]) // 2
    return (box[1] + box[3]) // 2


def _axis_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    return min(a1, b1) - max(a0, b0) > 0


def shape_lookup_names(shape: Any) -> list[str]:
    """Names a caller may use: drawing ``Name`` plus Control.Name when present."""
    names: list[str] = []
    try:
        drawing_name = getattr(shape, "Name", "") or ""
        if drawing_name:
            names.append(str(drawing_name))
    except Exception:
        pass
    try:
        shape_type = shape.getShapeType()
    except Exception:
        shape_type = ""
    if is_control_shape_type(str(shape_type)):
        try:
            control_name = getattr(shape.Control, "Name", "") or ""
            if control_name and control_name not in names:
                names.append(str(control_name))
        except Exception:
            pass
    return names


def find_shape_on_page(page: Any, *, name: str | None = None, index: int | None = None) -> tuple[Any, int] | None:
    """Resolve a shape by Name (drawing or control) then by page index.

    Exact match wins, then case-insensitive. First hit on the page.
    """
    wanted = str(name or "").strip()
    if wanted:
        folded: tuple[Any, int] | None = None
        try:
            count = page.getCount()
        except Exception:
            count = 0
        for i in range(count):
            try:
                shape = page.getByIndex(i)
            except Exception:
                continue
            aliases = shape_lookup_names(shape)
            if wanted in aliases:
                return shape, i
            if folded is None:
                want_cf = wanted.casefold()
                if any(alias.casefold() == want_cf for alias in aliases):
                    folded = (shape, i)
        if folded is not None:
            return folded
    if index is not None:
        try:
            shape = page.getByIndex(int(index))
            return shape, int(index)
        except Exception:
            return None
    return None


def apply_shape_field_value(shape: Any, value: Any) -> dict[str, Any]:
    """setString on a paper-form shape, or Text/State on a ControlShape."""
    try:
        shape_type = shape.getShapeType()
    except Exception:
        shape_type = ""
    if is_control_shape_type(str(shape_type)):
        try:
            model = shape.Control
        except Exception as exc:
            return {"status": "error", "error": f"ControlShape has no model: {exc}"}
        return apply_control_value(model, value)
    if hasattr(shape, "setString"):
        try:
            shape.setString("" if value is None else str(value))
        except Exception as exc:
            return {"status": "error", "error": f"setString failed: {exc}"}
        return {"status": "ok", "kind": "text_shape"}
    return {"status": "error", "error": "Shape is not text-capable"}


def _field_identity(field: dict[str, Any]) -> dict[str, Any]:
    ident: dict[str, Any] = {}
    for key in ("name", "index", "label_hint"):
        if key in field and field[key] is not None and field[key] != "":
            ident[key] = field[key]
    return ident


def resolve_fill_field(page: Any, field: dict[str, Any]) -> tuple[Any, int] | str:
    """Return ``(shape, index)`` or an error string."""
    name = field.get("name")
    index = field.get("index")
    label_hint = field.get("label_hint")
    # Name is the stable paper-form key; index is fallback only when name is absent.
    if name not in (None, ""):
        found = find_shape_on_page(page, name=str(name), index=None)
        if found is None:
            return f"No shape matching name={name!r}"
        return found
    if index is not None:
        found = find_shape_on_page(page, name=None, index=index)
        if found is None:
            return f"No shape matching index={index}"
        return found
    hint = str(label_hint or "").strip()
    if not hint:
        return "Each field needs name, index, or label_hint"
    return _find_by_label_hint(page, hint)


def _page_nodes_for_hints(page: Any) -> list[dict[str, Any]]:
    """Lightweight sibling nodes so label_hint uses the same heuristic as the tree."""
    nodes: list[dict[str, Any]] = []
    try:
        count = page.getCount()
    except Exception:
        return nodes
    for i in range(count):
        try:
            shape = page.getByIndex(i)
        except Exception:
            continue
        try:
            shape_type = shape.getShapeType()
        except Exception:
            shape_type = "UnknownShape"
        node: dict[str, Any] = {"type": short_shape_type(str(shape_type)), "index": i, "_shape": shape}
        try:
            pos = shape.getPosition()
            size = shape.getSize()
            node["geometry"] = {"x": pos.X, "y": pos.Y, "width": size.Width, "height": size.Height}
        except Exception:
            pass
        try:
            if hasattr(shape, "getString"):
                node["text"] = shape.getString()
        except Exception:
            pass
        if is_control_shape_type(str(shape_type)):
            try:
                node["control"] = snapshot_control(shape.Control)
            except Exception:
                node["control"] = {"type": "unknown", "name": ""}
        nodes.append(node)
    annotate_paper_form_nodes(nodes)
    return nodes


def _find_by_label_hint(page: Any, hint: str) -> tuple[Any, int] | str:
    want = hint.casefold()
    nodes = _page_nodes_for_hints(page)
    exact: list[dict[str, Any]] = []
    contains: list[dict[str, Any]] = []
    for node in nodes:
        if not (node.get("fillable") or node.get("control")):
            continue
        labels = []
        if node.get("label_hint"):
            labels.append(str(node["label_hint"]))
        control = node.get("control") or {}
        if control.get("label"):
            labels.append(str(control["label"]))
        if control.get("name"):
            labels.append(str(control["name"]))
        for alias in shape_lookup_names(node.get("_shape")):
            labels.append(alias)
        matched = False
        contained = False
        for label in labels:
            token = label.strip().casefold()
            if not token:
                continue
            if token == want:
                matched = True
                break
            if want in token or token in want:
                contained = True
        if matched:
            exact.append(node)
        elif contained:
            contains.append(node)
    chosen = exact or contains
    if not chosen:
        return f"No fillable shape or control matching label_hint={hint!r}"
    node = chosen[0]
    return node["_shape"], int(node["index"])


class FillDrawFields(ToolDrawShapeBase):
    name = "fill_draw_fields"
    intent = "edit"
    description = (
        "Do fill empty text boxes and existing form widgets on a Draw/Impress page "
        "because paper forms are blank shapes next to labels, not new ControlShapes. "
        "Resolve each field by shape Name (preferred), page index, or neighbor "
        "label_hint from get_draw_tree, then setString or Control Text/State. "
        "Returns per-field ok/fail. Do not create ControlShapes unless the user asked."
    )
    parameters = {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "description": "0-based page index (active page if omitted)"},
            "fields": {
                "type": "array",
                "description": "Fields to write. Each item needs value plus name, index, or label_hint.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Shape Name or Control.Name from get_draw_tree."},
                        "index": {"type": "integer", "description": "0-based shape index on the page."},
                        "label_hint": {
                            "type": "string",
                            "description": "Neighbor label text (left/above heuristic) when the blank has no Name.",
                        },
                        "value": {"type": "string", "description": "Text to write, or checkbox/radio yes/true/1."},
                    },
                    "required": ["value"],
                },
            },
        },
        "required": ["fields"],
    }
    is_mutation = True

    def execute(self, ctx, **kwargs):
        from plugin.draw.shapes import _resolve_shape_page

        fields = kwargs.get("fields") or []
        if not isinstance(fields, list) or not fields:
            return self._tool_error("fields must be a non-empty list of {name|index|label_hint, value}.")

        page, actual_idx, err = _resolve_shape_page(ctx, kwargs)
        if err:
            return self._tool_error(err)
        if page is None:
            return self._tool_error("No draw page available.")

        results: list[dict[str, Any]] = []
        filled = 0
        failed = 0
        for raw in fields:
            if not isinstance(raw, dict):
                failed += 1
                results.append({"status": "error", "error": "Field must be an object with value."})
                continue
            ident = _field_identity(raw)
            if "value" not in raw:
                failed += 1
                results.append({**ident, "status": "error", "error": "Missing value"})
                continue
            resolved = resolve_fill_field(page, raw)
            if isinstance(resolved, str):
                failed += 1
                results.append({**ident, "status": "error", "error": resolved})
                continue
            shape, shape_index = resolved
            written = apply_shape_field_value(shape, raw.get("value"))
            row = {**ident, **written, "index": shape_index}
            names = shape_lookup_names(shape)
            if names and "name" not in row:
                row["name"] = names[0]
            if written.get("status") == "ok":
                filled += 1
            else:
                failed += 1
            results.append(row)

        status = "ok" if failed == 0 else ("partial" if filled else "error")
        return {
            "status": status,
            "page": actual_idx,
            "filled": filled,
            "failed": failed,
            "results": results,
            "message": f"Filled {filled} field(s), {failed} failed. Empty boxes are fill targets; no ControlShapes were created.",
        }

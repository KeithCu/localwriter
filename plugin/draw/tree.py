# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2024 John Balis
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
"""Tree (LO-DOM) tools for Draw/Impress documents."""

import logging

from plugin.framework.tool import ToolBase

log = logging.getLogger(__name__)


class GetDrawTree(ToolBase):
    name = "get_draw_tree"
    intent = "read"
    description = (
        "Do this to understand page layout, paper-form blanks, and form widgets without a screenshot. "
        "Empty/near-empty text boxes are fill targets (blank/fillable plus optional label_hint: nearest "
        "text to the left, else above). ControlShapes include type, name, and current value/state. "
        "Use the Name from this tree with shape_upsert or fill_draw_fields; do not create ControlShapes "
        "for paper forms."
    )
    parameters = {"type": "object", "properties": {"page": {"type": "integer", "description": "0-based page index (active page if omitted)"}}, "required": []}
    uno_services = ["com.sun.star.drawing.DrawingDocument", "com.sun.star.presentation.PresentationDocument"]
    doc_types = ["draw", "impress"]
    tier = "core"

    def execute(self, ctx, **kwargs):
        from plugin.draw.bridge import DrawBridge

        bridge = DrawBridge(ctx.doc)
        idx = kwargs.get("page")
        
        # Use provided index or resolved active index from context
        actual_idx = idx if idx is not None else ctx.active_page_index
        if actual_idx is None:
             actual_idx = bridge.get_active_page_index()

        try:
            page = bridge.get_pages().getByIndex(actual_idx)
        except Exception:
            return self._tool_error("Invalid page index: %s" % actual_idx)

        if page is None:
            return self._tool_error("No draw page available.")

        return {"status": "ok", "page": actual_idx, "tree": self._build_shape_tree(page)}

    def _build_shape_tree(self, xshapes, base_index=None):
        """Recursively build a semantic tree from an XShapes collection (DrawPage or GroupShape)."""
        from plugin.draw.form_fields import annotate_paper_form_nodes, is_control_shape_type, snapshot_control

        tree = []
        try:
            count = xshapes.getCount()
        except Exception:
            return tree

        for i in range(count):
            try:
                shape = xshapes.getByIndex(i)
            except Exception:
                continue

            current_index = str(i) if base_index is None else f"{base_index}.{i}"

            try:
                shape_type = shape.getShapeType()
            except Exception:
                shape_type = "UnknownShape"

            node = {"type": shape_type.replace("com.sun.star.drawing.", "")}

            if base_index is None:
                node["index"] = i
            else:
                node["path_index"] = current_index

            try:
                name = getattr(shape, "Name", "")
                if name:
                    node["name"] = name
            except Exception:
                pass

            if is_control_shape_type(str(shape_type)):
                try:
                    node["control"] = snapshot_control(shape.Control)
                    # Name on the widget is the stable fill key when the drawing Name is empty.
                    if not node.get("name") and node["control"].get("name"):
                        node["name"] = node["control"]["name"]
                except Exception:
                    node["control"] = {"type": "unknown", "name": ""}

            try:
                if hasattr(shape, "getString"):
                    text = shape.getString().strip()
                    if text:
                        node["text"] = text
            except Exception:
                pass

            try:
                desc = getattr(shape, "Description", "")
                if desc:
                    node["alt_description"] = desc
                title = getattr(shape, "Title", "")
                if title:
                    node["alt_title"] = title
            except Exception:
                pass

            try:
                pos = shape.getPosition()
                size = shape.getSize()
                node["geometry"] = {"x": pos.X, "y": pos.Y, "width": size.Width, "height": size.Height}
            except Exception:
                pass

            if "ConnectorShape" in shape_type:
                try:
                    start_shape = shape.getPropertyValue("StartShape")
                    if start_shape:
                        s_name = getattr(start_shape, "Name", "")
                        s_text = start_shape.getString().strip() if hasattr(start_shape, "getString") else ""
                        node["connected_start"] = {"name": s_name, "text": s_text}
                except Exception:
                    pass
                try:
                    end_shape = shape.getPropertyValue("EndShape")
                    if end_shape:
                        e_name = getattr(end_shape, "Name", "")
                        e_text = end_shape.getString().strip() if hasattr(end_shape, "getString") else ""
                        node["connected_end"] = {"name": e_name, "text": e_text}
                except Exception:
                    pass

            style = {}
            for prop in ["FillColor", "LineColor", "ZOrder", "RotateAngle", "LineWidth"]:
                try:
                    val = shape.getPropertyValue(prop)
                    if val is not None:
                        if prop in ["FillColor", "LineColor"] and isinstance(val, int) and val != -1:
                            style[prop] = f"#{val:06X}"
                        else:
                            style[prop] = val
                except Exception:
                    pass

            try:
                geom = shape.getPropertyValue("CustomShapeGeometry")
                if geom:
                    for p in geom:
                        if p.Name == "Type":
                            node["custom_shape_type"] = p.Value
            except Exception:
                pass

            if style:
                node["style"] = style

            if "GroupShape" in shape_type:
                node["children"] = self._build_shape_tree(shape, current_index)

            tree.append(node)

        # Sibling-level blank/fillable + left/above label_hint (see form_fields.annotate_paper_form_nodes).
        annotate_paper_form_nodes(tree)
        return tree

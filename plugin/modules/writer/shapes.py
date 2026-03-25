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
"""Writer shape drawing tools, bridging Draw's implementations."""

import logging
from plugin.modules.writer.base import ToolWriterShapeBase
from plugin.modules.draw.shapes import CreateShape as DrawCreateShape
from plugin.modules.draw.shapes import EditShape as DrawEditShape
from plugin.modules.draw.shapes import DeleteShape as DrawDeleteShape
from plugin.modules.draw.shapes import GetDrawSummary as DrawGetDrawSummary

log = logging.getLogger("writeragent.writer")


# 1. Inherit from the Draw tool implementation.
# 2. Inherit from the specialized ToolWriterShapeBase to enforce Writer scoping.
# 3. Explicitly override `uno_services` to allow Writer documents.

class CreateShape(DrawCreateShape, ToolWriterShapeBase):
    name = "create_shape"
    uno_services = ["com.sun.star.text.TextDocument"]

class EditShape(DrawEditShape, ToolWriterShapeBase):
    name = "edit_shape"
    uno_services = ["com.sun.star.text.TextDocument"]

class DeleteShape(DrawDeleteShape, ToolWriterShapeBase):
    name = "delete_shape"
    uno_services = ["com.sun.star.text.TextDocument"]

class GetDrawSummary(DrawGetDrawSummary, ToolWriterShapeBase):
    name = "get_draw_summary"
    uno_services = ["com.sun.star.text.TextDocument"]


# And here are the Writer specific ones (WIP placeholders) that Draw didn't have:

class ConnectShapes(ToolWriterShapeBase):
    """Connect two shapes with a connector."""

    name = "shapes_connect"
    intent = "edit"
    description = "Draw a connector line between two existing shapes."
    parameters = {
        "type": "object",
        "properties": {
            "start_shape": {
                "type": "string",
                "description": "Name of the starting shape.",
            },
            "end_shape": {
                "type": "string",
                "description": "Name of the ending shape.",
            },
        },
        "required": ["start_shape", "end_shape"],
    }
    uno_services = ["com.sun.star.text.TextDocument"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "message": f"WIP: Connected '{kwargs.get('start_shape')}' to '{kwargs.get('end_shape')}'."}


class GroupShapes(ToolWriterShapeBase):
    """Group multiple shapes together."""

    name = "shapes_group"
    intent = "edit"
    description = "Group several drawing shapes into a single group object."
    parameters = {
        "type": "object",
        "properties": {
            "shape_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of shape names to group.",
            },
            "group_name": {
                "type": "string",
                "description": "Name for the new group shape.",
            },
        },
        "required": ["shape_names"],
    }
    uno_services = ["com.sun.star.text.TextDocument"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "message": f"WIP: Grouped shapes: {kwargs.get('shape_names')}."}

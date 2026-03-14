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
"""Hermes agent backend adapter. Keeps one long-lived Hermes CLI process; each Send writes to
stdin and streams the next response. Conversation context is preserved across messages.

We never close stdin (or the PTY write side)—closing it would signal EOF and cause Hermes to exit.
Only stop() terminates the process; between messages the process stays running with stdin open.

Expects Hermes to be configured with WriterAgent's MCP server in ~/.hermes/config.yaml.
"""

import re
from plugin.modules.agent_backend.cli_backend import CLIProcessBackend, strip_ansi

_HERMES_PROMPT_CHAR = "\u276f"


class HermesBackend(CLIProcessBackend):
    backend_id = "hermes"
    display_name = "Hermes"

    def get_default_cmd(self):
        return "hermes"

    def is_ready_prompt(self, line):
        if not line or _HERMES_PROMPT_CHAR not in line:
            return False
        s = strip_ansi(line).strip()
        s = re.sub(r"[\s\u2500-\u257f\-]+", "", s)
        return s == _HERMES_PROMPT_CHAR

    def is_end_of_response(self, line):
        # Hermes usually ends its response with the prompt char again, or "Goodbye"
        return self.is_ready_prompt(line) or "Goodbye" in line

    def format_input(self, user_message, document_context, document_url, system_prompt, selection_text, mcp_url=None, **kwargs):
        parts = []
        if document_url:
            parts.append(f"Current Document URL: {document_url}\n")
        if mcp_url:
            parts.append(f"WriterAgent MCP Server: {mcp_url}\n")
        if document_context:
            parts.append("\nExcerpt of document context (for quick reference):\n")
            parts.append(document_context)
            parts.append("\n\n")
        if system_prompt:
            parts.append("Instructions:\n\n")
            parts.append(system_prompt)
            parts.append("\n\n")
        parts.append("User: ")
        parts.append(user_message)
        parts.append("\n")
        return "".join(parts)

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
"""Gemini CLI launcher provider."""

import os
import json

from .base import BaseProvider


class GeminiProvider(BaseProvider):
    name = "gemini"
    label = "Gemini CLI"
    binary_name = "gemini"
    install_url = "https://github.com/google-gemini/gemini-cli"

    def setup_env(self, cwd, mcp_url):
        env = super().setup_env(cwd, mcp_url)
        settings = {"mcp_url": mcp_url}
        with open(os.path.join(cwd, "settings.json"), "w") as f:
            json.dump(settings, f, indent=2)
        return env

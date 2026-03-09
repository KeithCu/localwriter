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
"""Hermes Agent launcher provider."""

import os

from .base import BaseProvider


class HermesProvider(BaseProvider):
    name = "hermes"
    label = "Hermes Agent"
    binary_name = "hermes-agent"
    install_url = "https://github.com/project-hermes/hermes-agent"

    def setup_env(self, cwd, mcp_url):
        env = super().setup_env(cwd, mcp_url)
        hermes_home = self._find_hermes_home(cwd)
        if hermes_home:
            env["HERMES_HOME"] = hermes_home
            self._update_hermes_config(hermes_home, mcp_url)
        return env

    def _find_hermes_home(self, cwd):
        search_dirs = [cwd, os.path.dirname(cwd), os.path.expanduser("~/.hermes")]
        for d in search_dirs:
            if os.path.isdir(os.path.join(d, "config")):
                return d
        return None

    def _update_hermes_config(self, home, mcp_url):
        # Simplified: user manages main config; we just provide env.
        pass

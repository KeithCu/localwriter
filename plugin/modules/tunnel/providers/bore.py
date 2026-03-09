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
"""Bore tunnel provider — bore.pub relay."""

import logging

log = logging.getLogger("writeragent.tunnel.bore")


class BoreProvider:
    """Bore tunnel: exposes a local port via a bore relay server."""

    name = "bore"
    binary_name = "bore"
    version_args = ["bore", "--version"]
    install_url = "https://github.com/ekzhang/bore/releases"

    def build_command(self, port, scheme, config):
        server = config.get("server", "bore.pub")
        cmd = ["bore", "local", str(port), "--to", server]
        # bore outputs "listening at <host>:<port>"
        url_regex = r"listening at ([\w.\-]+:\d+)"
        return cmd, url_regex

    def parse_line(self, line):
        return None

    def pre_start(self, config):
        pass

    def post_stop(self, config):
        pass

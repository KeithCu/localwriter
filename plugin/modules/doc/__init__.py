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
"""Common tools and diagnostics module."""

import logging
from plugin.framework.module_base import ModuleBase

log = logging.getLogger("writeragent.doc")


class CommonModule(ModuleBase):
    """Provides generic document tools and debug diagnostics."""

    def initialize(self, services):
        self._services = services

    def on_action(self, action):
        cfg = self._services.config.proxy_for(self.name)
        if action == "debug_info":
            if not cfg.get("debug_enabled"):
                from plugin.framework.uno_context import get_ctx
                from plugin.framework.dialogs import msgbox
                msgbox(get_ctx(), "Debug",
                       "Enable debug in Options > WriterAgent > Common")
                return
            self._show_debug_info()
        else:
            super().on_action(action)

    def _show_debug_info(self):
        """Show system info in a message box."""
        from plugin.framework.uno_context import get_ctx
        from plugin.framework.dialogs import msgbox
        from plugin.version import EXTENSION_VERSION

        ctx = get_ctx()
        lines = ["WriterAgent v%s" % EXTENSION_VERSION, ""]

        # Registered services
        svc_names = sorted(self._services.list_services())
        lines.append("Services: %s" % ", ".join(svc_names))

        # Document info
        doc_svc = self._services.get("document")
        if doc_svc:
            doc = doc_svc.get_active_document()
            if doc:
                doc_type = doc_svc.detect_doc_type(doc) or "unknown"
                doc_len = doc_svc.get_document_length(doc)
                lines.append("")
                lines.append("Document: %s (%d chars)" % (doc_type, doc_len))

        msgbox(ctx, "WriterAgent Debug Info", "\n".join(lines))

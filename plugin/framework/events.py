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
"""EventBusService — wraps the framework EventBus as a named service."""

from plugin.framework.event_bus import EventBus, global_event_bus
from plugin.framework.service_base import ServiceBase


class EventBusService(ServiceBase, EventBus):
    """Singleton event bus exposed as a service.

    Inherits from both ServiceBase (for registry) and EventBus (for
    pub/sub). Modules access it as ``services.events``.
    """

    name = "events"

    def __init__(self):
        ServiceBase.__init__(self)
        self._subscribers = global_event_bus._subscribers

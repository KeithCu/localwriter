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
"""Homer Simpson dummy LLM provider — always answers D'oh!"""

import time
import logging

from plugin.modules.ai.provider_base import LlmProvider

log = logging.getLogger("writeragent.ai_dummy")

_RESPONSE = "D'oh!"


class HomerProvider(LlmProvider):
    """Fake LLM that streams 'D'oh!' one character at a time."""

    name = "ai_dummy"

    def __init__(self, config):
        self._config = config

    def stream(self, messages, tools=None, **kwargs):
        delay = (self._config.get("delay") or 50) / 1000.0
        for ch in _RESPONSE:
            if delay > 0:
                time.sleep(delay)
            yield {
                "content": ch,
                "thinking": "",
                "delta": {"content": ch},
                "finish_reason": None,
            }
        yield {
            "content": "",
            "thinking": "",
            "delta": {},
            "finish_reason": "stop",
        }

    def complete(self, messages, tools=None, **kwargs):
        delay = (self._config.get("delay") or 50) / 1000.0
        if delay > 0:
            time.sleep(delay * len(_RESPONSE))
        return {
            "content": _RESPONSE,
            "tool_calls": None,
            "finish_reason": "stop",
        }

    def supports_tools(self):
        return False

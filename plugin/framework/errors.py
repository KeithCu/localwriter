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
"""Centralized exception classes and error formatting for WriterAgent."""

class WriterAgentException(Exception):
    """Base exception for all custom WriterAgent errors."""
    def __init__(self, message, code="UNKNOWN_ERROR", details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ToolExecutionError(WriterAgentException):
    """Raised when a tool fails to execute properly."""
    def __init__(self, message, details=None):
        super().__init__(message, code="TOOL_EXECUTION_ERROR", details=details)


class NetworkError(WriterAgentException):
    """Raised when a network request fails."""
    def __init__(self, message, details=None):
        super().__init__(message, code="NETWORK_ERROR", details=details)


class ConfigError(WriterAgentException):
    """Raised when there is a configuration issue."""
    def __init__(self, message, details=None):
        super().__init__(message, code="CONFIG_ERROR", details=details)


class UnoObjectError(WriterAgentException):
    """Raised when interacting with LibreOffice UNO objects fails."""
    def __init__(self, message, details=None):
        super().__init__(message, code="UNO_OBJECT_ERROR", details=details)


def format_error_payload(e: Exception) -> dict:
    """Format an exception into the standard JSON error payload schema."""
    if isinstance(e, WriterAgentException):
        payload = {
            "status": "error",
            "code": e.code,
            "message": e.message,
        }
        if e.details:
            payload["details"] = e.details
        return payload

    # For unexpected exceptions
    return {
        "status": "error",
        "code": "INTERNAL_ERROR",
        "message": str(e),
        "details": {
            "type": type(e).__name__
        }
    }

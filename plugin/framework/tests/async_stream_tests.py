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
import os
import sys
import unittest
import queue

# Add project root to sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from unittest.mock import MagicMock
from plugin.framework.async_stream import run_stream_drain_loop

class TestAsyncStream(unittest.TestCase):
    def test_drain_loop_basic(self):
        q = queue.Queue()
        toolkit = MagicMock()
        job_done = [False]
        chunks = []

        def apply_chunk(text, is_thinking=False):
            chunks.append((text, is_thinking))

        def on_stream_done(data):
            return True

        # Put some items in the queue
        q.put(("thinking", "I am thinking"))
        q.put(("chunk", "Hello world"))
        q.put(("stream_done", {"status": "ok"}))

        # Run the loop
        run_stream_drain_loop(
            q, toolkit, job_done, apply_chunk, 
            on_stream_done, MagicMock(), MagicMock()
        )

        # Verify thinking block was wrapped correctly
        self.assertEqual(chunks[0], ("[Thinking] ", True))
        self.assertEqual(chunks[1], ("I am thinking", True))
        # Content chunk should close thinking
        self.assertEqual(chunks[2], (" /thinking\n", True))
        self.assertEqual(chunks[3], ("Hello world", False))
        self.assertTrue(job_done[0])

    def test_drain_loop_error(self):
        q = queue.Queue()
        toolkit = MagicMock()
        job_done = [False]
        errors = []

        def on_error(e):
            errors.append(e)

        q.put(("error", "Something went wrong"))

        run_stream_drain_loop(
            q, toolkit, job_done, MagicMock(), 
            MagicMock(), MagicMock(), on_error
        )

        self.assertEqual(errors[0], "Something went wrong")
        self.assertTrue(job_done[0])

    def test_drain_loop_stopped(self):
        q = queue.Queue()
        toolkit = MagicMock()
        job_done = [False]
        stopped_called = [False]

        def on_stopped():
            stopped_called[0] = True

        q.put(("stopped",))

        run_stream_drain_loop(
            q, toolkit, job_done, MagicMock(), 
            MagicMock(), on_stopped, MagicMock()
        )

        self.assertTrue(stopped_called[0])
        self.assertTrue(job_done[0])

if __name__ == "__main__":
    unittest.main()

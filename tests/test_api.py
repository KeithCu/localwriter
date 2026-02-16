"""
Test suite for LocalWriter LlmClient (core.api).
Tests core/api.py logic by mocking context/config.

Run: pytest tests/test_api.py -v
"""

import json
import ssl
import threading
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest

import sys
import unittest.mock

# Mock 'uno' module BEFORE importing core modules
if "uno" not in sys.modules:
    sys.modules["uno"] = unittest.mock.MagicMock()
    sys.modules["uno"].fileUrlToSystemPath = lambda x: x.replace("file://", "")

try:
    from core.api import LlmClient
    from core.config import as_bool
except ImportError:
    import os
    # Ensure we can import if running from root without proper pythonpath
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from core.api import LlmClient
    from core.config import as_bool


# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------

class MockServiceManager:
    def createInstanceWithContext(self, name, ctx):
        return None  # For Toolkit, PathSettings, etc.

class MockContext:
    def getServiceManager(self):
        return MockServiceManager()

# ---------------------------------------------------------------------------
# Mock SSE Server
# ---------------------------------------------------------------------------

class SSEHandler(BaseHTTPRequestHandler):
    """Mock SSE server handler. Subclasses set chunks and captured_requests."""
    chunks = []
    captured_requests = []

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        # Some clients might send empty body?
        parsed = json.loads(body) if body else {}

        self.__class__.captured_requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": parsed,
        })

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        for chunk_line in self.__class__.chunks:
            self.wfile.write(chunk_line.encode("utf-8") + b"\n\n")
            self.wfile.flush()

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, format, *args):
        pass  # suppress console noise


class ErrorHandler(BaseHTTPRequestHandler):
    """Returns HTTP 500 for error handling tests."""
    def do_POST(self):
        self.send_response(500)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Internal Server Error")

    def log_message(self, format, *args):
        pass


def start_mock_server(handler_class):
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    port = server.server_address[1]
    return server, port


COMPLETIONS_CHUNKS = [
    'data: {"choices":[{"text":"Once ","finish_reason":null}]}',
    'data: {"choices":[{"text":"upon ","finish_reason":null}]}',
    'data: {"choices":[{"text":"a time","finish_reason":"stop"}]}',
]

CHAT_CHUNKS = [
    'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
    'data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}',
    'data: {"choices":[{"delta":{"content":"!"},"finish_reason":"stop"}]}',
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_completions_server():
    class Handler(SSEHandler):
        chunks = list(COMPLETIONS_CHUNKS)
        captured_requests = []
    server, port = start_mock_server(Handler)
    yield Handler, port
    server.shutdown()


@pytest.fixture
def mock_chat_server():
    class Handler(SSEHandler):
        chunks = list(CHAT_CHUNKS)
        captured_requests = []
    server, port = start_mock_server(Handler)
    yield Handler, port
    server.shutdown()


@pytest.fixture
def mock_error_server():
    server, port = start_mock_server(ErrorHandler)
    yield port
    server.shutdown()


# ---------------------------------------------------------------------------
# Helper to run stream via LlmClient
# ---------------------------------------------------------------------------

def do_stream(server_port, api_type="completions", api_key="",
              is_openwebui=False, openai_compatible=False,
              prompt="Hello", system_prompt="", max_tokens=70, model="test-model"):
    
    endpoint = f"http://127.0.0.1:{server_port}"
    
    config = {
        "endpoint": endpoint,
        "api_key": api_key,
        "api_type": api_type,
        "model": model,
        "is_openwebui": is_openwebui,
        "openai_compatibility": openai_compatible,
        "temperature": 0.5,
        "seed": "",
        "request_timeout": 10
    }
    
    ctx = MockContext()
    client = LlmClient(config, ctx)
    
    accumulated = []
    
    # We use stream_completion which builds the request internally
    # But wait, stream_completion calls stream_request.
    # To capture requests easily, we can rely on the server side capture.
    
    client.stream_completion(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        api_type=api_type,
        append_callback=accumulated.append,
        dispatch_events=False # Don't try to use UNO toolkit
    )
    
    return "".join(accumulated)


# ---------------------------------------------------------------------------
# Unit Tests — as_bool
# ---------------------------------------------------------------------------

class TestAsBool:

    @pytest.mark.parametrize("value", [True])
    def test_bool_true(self, value):
        assert as_bool(value) is True

    @pytest.mark.parametrize("value", [False])
    def test_bool_false(self, value):
        assert as_bool(value) is False

    @pytest.mark.parametrize("value", ["true", "TRUE", "True", "1", "yes", "on"])
    def test_string_true_variants(self, value):
        assert as_bool(value) is True

    @pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off", "random", ""])
    def test_string_false_variants(self, value):
        assert as_bool(value) is False


# ---------------------------------------------------------------------------
# Unit Tests — LlmClient.make_api_request (Build Logic)
# ---------------------------------------------------------------------------

class TestMakeApiRequest:

    def test_ollama_completions(self):
        config = {
            "endpoint": "http://localhost:11434",
            "api_type": "completions",
            "model": "llama2",
            "seed": "123"
        }
        client = LlmClient(config, MockContext())
        req = client.make_api_request("Hello")
        
        assert req.full_url == "http://localhost:11434/v1/completions"
        body = json.loads(req.data)
        assert "prompt" in body
        assert "messages" not in body
        assert body["model"] == "llama2"
        assert body["seed"] == 123
        assert body["stream"] is True

    def test_openai_chat(self):
        config = {
            "endpoint": "https://api.openai.com",
            "api_key": "sk-test-key",
            "api_type": "chat",
            "model": "gpt-4",
            "openai_compatibility": True
        }
        client = LlmClient(config, MockContext())
        req = client.make_api_request("Hello", system_prompt="Sys")

        assert req.full_url == "https://api.openai.com/v1/chat/completions"
        body = json.loads(req.data)
        assert "messages" in body
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == "Sys"
        assert "seed" not in body
        assert req.headers["Authorization"] == "Bearer sk-test-key"

    def test_openwebui_chat(self):
        config = {
            "endpoint": "http://localhost:3000",
            "api_type": "chat",
            "is_openwebui": True
        }
        client = LlmClient(config, MockContext())
        req = client.make_api_request("Hello")

        assert req.full_url == "http://localhost:3000/api/chat/completions"


# ---------------------------------------------------------------------------
# Unit Tests — LlmClient.extract_content_from_response
# ---------------------------------------------------------------------------

class TestExtractContent:
    
    def setup_method(self):
        self.client = LlmClient({}, MockContext())

    def test_completions_text(self):
        chunk = {"choices": [{"text": "Hello", "finish_reason": None}]}
        content, reason, thinking, delta = self.client.extract_content_from_response(chunk, "completions")
        assert content == "Hello"
        assert reason is None

    def test_chat_content(self):
        chunk = {"choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]}
        content, reason, thinking, delta = self.client.extract_content_from_response(chunk, "chat")
        assert content == "Hello"
        assert reason is None

    def test_thinking_extraction(self):
        # DeepSeek style
        chunk = {"choices": [{"delta": {"reasoning_content": "Hmm..."}, "finish_reason": None}]}
        content, reason, thinking, delta = self.client.extract_content_from_response(chunk, "chat")
        assert thinking == "Hmm..."
        assert content == ""


# ---------------------------------------------------------------------------
# Integration Tests — Streaming
# ---------------------------------------------------------------------------

class TestStreamOllama:

    def test_accumulated_text(self, mock_completions_server):
        handler, port = mock_completions_server
        text = do_stream(port, api_type="completions")
        assert text == "Once upon a time"
        
        # Verify request details captured by server
        req = handler.captured_requests[0]
        assert req["path"] == "/v1/completions"
        assert req["body"]["model"] == "test-model"

class TestStreamOpenAI:

    def test_accumulated_text(self, mock_chat_server):
        handler, port = mock_chat_server
        text = do_stream(port, api_type="chat", openai_compatible=True)
        assert text == "Hello world!"
        
        req = handler.captured_requests[0]
        assert req["path"] == "/v1/chat/completions"
        assert "messages" in req["body"]


class TestStreamErrors:

    def test_http_500(self, mock_error_server):
        port = mock_error_server
        try:
            do_stream(port)
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Server error (500)" in str(e) or "HTTP Error 500" in str(e)

    def test_connection_refused(self):
        # Port 1 is likely closed
        try:
            do_stream(1)
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Connection Refused" in str(e) or "Connection Error" in str(e)

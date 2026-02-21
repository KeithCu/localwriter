# Port utilities and HTTP server structure adapted from the LibreOffice MCP
# Extension (in-repo: libreoffice-mcp-extension/). See registration.py (port
# helpers) and pythonpath/ai_interface.py (server/handler). We're grateful for
# their work; when maintaining this module, check that directory for updates.
"""
MCP HTTP server for LocalWriter. Exposes Writer/Calc/Draw tools to external AI
clients. Document targeting via X-Document-URL header; all UNO work runs on
main thread via core.mcp_thread.
"""
import json
import os
import socket as _socket
import subprocess as _subprocess
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

from core.mcp_thread import execute_on_main_thread
from core.document import is_calc, is_draw, is_writer

# Health response body must contain this so _probe_health identifies our server
MCP_HEALTH_SIGNATURE = "LocalWriter MCP"


def _resolve_document(ctx, doc_url_header):
    """
    Resolve target document from X-Document-URL header. Runs on main thread.
    Returns (doc, type_str) where type_str is "writer"|"calc"|"draw", or (None, None).
    """
    smgr = ctx.getServiceManager()
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    if not doc_url_header or not str(doc_url_header).strip():
        doc = desktop.getCurrentComponent()
        if doc is None:
            return None, None
        if is_calc(doc):
            return doc, "calc"
        if is_draw(doc):
            return doc, "draw"
        return doc, "writer"

    want = urllib.parse.unquote(str(doc_url_header).strip()).lower().rstrip("/")
    try:
        components = desktop.getComponents()
        enum = components.createEnumeration()
        while enum.hasMoreElements():
            doc = enum.nextElement()
            try:
                if not hasattr(doc, "getURL"):
                    continue
                url = doc.getURL()
                if not url:
                    continue
                candidate = urllib.parse.unquote(url).lower().rstrip("/")
                if candidate == want:
                    if is_calc(doc):
                        return doc, "calc"
                    if is_draw(doc):
                        return doc, "draw"
                    return doc, "writer"
            except Exception:
                continue
    except Exception:
        pass
    return None, None


def _get_tools_for_doc(doc, doc_type):
    """Return the tool list for the given document type. Main thread."""
    if doc_type == "calc":
        from core.calc_tools import CALC_TOOLS
        return CALC_TOOLS
    if doc_type == "draw":
        from core.draw_tools import DRAW_TOOLS
        return DRAW_TOOLS
    from core.document_tools import WRITER_TOOLS
    return WRITER_TOOLS


def _probe_health(host, port, timeout=2):
    """Probe /health endpoint. Returns True if our server responds."""
    try:
        import http.client
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        conn.close()
        return MCP_HEALTH_SIGNATURE in body
    except Exception:
        return False


def _is_port_bound(host, port, timeout=1):
    """Returns True if anything is listening on host:port."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def _get_pids_on_port(port):
    """Get PIDs of processes listening on the port (Windows)."""
    pids = set()
    try:
        result = _subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(_subprocess, "CREATE_NO_WINDOW", 0),
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit():
                    pids.add(int(pid))
    except Exception:
        pass
    return pids


def _kill_zombies_on_port(host, port):
    """Kill processes bound to the port that aren't our server (Windows).
    On Linux just verifies the port is free. Safe to call on all platforms."""
    if not _is_port_bound(host, port):
        return True
    if _probe_health(host, port):
        return False  # our server already there
    # Windows: try to kill zombies
    if os.name == "nt":
        pids = _get_pids_on_port(port)
        my_pid = os.getpid()
        for pid in pids:
            if pid == my_pid:
                continue
            try:
                _subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                    creationflags=getattr(_subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
        import time
        time.sleep(1)
    return not _is_port_bound(host, port)


class MCPHandler(BaseHTTPRequestHandler):
    ctx = None  # set at class level before server starts

    def _respond(self, code, body):
        if isinstance(body, dict):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Document-URL")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "name": MCP_HEALTH_SIGNATURE})
            return
        if self.path in ("/", "/tools", "/documents"):
            doc_url = self.headers.get("X-Document-URL") or None

            def _run():
                doc, doc_type = _resolve_document(self.ctx, doc_url)
                if self.path == "/documents":
                    # List all open documents
                    smgr = self.ctx.getServiceManager()
                    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
                    out = []
                    try:
                        components = desktop.getComponents()
                        enum = components.createEnumeration()
                        while enum.hasMoreElements():
                            d = enum.nextElement()
                            try:
                                url = d.getURL() if hasattr(d, "getURL") else ""
                                t = "calc" if is_calc(d) else "draw" if is_draw(d) else "writer"
                                out.append({"url": url or "", "type": t})
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return {"documents": out}

                if doc is None:
                    return {"error": "no document", "message": "No document found. Open a document or set X-Document-URL."}
                if self.path == "/":
                    from core.constants import get_chat_system_prompt_for_document
                    instructions = get_chat_system_prompt_for_document(doc)
                    return {"name": "LocalWriter", "instructions": instructions, "tools_count": len(_get_tools_for_doc(doc, doc_type))}
                # /tools
                tools = _get_tools_for_doc(doc, doc_type)
                return {"tools": tools, "count": len(tools)}

            try:
                result = execute_on_main_thread(_run, timeout=10.0)
                self._respond(200, result)
            except TimeoutError:
                self._respond(504, {"status": "error", "message": "timeout"})
            except Exception as e:
                self._respond(500, {"status": "error", "message": str(e)})
            return
        self._respond(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        path = self.path.rstrip("/")
        tool_name = path[7:] if path.startswith("/tools/") else body.get("tool")
        if not tool_name:
            self._respond(400, {"status": "error", "message": "missing tool name"})
            return
        doc_url = self.headers.get("X-Document-URL") or None

        def _run():
            from core.calc_bridge import CalcBridge
            from core.draw_bridge import DrawBridge
            doc, doc_type = _resolve_document(self.ctx, doc_url)
            if doc is None:
                return json.dumps({"status": "error", "message": "No document found. Open a document or set X-Document-URL."})
            if doc_type == "calc":
                from core.calc_tools import execute_calc_tool
                return execute_calc_tool(tool_name, body, doc, self.ctx)
            if doc_type == "draw":
                from core.draw_tools import execute_draw_tool
                return execute_draw_tool(tool_name, body, doc, self.ctx, status_callback=None)
            from core.document_tools import execute_tool
            return execute_tool(tool_name, body, doc, self.ctx)

        try:
            result = execute_on_main_thread(_run, timeout=30.0)
            self._respond(200, result if isinstance(result, str) else json.dumps(result))
        except TimeoutError:
            self._respond(504, {"status": "error", "message": "timeout"})
        except Exception as e:
            self._respond(500, {"status": "error", "message": str(e)})


class MCPHttpServer:
    def __init__(self, ctx, port=8765):
        MCPHandler.ctx = ctx
        self._ctx = ctx
        self._port = port
        self._server = HTTPServer(("localhost", port), MCPHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()

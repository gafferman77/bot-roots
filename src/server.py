"""
Mini servidor HTTP que expone los datos del bot via API REST.
Corre en un thread separado junto al bot principal.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent / "logs"


class BotHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            self._serve_file(LOGS_DIR / "status.json")
        elif self.path == "/trades":
            self._serve_trades()
        elif self.path == "/health":
            self._respond(200, b"OK", "text/plain")
        else:
            self._respond(404, b"Not found", "text/plain")

    def _serve_file(self, path: Path):
        if not path.exists():
            self._respond(404, b"{}", "application/json")
            return
        data = path.read_bytes()
        self._respond(200, data, "application/json")

    def _serve_trades(self):
        path = LOGS_DIR / "trades.jsonl"
        if not path.exists():
            self._respond(200, b"[]", "application/json")
            return
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        trades = []
        for line in lines:
            try:
                trades.append(json.loads(line))
            except Exception:
                pass
        self._respond(200, json.dumps(trades).encode(), "application/json")

    def _respond(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silenciar logs HTTP en consola


def start_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), BotHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

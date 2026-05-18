"""
Mini servidor HTTP que expone los datos del bot via API REST.
El status se mantiene en memoria para compatibilidad con Render free tier.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Estado compartido en memoria
_status: dict = {}
_trades: list = []
_lock = threading.Lock()


def update_status(data: dict) -> None:
    with _lock:
        _status.clear()
        _status.update(data)


def append_trade(trade: dict) -> None:
    with _lock:
        _trades.append(trade)


def get_status() -> dict:
    with _lock:
        return dict(_status)


def get_trades() -> list:
    with _lock:
        return list(_trades)


class BotHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            body = json.dumps(get_status()).encode()
            self._respond(200, body, "application/json")
        elif self.path == "/trades":
            body = json.dumps(get_trades()).encode()
            self._respond(200, body, "application/json")
        elif self.path == "/health":
            self._respond(200, b"OK", "text/plain")
        else:
            self._respond(404, b"Not found", "text/plain")

    def _respond(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), BotHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

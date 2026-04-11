import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from presentation.http.handlers.expense_api_handler import ExpenseAPIHandler

logger = logging.getLogger(__name__)

_expense_endpoint_handler = None


def set_expense_endpoint_handler(handler):
    global _expense_endpoint_handler
    _expense_endpoint_handler = handler


def get_http_api_router():
    return HTTPAPIRouter(_expense_endpoint_handler)


class HTTPAPIRouter:
    def __init__(self, endpoint_handler):
        self.endpoint_handler = endpoint_handler

    def route(self, method: str, path: str, headers: dict, body: bytes) -> tuple[int, dict, dict]:
        if path != "/api/v1/expenses/text":
            return 404, {
                "status": "error",
                "error_code": "ROUTE_NOT_FOUND",
                "message": "The requested route does not exist.",
            }, {}

        if method != "POST":
            return 405, {
                "status": "error",
                "error_code": "METHOD_NOT_ALLOWED",
                "message": "This endpoint only accepts POST requests.",
            }, {"Allow": "POST"}

        if self.endpoint_handler is None:
            return 503, {
                "status": "error",
                "error_code": "HANDLER_NOT_CONFIGURED",
                "message": "The HTTP handler is not configured.",
            }, {}

        status_code, payload = self.endpoint_handler.handle_post(headers, body)
        return status_code, payload, {}


class _APIServerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        self._dispatch("POST", body)

    def do_GET(self):
        self._dispatch("GET", b"")

    def _dispatch(self, method: str, body: bytes):
        router = get_http_api_router()
        status_code, payload, extra_headers = router.route(
            method=method,
            path=self.path,
            headers=dict(self.headers.items()),
            body=body,
        )
        self._send_json(status_code, payload, extra_headers=extra_headers)

    def _send_json(self, status_code: int, payload: dict, extra_headers: dict | None = None):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        pass


def start_http_api_server(port: int = 8081):
    server = HTTPServer(("0.0.0.0", port), _APIServerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("HTTP API server running on port %s", port)


def configure_http_api(container):
    set_expense_endpoint_handler(ExpenseAPIHandler(container))

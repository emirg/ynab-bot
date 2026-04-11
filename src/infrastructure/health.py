import logging
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from presentation.http.server import get_http_api_router

logger = logging.getLogger(__name__)

_healthy = True
_oauth_service = None
_on_oauth_success = None

_SUCCESS_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>YNAB Bot</title></head>
<body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>Cuenta YNAB conectada</h1>
<p>Ya puedes cerrar esta ventana y volver a Telegram.</p>
</body></html>"""

_ERROR_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>YNAB Bot - Error</title></head>
<body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>Error al conectar</h1>
<p>{error}</p>
<p>Vuelve a intentar con /connect en Telegram.</p>
</body></html>"""


def route_health_request(method: str, path: str, headers: dict | None = None, body: bytes = b""):
    headers = headers or {}
    parsed = urlparse(path)

    if parsed.path.startswith("/api/v1/"):
        router = get_http_api_router()
        status, payload, extra_headers = router.route(
            method=method,
            path=parsed.path,
            headers=headers,
            body=body,
        )
        return status, "json", payload, extra_headers

    if method == "POST":
        return 404, "json", {
            "status": "error",
            "error_code": "ROUTE_NOT_FOUND",
            "message": "La ruta solicitada no existe.",
        }, {}

    if parsed.path == "/oauth/callback":
        return _route_oauth_callback(parsed)

    if _healthy:
        return 200, "bytes", b"ok", {}

    return 503, "bytes", b"unhealthy", {}


def set_healthy(value: bool):
    global _healthy
    _healthy = value


def set_oauth_service(service):
    global _oauth_service
    _oauth_service = service


def set_on_oauth_success(callback):
    global _on_oauth_success
    _on_oauth_success = callback


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._dispatch("GET", b"")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        self._dispatch("POST", body)

    def _dispatch(self, method: str, body: bytes):
        status, response_type, payload, extra_headers = route_health_request(
            method=method,
            path=self.path,
            headers=dict(self.headers.items()),
            body=body,
        )
        if response_type == "json":
            self._send_json(status, payload, extra_headers)
        elif response_type == "html":
            self._send_html(status, payload)
        else:
            self.send_response(status)
            self.end_headers()
            self.wfile.write(payload)

    def _send_html(self, status, html):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _send_json(self, status, payload, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):
        pass  # Silence request logs


def _route_oauth_callback(parsed):
    params = parse_qs(parsed.query)
    code = params.get("code", [None])[0]
    state = params.get("state", [None])[0]

    if not code or not state:
        return 400, "html", _ERROR_HTML.format(error="Parámetros faltantes en la solicitud."), {}

    if _oauth_service is None:
        return 503, "html", _ERROR_HTML.format(error="Servicio OAuth no disponible."), {}

    try:
        user_config = _oauth_service.exchange_code_for_tokens(code, state)

        if _on_oauth_success:
            try:
                _on_oauth_success(user_config.telegram_id)
            except Exception as e:
                logger.error(f"Error in on_oauth_success callback: {e}")

        return 200, "html", _SUCCESS_HTML, {}
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return 400, "html", _ERROR_HTML.format(error=str(e)), {}


def start_health_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check server running on port {port}")

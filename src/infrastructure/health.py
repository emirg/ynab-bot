import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

_healthy = True
_oauth_service = None

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


def set_healthy(value: bool):
    global _healthy
    _healthy = value


def set_oauth_service(service):
    global _oauth_service
    _oauth_service = service


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/oauth/callback":
            self._handle_oauth_callback(parsed)
        elif _healthy:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"unhealthy")

    def _handle_oauth_callback(self, parsed):
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        if not code or not state:
            self._send_html(400, _ERROR_HTML.format(error="Parámetros faltantes en la solicitud."))
            return

        if _oauth_service is None:
            self._send_html(503, _ERROR_HTML.format(error="Servicio OAuth no disponible."))
            return

        try:
            _oauth_service.exchange_code_for_tokens(code, state)
            self._send_html(200, _SUCCESS_HTML)
        except Exception as e:
            logger.error(f"OAuth callback error: {e}")
            self._send_html(400, _ERROR_HTML.format(error=str(e)))

    def _send_html(self, status, html):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass  # Silence request logs


def start_health_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check server running on port {port}")

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)

_healthy = True


def set_healthy(value: bool):
    global _healthy
    _healthy = value


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if _healthy:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"unhealthy")

    def log_message(self, format, *args):
        pass  # Silence request logs


def start_health_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check server running on port {port}")

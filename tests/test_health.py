import urllib.request

from infrastructure.health import start_health_server, set_healthy

_PORT = 18080
start_health_server(_PORT)


class TestHealthServer:
    def _get(self):
        req = urllib.request.Request(f"http://127.0.0.1:{_PORT}/")
        try:
            resp = urllib.request.urlopen(req)
            return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_healthy_returns_200(self):
        set_healthy(True)
        status, body = self._get()
        assert status == 200
        assert body == b"ok"

    def test_unhealthy_returns_503(self):
        set_healthy(False)
        status, body = self._get()
        assert status == 503
        assert body == b"unhealthy"
        set_healthy(True)

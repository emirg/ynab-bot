import urllib.request
from unittest.mock import MagicMock

from infrastructure.health import (
    start_health_server, set_healthy, set_oauth_service, set_on_oauth_success
)
from domain.models.user import UserConfiguration, UserStatus

_PORT = 18080
start_health_server(_PORT)


def _get(path="/"):
    req = urllib.request.Request(f"http://127.0.0.1:{_PORT}{path}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        with e:
            return e.code, e.read()


class TestHealthServer:
    def test_healthy_returns_200(self):
        set_healthy(True)
        status, body = _get()
        assert status == 200
        assert body == b"ok"

    def test_unhealthy_returns_503(self):
        set_healthy(False)
        status, body = _get()
        assert status == 503
        assert body == b"unhealthy"
        set_healthy(True)


class TestOAuthCallback:
    def test_missing_params_returns_400(self):
        status, body = _get("/oauth/callback")
        assert status == 400
        assert b"faltantes" in body.lower() or "Parámetros".encode() in body

    def test_no_oauth_service_returns_503(self):
        set_oauth_service(None)
        status, body = _get("/oauth/callback?code=abc&state=123.sig")
        assert status == 503

    def test_successful_callback(self):
        mock_service = MagicMock()
        mock_service.exchange_code_for_tokens.return_value = UserConfiguration(
            telegram_id=1, status=UserStatus.AUTHORIZED
        )
        set_oauth_service(mock_service)
        
        # Setup callback mock
        mock_callback = MagicMock()
        set_on_oauth_success(mock_callback)
        
        status, body = _get("/oauth/callback?code=abc&state=123.sig")
        assert status == 200
        assert b"conectada" in body.lower()
        mock_service.exchange_code_for_tokens.assert_called_once_with("abc", "123.sig")
        
        # Verify callback was called with correct telegram_id
        mock_callback.assert_called_once_with(1)
        
        # Cleanup
        set_oauth_service(None)
        set_on_oauth_success(None)

    def test_exchange_error_returns_400(self):
        mock_service = MagicMock()
        mock_service.exchange_code_for_tokens.side_effect = Exception("invalid code")
        set_oauth_service(mock_service)
        status, body = _get("/oauth/callback?code=bad&state=123.sig")
        assert status == 400
        assert b"invalid code" in body
        set_oauth_service(None)

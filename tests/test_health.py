import json
from unittest.mock import MagicMock

from infrastructure.health import (
    route_health_request, set_healthy, set_oauth_service, set_on_oauth_success
)
from domain.models.user import UserConfiguration, UserStatus
from presentation.http.server import set_expense_endpoint_handler

def _get(path="/", headers=None):
    status, response_type, payload, _extra_headers = route_health_request(
        method="GET",
        path=path,
        headers=headers or {},
        body=b"",
    )
    if response_type == "html":
        return status, payload.encode()
    if response_type == "json":
        return status, json.dumps(payload).encode()
    return status, payload


def _post(path="/", payload=None, headers=None):
    status, response_type, response_payload, _extra_headers = route_health_request(
        method="POST",
        path=path,
        headers=headers or {"Content-Type": "application/json"},
        body=json.dumps(payload or {}).encode(),
    )
    if response_type == "html":
        return status, response_payload.encode()
    if response_type == "json":
        return status, json.dumps(response_payload).encode()
    return status, response_payload


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

    def test_api_route_delegates_on_same_public_server(self):
        mock_handler = MagicMock()
        mock_handler.handle_post.return_value = (
            200,
            {"status": "preview", "message": "ok"},
        )
        set_expense_endpoint_handler(mock_handler)

        status, body = _post(
            "/api/v1/expenses/text",
            payload={"telegram_user_id": 123, "text": "Gaste 25k en Carulla"},
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test",
            },
        )

        assert status == 200
        assert json.loads(body.decode())["status"] == "preview"
        mock_handler.handle_post.assert_called_once()


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

import json
from unittest.mock import MagicMock

from infrastructure.config.app_config import AppConfig
from infrastructure.health import route_health_request
from infrastructure.container import DIContainer
from presentation.http.server import configure_http_api


def _post(path, payload, auth="dev-api-key"):
    status, response_type, response_payload, _extra_headers = route_health_request(
        method="POST",
        path=path,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth}",
        },
        body=json.dumps(payload).encode("utf-8"),
    )
    assert response_type == "json"
    return status, response_payload


def _build_container(tmp_path):
    return DIContainer(
        AppConfig(
            telegram_token=None,
            openai_key=None,
            admin_ids=[1],
            ynab_client_id=None,
            ynab_client_secret=None,
            ynab_redirect_uri=None,
            token_encryption_key="aTULl7SBg8iYq9Kof_vgaC8GdG25-ryXic46AotyOQs=",
            http_api_key="dev-http-key",
            app_mode="http-dev",
            external_mode="stub",
            dev_api_key="dev-api-key",
            enable_dev_routes=True,
            database_path=str(tmp_path / "dev-harness.db"),
        )
    )


class TestDevAPIHandler:
    def test_bootstrap_and_simulate_text_message(self, tmp_path):
        container = _build_container(tmp_path)
        configure_http_api(container)

        status, payload = _post("/dev/bootstrap", {"telegram_user_id": 42})
        assert status == 200
        assert payload["status"] == "ok"
        assert payload["onboarding_step"] == "complete"

        status, payload = _post("/dev/messages/text", {"telegram_user_id": 42, "text": "Gaste 25k en Carulla"})
        assert status == 200
        assert payload["kind"] == "message"
        assert "Gasto registrado" in payload["message"]

    def test_simulate_start_command(self, tmp_path):
        container = _build_container(tmp_path)
        configure_http_api(container)
        _post("/dev/bootstrap", {"telegram_user_id": 7, "configured": False})

        status, payload = _post("/dev/messages/text", {"telegram_user_id": 7, "text": "/start"})
        assert status == 200
        assert payload["kind"] == "command"
        assert payload["command"] == "/start"

    def test_invalid_dev_token_is_rejected(self, tmp_path):
        container = _build_container(tmp_path)
        configure_http_api(container)

        status, payload = _post("/dev/bootstrap", {"telegram_user_id": 1}, auth="wrong")
        assert status == 401
        assert payload["error_code"] == "INVALID_API_KEY"

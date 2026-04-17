import json
from unittest.mock import MagicMock

from infrastructure.health import route_health_request, set_advisor_page_handler
from presentation.http.server import set_advisor_api_handler


def _get(path="/", headers=None):
    status, response_type, payload, extra_headers = route_health_request(
        method="GET",
        path=path,
        headers=headers or {},
        body=b"",
    )
    return status, response_type, payload, extra_headers


def _post(path="/", headers=None):
    status, response_type, payload, extra_headers = route_health_request(
        method="POST",
        path=path,
        headers=headers or {},
        body=b"",
    )
    return status, response_type, payload, extra_headers


def test_advisor_launch_route_delegates_to_page_handler():
    handler = MagicMock()
    handler.handle_launch.return_value = (302, "bytes", b"", {"Location": "/advisor"})
    set_advisor_page_handler(handler)

    status, response_type, payload, extra_headers = _get("/advisor/launch?token=abc")

    assert status == 302
    assert response_type == "bytes"
    assert extra_headers["Location"] == "/advisor"
    handler.handle_launch.assert_called_once_with("abc")
    set_advisor_page_handler(None)


def test_advisor_page_route_delegates_to_page_handler():
    handler = MagicMock()
    handler.handle_page.return_value = (200, "html", "<html>ok</html>", {})
    set_advisor_page_handler(handler)

    status, response_type, payload, _ = _get("/advisor", headers={"Cookie": "advisor_session=abc"})

    assert status == 200
    assert response_type == "html"
    assert payload == "<html>ok</html>"
    handler.handle_page.assert_called_once()
    set_advisor_page_handler(None)


def test_advisor_bootstrap_route_delegates_to_api_handler():
    handler = MagicMock()
    handler.handle_bootstrap.return_value = (200, {"status": "ok", "advisor_state": "ready"}, {})
    set_advisor_api_handler(handler)

    status, response_type, payload, _ = _get("/api/v1/advisor/bootstrap", headers={"Cookie": "advisor_session=abc"})

    assert status == 200
    assert response_type == "json"
    assert payload["advisor_state"] == "ready"
    handler.handle_bootstrap.assert_called_once()
    set_advisor_api_handler(None)


def test_advisor_dashboard_route_delegates_to_api_handler():
    handler = MagicMock()
    handler.handle_dashboard.return_value = (
        200,
        {"status": "ok", "selected_period": "mes", "insights": []},
        {},
    )
    set_advisor_api_handler(handler)

    status, response_type, payload, _ = _get("/api/v1/advisor/dashboard?period=mes", headers={"Cookie": "advisor_session=abc"})

    assert status == 200
    assert response_type == "json"
    assert payload["selected_period"] == "mes"
    handler.handle_dashboard.assert_called_once()
    set_advisor_api_handler(None)


def test_advisor_dashboard_route_preserves_insights_payload():
    handler = MagicMock()
    handler.handle_dashboard.return_value = (
        200,
        {
            "status": "ok",
            "selected_period": "mes",
            "insights": [{"code": "all_clear", "title": "Sin alertas"}],
        },
        {},
    )
    set_advisor_api_handler(handler)

    status, response_type, payload, _ = _get("/api/v1/advisor/dashboard?period=mes", headers={"Cookie": "advisor_session=abc"})

    assert status == 200
    assert response_type == "json"
    assert payload["insights"][0]["code"] == "all_clear"
    set_advisor_api_handler(None)


def test_advisor_logout_route_delegates_to_api_handler():
    handler = MagicMock()
    handler.handle_logout.return_value = (200, {"status": "ok"}, {"Set-Cookie": "advisor_session=; Max-Age=0"})
    set_advisor_api_handler(handler)

    status, response_type, payload, extra_headers = _post("/api/v1/advisor/logout", headers={"Cookie": "advisor_session=abc"})

    assert status == 200
    assert response_type == "json"
    assert payload["status"] == "ok"
    assert "Set-Cookie" in extra_headers
    handler.handle_logout.assert_called_once()
    set_advisor_api_handler(None)

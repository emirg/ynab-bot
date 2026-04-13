from unittest.mock import MagicMock

from presentation.http.handlers.advisor_page_handler import AdvisorPageHandler


def test_handle_page_returns_html_with_insights_section():
    container = MagicMock()
    access_service = MagicMock()
    access_service.get_session_telegram_id.return_value = 123
    container.get_advisor_access_service.return_value = access_service

    config = MagicMock()
    config.resolved_advisor_base_url = "https://advisor.example.com"
    container.get_config.return_value = config

    handler = AdvisorPageHandler(container)

    status, response_type, payload, extra_headers = handler.handle_page({"Cookie": "advisor_session=abc"})

    assert status == 200
    assert response_type == "html"
    assert "Insights del advisor" in payload
    assert 'id="insights-list"' in payload
    assert extra_headers == {}

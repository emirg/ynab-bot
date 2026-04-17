"""Tests for ResilientHTTPClient."""
import pytest
from unittest.mock import MagicMock, call, patch

import requests

from domain.exceptions import YNABApiException
from infrastructure.http_client import ResilientHTTPClient


def _make_response(status_code: int, text: str = "", headers: dict = None) -> MagicMock:
    """Helper to build a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.headers = headers or {}
    return resp


def _make_client(max_retries: int = 3, retry_backoff_base: float = 1.0):
    """Build a ResilientHTTPClient with a mock sleep and a patched session."""
    sleep_mock = MagicMock()
    client = ResilientHTTPClient(
        base_url="https://api.example.com",
        default_headers={"Authorization": "Bearer token"},
        timeout=5,
        max_retries=max_retries,
        retry_backoff_base=retry_backoff_base,
        sleep_func=sleep_mock,
    )
    return client, sleep_mock


# ──────────────────────────────────────────────────────────────────────────────
# 1. Successful request — no retry
# ──────────────────────────────────────────────────────────────────────────────

def test_successful_request_no_retry():
    client, sleep_mock = _make_client()
    ok_response = _make_response(200, "ok")

    with patch.object(client._session, "request", return_value=ok_response) as mock_req:
        result = client.get("/v1/budgets")

    assert result is ok_response
    mock_req.assert_called_once()
    sleep_mock.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Retry on 429 then success on second attempt
# ──────────────────────────────────────────────────────────────────────────────

def test_retry_on_429_then_success():
    client, sleep_mock = _make_client()
    resp_429 = _make_response(429, "rate limited")
    resp_200 = _make_response(200, "ok")

    with patch.object(client._session, "request", side_effect=[resp_429, resp_200]):
        result = client.get("/v1/budgets")

    assert result is resp_200
    sleep_mock.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Retry on 500 then success
# ──────────────────────────────────────────────────────────────────────────────

def test_retry_on_500_then_success():
    client, sleep_mock = _make_client()
    resp_500 = _make_response(500, "server error")
    resp_200 = _make_response(200, "ok")

    with patch.object(client._session, "request", side_effect=[resp_500, resp_200]):
        result = client.get("/v1/budgets")

    assert result is resp_200
    sleep_mock.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# 4. Retry on ConnectionError then success
# ──────────────────────────────────────────────────────────────────────────────

def test_retry_on_connection_error_then_success():
    client, sleep_mock = _make_client()
    resp_200 = _make_response(200, "ok")

    with patch.object(
        client._session,
        "request",
        side_effect=[requests.exceptions.ConnectionError("conn refused"), resp_200],
    ):
        result = client.get("/v1/budgets")

    assert result is resp_200
    sleep_mock.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# 5. Retry on Timeout then success
# ──────────────────────────────────────────────────────────────────────────────

def test_retry_on_timeout_then_success():
    client, sleep_mock = _make_client()
    resp_200 = _make_response(200, "ok")

    with patch.object(
        client._session,
        "request",
        side_effect=[requests.exceptions.Timeout("timed out"), resp_200],
    ):
        result = client.get("/v1/budgets")

    assert result is resp_200
    sleep_mock.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# 6. All retries exhausted raises YNABApiException with status_code
# ──────────────────────────────────────────────────────────────────────────────

def test_all_retries_exhausted_raises_ynab_api_exception():
    client, _ = _make_client(max_retries=2)
    resp_500 = _make_response(500, "still broken")

    with patch.object(client._session, "request", return_value=resp_500):
        with pytest.raises(YNABApiException) as exc_info:
            client.get("/v1/budgets")

    assert exc_info.value.status_code == 500


def test_all_retries_exhausted_network_error_raises_ynab_api_exception():
    client, _ = _make_client(max_retries=2)

    with patch.object(
        client._session,
        "request",
        side_effect=requests.exceptions.ConnectionError("no network"),
    ):
        with pytest.raises(YNABApiException) as exc_info:
            client.get("/v1/budgets")

    assert exc_info.value.status_code is None


# ──────────────────────────────────────────────────────────────────────────────
# 7. Retry-After header respected
# ──────────────────────────────────────────────────────────────────────────────

def test_retry_after_header_respected():
    client, sleep_mock = _make_client()
    resp_429 = _make_response(429, "rate limited", headers={"Retry-After": "42"})
    resp_200 = _make_response(200, "ok")

    with patch.object(client._session, "request", side_effect=[resp_429, resp_200]):
        client.get("/v1/budgets")

    sleep_mock.assert_called_once_with(42.0)


# ──────────────────────────────────────────────────────────────────────────────
# 8. Timeout passed to requests
# ──────────────────────────────────────────────────────────────────────────────

def test_timeout_passed_to_requests():
    client, _ = _make_client()
    resp_200 = _make_response(200, "ok")

    with patch.object(client._session, "request", return_value=resp_200) as mock_req:
        client.get("/v1/budgets")

    _, call_kwargs = mock_req.call_args
    assert call_kwargs.get("timeout") == 5


# ──────────────────────────────────────────────────────────────────────────────
# 9. max_retries configurable — set to 1, verify only 1 retry
# ──────────────────────────────────────────────────────────────────────────────

def test_max_retries_configurable():
    client, sleep_mock = _make_client(max_retries=1)
    resp_500 = _make_response(500, "broken")

    with patch.object(client._session, "request", return_value=resp_500) as mock_req:
        with pytest.raises(YNABApiException):
            client.get("/v1/budgets")

    # 1 initial attempt + 1 retry = 2 total calls
    assert mock_req.call_count == 2
    assert sleep_mock.call_count == 1


# ──────────────────────────────────────────────────────────────────────────────
# 10. No retry on 401 — raises immediately
# ──────────────────────────────────────────────────────────────────────────────

def test_no_retry_on_401():
    client, sleep_mock = _make_client()
    resp_401 = _make_response(401, "unauthorized")

    with patch.object(client._session, "request", return_value=resp_401) as mock_req:
        result = client.get("/v1/budgets")

    assert result is resp_401
    mock_req.assert_called_once()
    sleep_mock.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 11. No retry on 400 — raises immediately
# ──────────────────────────────────────────────────────────────────────────────

def test_no_retry_on_400():
    client, sleep_mock = _make_client()
    resp_400 = _make_response(400, "bad request")

    with patch.object(client._session, "request", return_value=resp_400) as mock_req:
        result = client.get("/v1/budgets")

    assert result is resp_400
    mock_req.assert_called_once()
    sleep_mock.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 12. Backoff is exponential (verify sleep values: 1, 2, 4...)
# ──────────────────────────────────────────────────────────────────────────────

def test_backoff_is_exponential():
    # max_retries=3 means: attempt 0, sleep, attempt 1, sleep, attempt 2, sleep, attempt 3 → raise
    client, sleep_mock = _make_client(max_retries=3, retry_backoff_base=1.0)
    resp_500 = _make_response(500, "broken")

    with patch.object(client._session, "request", return_value=resp_500):
        with pytest.raises(YNABApiException):
            client.get("/v1/budgets")

    # Sleeps should be 1*2^0=1, 1*2^1=2, 1*2^2=4
    assert sleep_mock.call_count == 3
    sleep_calls = [c.args[0] for c in sleep_mock.call_args_list]
    assert sleep_calls == [1.0, 2.0, 4.0]


# ──────────────────────────────────────────────────────────────────────────────
# 13. Backoff capped at 10s
# ──────────────────────────────────────────────────────────────────────────────

def test_backoff_capped_at_10_seconds():
    # Use a large base so the formula would exceed 10s on the first retry
    client, sleep_mock = _make_client(max_retries=2, retry_backoff_base=100.0)
    resp_500 = _make_response(500, "broken")

    with patch.object(client._session, "request", return_value=resp_500):
        with pytest.raises(YNABApiException):
            client.get("/v1/budgets")

    for c in sleep_mock.call_args_list:
        assert c.args[0] <= 10.0

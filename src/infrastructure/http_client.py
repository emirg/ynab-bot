"""Resilient HTTP client with retry and backoff logic."""
import logging
import time
from typing import Callable, Optional

import requests

from domain.exceptions import YNABApiException

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 10.0


class ResilientHTTPClient:
    """HTTP client wrapping requests.Session with automatic retry and exponential backoff.

    Args:
        max_retries: Number of retry attempts after the initial request
            (total calls = max_retries + 1).
    """

    def __init__(
        self,
        base_url: str,
        default_headers: Optional[dict] = None,
        timeout: int = 15,
        max_retries: int = 3,
        retry_backoff_base: float = 1.0,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff_base = retry_backoff_base
        self._sleep = sleep_func
        self._session = requests.Session()
        if default_headers:
            self._session.headers.update(default_headers)

    def _build_url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _compute_backoff(self, attempt: int, response: Optional[requests.Response]) -> float:
        """Return the number of seconds to wait before the next attempt."""
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        wait = self._retry_backoff_base * (2 ** attempt)
        return min(wait, MAX_BACKOFF_SECONDS)

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = self._build_url(path)
        kwargs.setdefault("timeout", self._timeout)

        last_response: Optional[requests.Response] = None
        last_exception: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._session.request(method, url, **kwargs)

                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return response

                last_response = response
                last_exception = None

                if attempt < self._max_retries:
                    wait = self._compute_backoff(attempt, response)
                    logger.warning(
                        "Retryable HTTP error — will retry",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "status_code": response.status_code,
                            "wait_seconds": wait,
                            "url": url,
                        },
                    )
                    self._sleep(wait)

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                last_response = None
                last_exception = exc

                if attempt < self._max_retries:
                    wait = self._compute_backoff(attempt, None)
                    logger.warning(
                        "Retryable network error — will retry",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "error": str(exc),
                            "wait_seconds": wait,
                            "url": url,
                        },
                    )
                    self._sleep(wait)

        # All retries exhausted
        if last_response is not None:
            raise YNABApiException(
                f"HTTP {last_response.status_code} after {self._max_retries} retries",
                status_code=last_response.status_code,
                response_body=last_response.text,
            )
        raise YNABApiException(
            f"Network error after {self._max_retries} retries: {last_exception}",
            status_code=None,
            response_body=None,
        )

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self._request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self._request("DELETE", path, **kwargs)

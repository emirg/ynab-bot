from unittest.mock import MagicMock

from presentation.http.server import HTTPAPIRouter


class TestHTTPServer:
    def test_post_expense_route_dispatches_to_handler(self):
        endpoint_handler = MagicMock()
        endpoint_handler.handle_post.return_value = (200, {"status": "preview"})
        router = HTTPAPIRouter(endpoint_handler)

        status, body, extra_headers = router.route(
            method="POST",
            path="/api/v1/expenses/text",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer secret",
            },
            body=b'{"telegram_user_id": 123, "text": "Gaste 25k en Carulla"}',
        )

        assert status == 200
        assert body == {"status": "preview"}
        assert extra_headers == {}
        endpoint_handler.handle_post.assert_called_once()

    def test_unknown_route_returns_404(self):
        router = HTTPAPIRouter(MagicMock())

        status, body, extra_headers = router.route(
            method="POST",
            path="/api/v1/unknown",
            headers={"Content-Type": "application/json"},
            body=b'{"hello": "world"}',
        )

        assert status == 404
        assert body["error_code"] == "ROUTE_NOT_FOUND"
        assert extra_headers == {}

    def test_get_on_post_only_route_returns_405(self):
        router = HTTPAPIRouter(MagicMock())

        status, body, extra_headers = router.route(
            method="GET",
            path="/api/v1/expenses/text",
            headers={},
            body=b"",
        )

        assert status == 405
        assert body["error_code"] == "METHOD_NOT_ALLOWED"
        assert extra_headers == {"Allow": "POST"}

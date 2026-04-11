import pytest

from presentation.http.auth import (
    HTTPAuthError,
    validate_bearer_token,
)


class TestValidateBearerToken:
    def test_missing_header_raises(self):
        with pytest.raises(HTTPAuthError) as exc_info:
            validate_bearer_token({}, expected_token="secret")

        assert exc_info.value.error_code == "MISSING_AUTHORIZATION"

    def test_non_bearer_scheme_raises(self):
        with pytest.raises(HTTPAuthError) as exc_info:
            validate_bearer_token({"Authorization": "Basic secret"}, expected_token="secret")

        assert exc_info.value.error_code == "INVALID_AUTH_SCHEME"

    def test_invalid_token_raises(self):
        with pytest.raises(HTTPAuthError) as exc_info:
            validate_bearer_token({"Authorization": "Bearer wrong"}, expected_token="secret")

        assert exc_info.value.error_code == "INVALID_API_KEY"

    def test_valid_token_returns_true(self):
        assert validate_bearer_token(
            {"Authorization": "Bearer secret"},
            expected_token="secret",
        ) is True

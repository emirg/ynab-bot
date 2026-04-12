import hmac


class HTTPAuthError(Exception):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def validate_bearer_token(headers: dict, expected_token: str) -> bool:
    auth_header = headers.get("Authorization")
    if not auth_header:
        raise HTTPAuthError(
            error_code="MISSING_AUTHORIZATION",
            message="Missing Authorization header.",
        )

    scheme, _, token = auth_header.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPAuthError(
            error_code="INVALID_AUTH_SCHEME",
            message="Authorization header must use the Bearer scheme.",
        )

    if not hmac.compare_digest(token, expected_token):
        raise HTTPAuthError(
            error_code="INVALID_API_KEY",
            message="Invalid authentication token.",
        )

    return True

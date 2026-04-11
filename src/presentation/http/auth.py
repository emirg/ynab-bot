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
            message="Falta el header Authorization.",
        )

    scheme, _, token = auth_header.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPAuthError(
            error_code="INVALID_AUTH_SCHEME",
            message="El header Authorization debe usar el esquema Bearer.",
        )

    if token != expected_token:
        raise HTTPAuthError(
            error_code="INVALID_API_KEY",
            message="El token de autenticación no es válido.",
        )

    return True

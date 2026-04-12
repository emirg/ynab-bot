import json

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


class TextMessageRequestValidationError(Exception):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class TextMessageRequest(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)

    telegram_user_id: int
    text: str
    force_commit: bool = False

    @field_validator("telegram_user_id")
    @classmethod
    def validate_telegram_user_id(cls, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("telegram_user_id must be an integer.")
        return value

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value:
            raise ValueError("text must be a non-empty string.")
        return value


def parse_text_message_request(body: bytes) -> TextMessageRequest:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TextMessageRequestValidationError(
            "INVALID_JSON",
            "Request body does not contain valid JSON.",
        ) from exc

    if not isinstance(payload, dict):
        raise TextMessageRequestValidationError(
            "INVALID_REQUEST",
            "Request body must be a JSON object.",
        )

    try:
        return TextMessageRequest.model_validate(payload)
    except ValidationError as exc:
        first_error = exc.errors()[0] if exc.errors() else {}
        field = first_error.get("loc", [None])[0]

        if field == "telegram_user_id":
            message = "telegram_user_id must be an integer."
        elif field == "text":
            message = "text must be a non-empty string."
        elif field == "force_commit":
            message = "force_commit must be a boolean."
        else:
            message = "Request body contains invalid fields."

        raise TextMessageRequestValidationError("INVALID_REQUEST", message) from exc

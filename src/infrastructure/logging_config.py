"""
Structured logging configuration for YNAB Bot.

Provides JSON logging for production (Railway) and human-readable format for local dev.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


# Optional extra fields that the JSON formatter will include when present in log records.
_OPTIONAL_FIELDS = (
    "user_id",
    "operation",
    "duration_ms",
    "status_code",
    "error_type",
    "attempt",
    "max_retries",
    "wait_seconds",
    "url",
    "error",
)

_REDACTED = "[REDACTED]"
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "api-key",
    "apikey",
    "auth",
    "authorization",
    "client_secret",
    "code",
    "id_token",
    "key",
    "password",
    "refresh_token",
    "secret",
    "session",
    "session_token",
    "sig",
    "signature",
    "state",
    "token",
}

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_AUTH_HEADER_RE = re.compile(
    r"(?i)\b(authorization\s*[:=]\s*)(bearer|basic)\s+([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\b(bearer|basic)\s+([A-Za-z0-9._~+/=-]{12,})")
_TELEGRAM_BOT_URL_RE = re.compile(r"(https://api\.telegram\.org/bot)([^/\s]+)")
_TELEGRAM_BOT_TOKEN_RE = re.compile(
    r"(?<![\w-])\d{6,}:[A-Za-z0-9_-]{20,}(?![\w-])"
)


def _redact_url_credentials(netloc: str) -> str:
    if "@" not in netloc:
        return netloc

    credentials, host = netloc.rsplit("@", 1)
    if ":" in credentials:
        return f"{_REDACTED}:{_REDACTED}@{host}"
    return f"{_REDACTED}@{host}"


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value

    if not parsed.scheme or not parsed.netloc:
        return value

    query = parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = [
        (key, _REDACTED if key.lower() in _SENSITIVE_QUERY_KEYS else query_value)
        for key, query_value in query
    ]
    return urlunsplit(
        (
            parsed.scheme,
            _redact_url_credentials(parsed.netloc),
            parsed.path,
            urlencode(redacted_query, doseq=True),
            parsed.fragment,
        )
    )


def redact_sensitive_data(value: str) -> str:
    """Return a copy of value with URL tokens and credentials redacted."""
    redacted = _URL_RE.sub(lambda match: _redact_url(match.group(0)), value)
    redacted = _TELEGRAM_BOT_URL_RE.sub(rf"\1{_REDACTED}", redacted)
    redacted = _AUTH_HEADER_RE.sub(rf"\1\2 {_REDACTED}", redacted)
    redacted = _BEARER_RE.sub(rf"\1 {_REDACTED}", redacted)
    redacted = _TELEGRAM_BOT_TOKEN_RE.sub(_REDACTED, redacted)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_data(value)
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}

    rendered = str(value)
    redacted = redact_sensitive_data(rendered)
    if redacted != rendered:
        return redacted
    return value


class SensitiveDataFilter(logging.Filter):
    """Redact sensitive data before a log record reaches any formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_value(record.msg)
        if record.args:
            record.args = _redact_value(record.args)

        for field in _OPTIONAL_FIELDS:
            if hasattr(record, field):
                setattr(record, field, _redact_value(getattr(record, field)))

        return True


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_data(record.getMessage()),
        }

        for field in _OPTIONAL_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = _redact_value(value)

        return json.dumps(log_entry, ensure_ascii=False)


class RedactingFormatter(logging.Formatter):
    """Formats log records and redacts the final rendered output."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_data(super().format(record))


def setup_logging(level: str = "INFO", json_format: bool = None) -> None:
    """Configure root logger with a single StreamHandler to stdout.

    Args:
        level: Logging level string (e.g. "INFO", "DEBUG").
        json_format: True → JSON, False → human-readable, None → auto-detect.
                     Auto-detect uses JSON when RAILWAY_ENVIRONMENT env var is set.
    """
    if json_format is None:
        json_format = "RAILWAY_ENVIRONMENT" in os.environ

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates when called multiple times.
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SensitiveDataFilter())

    if json_format:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = RedactingFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    for logger_name in ("httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def log_with_context(logger: logging.Logger, level: int, message: str, **extra) -> None:
    """Log a message with optional structured extra fields.

    The JSON formatter will include any recognised extra fields
    (user_id, operation, duration_ms, status_code, error_type).

    Args:
        logger: The logger instance to use.
        level: Logging level constant (e.g. logging.INFO).
        message: The log message.
        **extra: Arbitrary key/value pairs attached to the log record.
    """
    logger.log(level, message, extra=extra)

"""
Structured logging configuration for YNAB Bot.

Provides JSON logging for production (Railway) and human-readable format for local dev.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


# Optional extra fields that the JSON formatter will include when present in log records.
_OPTIONAL_FIELDS = ("user_id", "operation", "duration_ms", "status_code", "error_type")


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in _OPTIONAL_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        return json.dumps(log_entry, ensure_ascii=False)


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

    if json_format:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


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

"""Tests for src/infrastructure/logging_config.py"""

import io
import json
import logging
import os
from unittest.mock import patch

import pytest

from infrastructure.logging_config import (
    JsonFormatter,
    SensitiveDataFilter,
    log_with_context,
    redact_sensitive_data,
    setup_logging,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_log(use_json: bool) -> tuple[logging.Logger, io.StringIO]:
    """Set up a logger with a StringIO handler and return (logger, stream)."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    if use_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
    logger = logging.getLogger(f"test.{id(stream)}")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger, stream


# ---------------------------------------------------------------------------
# Test 1: JSON formatter outputs valid JSON with expected base fields
# ---------------------------------------------------------------------------

class TestJsonFormatterBaseFields:
    def test_output_is_valid_json(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("hello")
        output = stream.getvalue().strip()
        parsed = json.loads(output)  # raises if invalid JSON
        assert isinstance(parsed, dict)

    def test_base_fields_present(self):
        logger, stream = _capture_log(use_json=True)
        logger.warning("test message")
        parsed = json.loads(stream.getvalue().strip())
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "message" in parsed

    def test_level_value(self):
        logger, stream = _capture_log(use_json=True)
        logger.error("something failed")
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["level"] == "ERROR"

    def test_message_value(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("expense recorded")
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["message"] == "expense recorded"

    def test_timestamp_is_iso_format(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("check timestamp")
        parsed = json.loads(stream.getvalue().strip())
        # Should parse without error
        from datetime import datetime
        dt = datetime.fromisoformat(parsed["timestamp"])
        assert dt is not None


# ---------------------------------------------------------------------------
# Test 2: Human-readable format matches current pattern
# ---------------------------------------------------------------------------

class TestHumanReadableFormat:
    def test_format_contains_level(self):
        logger, stream = _capture_log(use_json=False)
        logger.info("human log")
        output = stream.getvalue().strip()
        assert "INFO" in output

    def test_format_contains_message(self):
        logger, stream = _capture_log(use_json=False)
        logger.info("human log")
        output = stream.getvalue().strip()
        assert "human log" in output

    def test_format_contains_logger_name(self):
        logger, stream = _capture_log(use_json=False)
        logger.info("msg")
        output = stream.getvalue().strip()
        assert logger.name in output

    def test_format_matches_pattern(self):
        """Output should match: YYYY-MM-DD HH:MM:SS,mmm - name - LEVEL - message"""
        import re
        logger, stream = _capture_log(use_json=False)
        logger.info("pattern test")
        output = stream.getvalue().strip()
        pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ - .+ - INFO - pattern test"
        assert re.match(pattern, output), f"Output did not match expected pattern: {output}"


# ---------------------------------------------------------------------------
# Test 3: Extra fields appear in JSON output when provided
# ---------------------------------------------------------------------------

class TestJsonFormatterExtraFields:
    def test_user_id_included(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("op done", extra={"user_id": 42})
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["user_id"] == 42

    def test_operation_included(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("finished", extra={"operation": "create_transaction"})
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["operation"] == "create_transaction"

    def test_multiple_extra_fields(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("done", extra={"user_id": 7, "operation": "get_categories", "duration_ms": 123})
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["user_id"] == 7
        assert parsed["operation"] == "get_categories"
        assert parsed["duration_ms"] == 123

    def test_status_code_included(self):
        logger, stream = _capture_log(use_json=True)
        logger.error("api error", extra={"status_code": 429})
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["status_code"] == 429

    def test_error_type_included(self):
        logger, stream = _capture_log(use_json=True)
        logger.error("fail", extra={"error_type": "YNABApiException"})
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["error_type"] == "YNABApiException"


# ---------------------------------------------------------------------------
# Test 3b: Sensitive values are redacted from log output
# ---------------------------------------------------------------------------

class TestSensitiveDataRedaction:
    def test_redacts_sensitive_query_params(self):
        value = (
            "https://bot.example.com/advisor/launch?token=abc123&"
            "period=month&access_token=secret-token"
        )

        output = redact_sensitive_data(value)

        assert "token=abc123" not in output
        assert "access_token=secret-token" not in output
        assert "token=%5BREDACTED%5D" in output
        assert "access_token=%5BREDACTED%5D" in output
        assert "period=month" in output

    def test_redacts_bearer_credentials(self):
        output = redact_sensitive_data("Authorization: Bearer secret-token-value")

        assert "secret-token-value" not in output
        assert "Authorization: Bearer [REDACTED]" in output

    def test_redacts_telegram_bot_path_token(self):
        output = redact_sensitive_data(
            "https://api.telegram.org/bot123456:secret-token/sendMessage"
        )

        assert "123456:secret-token" not in output
        assert "https://api.telegram.org/bot[REDACTED]/sendMessage" in output

    def test_redacts_bare_telegram_bot_token_in_exception_message(self):
        output = redact_sensitive_data(
            "Error starting the bot: The token "
            "`123456789:abcdefghijklmnopqrstuvwxyzABCDE` "
            "was rejected by the server"
        )

        assert "123456789:abcdefghijklmnopqrstuvwxyzABCDE" not in output
        assert "The token `[REDACTED]` was rejected by the server" in output

    def test_redacts_bare_telegram_bot_token_in_critical_startup_message(self):
        output = redact_sensitive_data(
            "Critical error while starting the bot: The token "
            "`123456789:abcdefghijklmnopqrstuvwxyzABCDE` "
            "was rejected by the server."
        )

        assert "123456789:abcdefghijklmnopqrstuvwxyzABCDE" not in output
        assert "The token `[REDACTED]` was rejected by the server." in output

    def test_json_formatter_redacts_message(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("launch https://example.test/path?code=oauth-code&ok=1")

        parsed = json.loads(stream.getvalue().strip())

        assert "oauth-code" not in parsed["message"]
        assert "code=%5BREDACTED%5D" in parsed["message"]
        assert "ok=1" in parsed["message"]

    def test_json_formatter_redacts_structured_url_extra(self):
        logger, stream = _capture_log(use_json=True)
        logger.info(
            "retrying",
            extra={"url": "https://example.test/path?api_key=secret&visible=yes"},
        )

        parsed = json.loads(stream.getvalue().strip())

        assert parsed["url"] == (
            "https://example.test/path?api_key=%5BREDACTED%5D&visible=yes"
        )

    def test_filter_redacts_httpx_style_log_args(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SensitiveDataFilter())
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger(f"test.args.{id(stream)}")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info(
            'HTTP Request: %s %s "%s %d %s"',
            "GET",
            "https://example.test/callback?state=signed-state&safe=1",
            "HTTP/1.1",
            200,
            "OK",
        )

        output = stream.getvalue().strip()
        assert "signed-state" not in output
        assert "state=%5BREDACTED%5D" in output
        assert "safe=1" in output

    def test_filter_redacts_httpx_telegram_get_updates_url(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SensitiveDataFilter())
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger(f"test.telegram.{id(stream)}")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info(
            'HTTP Request: POST %s "HTTP/1.1 200 OK"',
            "https://api.telegram.org/bot123456:fake-secret-token/getUpdates",
        )

        output = stream.getvalue().strip()
        assert "123456:fake-secret-token" not in output
        assert "https://api.telegram.org/bot[REDACTED]/getUpdates" in output

    def test_setup_logging_redacts_human_readable_output(self):
        stream = io.StringIO()
        setup_logging(level="INFO", json_format=False)
        root = logging.getLogger()
        root.handlers[0].stream = stream

        root.info("callback https://example.test/cb?refresh_token=secret&ok=1")

        output = stream.getvalue().strip()
        assert "refresh_token=secret" not in output
        assert "refresh_token=%5BREDACTED%5D" in output
        assert "ok=1" in output


# ---------------------------------------------------------------------------
# Test 4: Auto-detection — RAILWAY_ENVIRONMENT set → JSON format
# ---------------------------------------------------------------------------

class TestAutoDetectionRailway:
    def test_railway_env_triggers_json(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT": "production"}):
            setup_logging(level="DEBUG", json_format=None)

        root = logging.getLogger()
        # Detach real handler; attach a test one using the JsonFormatter
        assert len(root.handlers) == 1
        formatter = root.handlers[0].formatter
        assert isinstance(formatter, JsonFormatter)

    def test_railway_env_json_output_valid(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT": "production"}):
            setup_logging(level="DEBUG", json_format=None)

        root = logging.getLogger()
        root.handlers[0].stream = stream  # redirect to our test stream
        root.info("railway test")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["message"] == "railway test"


# ---------------------------------------------------------------------------
# Test 5: Auto-detection — RAILWAY_ENVIRONMENT not set → human-readable
# ---------------------------------------------------------------------------

class TestAutoDetectionLocal:
    def test_no_railway_env_uses_human_readable(self):
        env = {k: v for k, v in os.environ.items() if k != "RAILWAY_ENVIRONMENT"}
        with patch.dict(os.environ, env, clear=True):
            setup_logging(level="DEBUG", json_format=None)

        root = logging.getLogger()
        assert len(root.handlers) == 1
        formatter = root.handlers[0].formatter
        assert not isinstance(formatter, JsonFormatter)
        assert isinstance(formatter, logging.Formatter)


# ---------------------------------------------------------------------------
# Test 6: log_with_context helper passes extra fields to the record
# ---------------------------------------------------------------------------

class TestLogWithContext:
    def test_extra_fields_appear_in_json(self):
        logger, stream = _capture_log(use_json=True)
        log_with_context(logger, logging.INFO, "ctx msg", user_id=99, operation="test_op")
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["message"] == "ctx msg"
        assert parsed["user_id"] == 99
        assert parsed["operation"] == "test_op"

    def test_no_extra_fields_still_logs(self):
        logger, stream = _capture_log(use_json=True)
        log_with_context(logger, logging.WARNING, "no extras")
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["message"] == "no extras"
        assert parsed["level"] == "WARNING"

    def test_works_with_human_readable(self):
        logger, stream = _capture_log(use_json=False)
        log_with_context(logger, logging.INFO, "readable", user_id=1)
        output = stream.getvalue().strip()
        assert "readable" in output


# ---------------------------------------------------------------------------
# Test 7: Missing extra fields don't appear in JSON output (no null values)
# ---------------------------------------------------------------------------

class TestMissingExtraFieldsAbsent:
    def test_optional_fields_absent_when_not_provided(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("clean output")
        parsed = json.loads(stream.getvalue().strip())
        for field in ("user_id", "operation", "duration_ms", "status_code", "error_type"):
            assert field not in parsed, f"Field '{field}' should not appear when not provided"

    def test_partial_fields_only_provided_ones_present(self):
        logger, stream = _capture_log(use_json=True)
        logger.info("partial", extra={"user_id": 5})
        parsed = json.loads(stream.getvalue().strip())
        assert "user_id" in parsed
        for field in ("operation", "duration_ms", "status_code", "error_type"):
            assert field not in parsed, f"Field '{field}' should not appear when not provided"


# ---------------------------------------------------------------------------
# Additional: setup_logging is idempotent (no duplicate handlers)
# ---------------------------------------------------------------------------

class TestSetupLoggingIdempotent:
    def test_no_duplicate_handlers(self):
        setup_logging(level="INFO", json_format=False)
        setup_logging(level="INFO", json_format=False)
        root = logging.getLogger()
        assert len(root.handlers) == 1

    def test_level_applied_to_root(self):
        setup_logging(level="WARNING", json_format=False)
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_http_client_loggers_default_to_warning(self):
        logging.getLogger("httpx").setLevel(logging.NOTSET)
        logging.getLogger("httpcore").setLevel(logging.NOTSET)

        setup_logging(level="INFO", json_format=False)

        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING

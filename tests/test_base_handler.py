"""Tests for BaseHandler structured logging and send_error_message improvements."""
import logging
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler


# ---------------------------------------------------------------------------
# Minimal concrete subclass so we can instantiate BaseHandler
# ---------------------------------------------------------------------------

class _ConcreteHandler(BaseHandler):
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def container():
    return MagicMock()


@pytest.fixture
def handler(container):
    return _ConcreteHandler(container)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def update():
    mock = MagicMock(spec=Update)
    mock.effective_user = MagicMock(spec=User)
    mock.effective_user.id = 42
    mock.effective_user.full_name = "Test User"
    mock.effective_user.username = "testuser"
    message_mock = AsyncMock(spec=Message)
    mock.message = message_mock
    mock.callback_query = None
    return mock


# ---------------------------------------------------------------------------
# Tests: send_error_message
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_send_error_message_uses_string_parameter(handler, update):
    """send_error_message(update, msg) sends the plain string when no exception provided."""
    with patch.object(handler, 'send_message', new=AsyncMock()) as mock_send:
        await handler.send_error_message(update, "algo salió mal")

    mock_send.assert_called_once()
    sent_text = mock_send.call_args[0][1]
    assert "algo salió mal" in sent_text


@pytest.mark.anyio
async def test_send_error_message_uses_user_message_from_exception(handler, update):
    """send_error_message uses exception.user_message when exception has that attribute."""
    exc = Exception("raw internal detail")
    exc.user_message = "Mensaje amigable en español."

    with patch.object(handler, 'send_message', new=AsyncMock()) as mock_send:
        await handler.send_error_message(update, "fallback string", exception=exc)

    sent_text = mock_send.call_args[0][1]
    assert "Mensaje amigable en español." in sent_text
    assert "fallback string" not in sent_text
    assert "raw internal detail" not in sent_text


@pytest.mark.anyio
async def test_send_error_message_uses_string_when_exception_has_no_user_message(handler, update):
    """send_error_message falls back to the string param when exception lacks user_message."""
    exc = ValueError("technical error")  # no user_message attribute

    with patch.object(handler, 'send_message', new=AsyncMock()) as mock_send:
        await handler.send_error_message(update, "fallback string", exception=exc)

    sent_text = mock_send.call_args[0][1]
    assert "fallback string" in sent_text


@pytest.mark.anyio
async def test_send_error_message_backward_compatible_no_exception(handler, update):
    """send_error_message(update, msg) signature without exception kwarg still works."""
    with patch.object(handler, 'send_message', new=AsyncMock()) as mock_send:
        await handler.send_error_message(update, "solo el string")

    sent_text = mock_send.call_args[0][1]
    assert "solo el string" in sent_text


# ---------------------------------------------------------------------------
# Tests: structured logging methods
# ---------------------------------------------------------------------------

def test_log_handler_start_passes_structured_fields(handler, update):
    """log_handler_start calls log_with_context with user_id and operation."""
    with patch('presentation.telegram.handlers.base_handler.log_with_context') as mock_lwc:
        handler.log_handler_start("TestHandler", update)

    mock_lwc.assert_called_once()
    _, args, kwargs = mock_lwc.mock_calls[0]
    assert args[1] == logging.INFO
    assert kwargs.get('user_id') == 42
    assert kwargs.get('operation') == "TestHandler"


def test_log_handler_error_passes_structured_fields(handler, update):
    """log_handler_error calls log_with_context with user_id, operation, and error_type."""
    err = RuntimeError("boom")
    with patch('presentation.telegram.handlers.base_handler.log_with_context') as mock_lwc:
        handler.log_handler_error("TestHandler", update, err)

    mock_lwc.assert_called_once()
    _, args, kwargs = mock_lwc.mock_calls[0]
    assert args[1] == logging.ERROR
    assert kwargs.get('user_id') == 42
    assert kwargs.get('operation') == "TestHandler"
    assert kwargs.get('error_type') == "RuntimeError"


def test_log_handler_success_passes_structured_fields(handler, update):
    """log_handler_success calls log_with_context with user_id and operation."""
    with patch('presentation.telegram.handlers.base_handler.log_with_context') as mock_lwc:
        handler.log_handler_success("TestHandler", update)

    mock_lwc.assert_called_once()
    _, args, kwargs = mock_lwc.mock_calls[0]
    assert args[1] == logging.INFO
    assert kwargs.get('user_id') == 42
    assert kwargs.get('operation') == "TestHandler"


def test_log_handler_error_type_name_is_class_name(handler, update):
    """error_type field reflects the actual exception class name."""
    class CustomDomainError(Exception):
        pass

    err = CustomDomainError("domain problem")
    with patch('presentation.telegram.handlers.base_handler.log_with_context') as mock_lwc:
        handler.log_handler_error("SomeHandler", update, err)

    _, _, kwargs = mock_lwc.mock_calls[0]
    assert kwargs.get('error_type') == "CustomDomainError"

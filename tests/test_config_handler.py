"""Tests for ConfigHandler — /zona command."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from presentation.telegram.handlers.config_handler import ConfigHandler
from domain.time_utils import DEFAULT_TIMEZONE


@pytest.fixture
def container():
    mock = MagicMock()
    mock.get_auth_service.return_value = MagicMock()
    mock.get_user_config_service.return_value = MagicMock()
    mock.get_split_config_service.return_value = MagicMock()
    mock.get_oauth_service.return_value = MagicMock()
    return mock


@pytest.fixture
def handler(container):
    return ConfigHandler(container)


@pytest.fixture
def update():
    mock = MagicMock(spec=Update)
    mock.effective_user = MagicMock(spec=User)
    mock.effective_user.id = 123
    mock.effective_user.first_name = "TestUser"

    message_mock = AsyncMock(spec=Message)
    mock.message = message_mock
    mock.callback_query = None
    return mock


@pytest.fixture
def context():
    return MagicMock(spec=ContextTypes.DEFAULT_TYPE)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


# ---------------------------------------------------------------------------
# /zona command
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_zona_command_shows_current(handler, container, update, context):
    """``/zona`` without args shows current timezone."""
    context.args = []
    container.get_user_config_service().get_user_status.return_value = {
        'timezone': DEFAULT_TIMEZONE,
    }
    await handler.zona_command(update, context)
    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert DEFAULT_TIMEZONE in text


@pytest.mark.anyio
async def test_zona_command_updates(handler, container, update, context):
    """``/zona America/Bogota`` updates and confirms."""
    context.args = ['America/Bogota']
    await handler.zona_command(update, context)
    container.get_user_config_service().update_timezone.assert_called_once_with(123, 'America/Bogota')
    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert 'America/Bogota' in text


@pytest.mark.anyio
async def test_zona_command_invalid(handler, container, update, context):
    """``/zona Invalid/Zone`` returns error."""
    context.args = ['Invalid/Zone']
    container.get_user_config_service().update_timezone.side_effect = ValueError("Zona horaria invalida: 'Invalid/Zone'")
    await handler.zona_command(update, context)
    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert 'invalida' in text.lower() or 'error' in text.lower()

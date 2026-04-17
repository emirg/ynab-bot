"""Tests for SummaryHandler (/resumen command)."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from presentation.telegram.handlers.summary_handler import SummaryHandler
from domain.models.user import UserConfiguration, UserStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def summary_service():
    return MagicMock()


@pytest.fixture
def auth_service():
    return MagicMock()


@pytest.fixture
def container(summary_service, auth_service):
    mock = MagicMock()
    mock.get_auth_service.return_value = auth_service
    mock.get_on_demand_summary_service.return_value = summary_service
    return mock


@pytest.fixture
def handler(container):
    return SummaryHandler(container)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def update():
    mock = MagicMock(spec=Update)
    mock.effective_user = MagicMock(spec=User)
    mock.effective_user.id = 42
    mock.effective_user.first_name = "TestUser"
    message_mock = AsyncMock(spec=Message)
    mock.message = message_mock
    mock.callback_query = None
    return mock


@pytest.fixture
def callback_update():
    mock = MagicMock(spec=Update)
    mock.effective_user = MagicMock(spec=User)
    mock.effective_user.id = 42
    mock.effective_user.first_name = "TestUser"
    mock.message = None
    query = AsyncMock()
    query.data = "resumen_mes_categorias"
    query.from_user.id = 42
    query.message = AsyncMock(spec=Message)
    mock.callback_query = query
    return mock


@pytest.fixture
def context():
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.args = []
    return ctx


def _make_authorized_user() -> UserConfiguration:
    """Return an authorized UserConfiguration."""
    return UserConfiguration(telegram_id=42, status=UserStatus.AUTHORIZED)

@pytest.mark.anyio
async def test_resumen_returns_disabled_message(handler, auth_service, summary_service, update, context):
    context.args = []
    auth_service.register_user.return_value = _make_authorized_user()

    await handler.handle_resumen_command(update, context)

    auth_service.register_user.assert_called_once_with(update.effective_user)
    summary_service.parse_period.assert_not_called()
    summary_service.generate_summary.assert_not_called()
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "deshabilitado temporalmente" in args[0]
    assert "YNAB Reflect" in args[0]


@pytest.mark.anyio
async def test_resumen_ignores_period_args_while_disabled(handler, auth_service, summary_service, update, context):
    context.args = ["dia"]
    auth_service.register_user.return_value = _make_authorized_user()

    await handler.handle_resumen_command(update, context)

    summary_service.parse_period.assert_not_called()
    summary_service.generate_summary.assert_not_called()
    args, _ = update.message.reply_text.call_args
    assert "deshabilitado temporalmente" in args[0]


@pytest.mark.anyio
async def test_handle_delegates_to_resumen_command(handler, auth_service, summary_service, update, context):
    context.args = []
    auth_service.register_user.return_value = _make_authorized_user()

    await handler.handle(update, context)

    summary_service.generate_summary.assert_not_called()
    update.message.reply_text.assert_called_once()


@pytest.mark.anyio
async def test_monthly_callback_shows_disabled_message(handler, callback_update, context):
    await handler.handle_callback_query(callback_update, context)

    callback_update.callback_query.edit_message_text.assert_called_once()
    args, kwargs = callback_update.callback_query.edit_message_text.call_args
    assert "deshabilitado temporalmente" in args[0]
    assert kwargs["parse_mode"] == "Markdown"

"""Tests for SummaryHandler (/resumen command)."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from presentation.telegram.handlers.summary_handler import SummaryHandler
from domain.models.user import UserConfiguration, UserStatus
from domain.exceptions import YNABApiException, OAuthException


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def summary_service():
    """Return a pre-built summary service mock so tests and handler share same object."""
    svc = MagicMock()
    svc.parse_period.return_value = "mes"
    svc.generate_summary.return_value = MagicMock()
    return svc


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
def context():
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.args = []
    return ctx


def _make_configured_user() -> UserConfiguration:
    """Return an authorized + configured UserConfiguration."""
    return UserConfiguration(
        telegram_id=42,
        status=UserStatus.AUTHORIZED,
        budget_id="budget-123",
        default_account_id="account-456",
        ynab_access_token="token-abc",
    )


def _make_unconfigured_user() -> UserConfiguration:
    """Return an authorized but unconfigured UserConfiguration (no budget)."""
    return UserConfiguration(telegram_id=42, status=UserStatus.AUTHORIZED)


def _patch_formatter(formatted_text: str):
    """Context manager that replaces OnDemandSummaryFormatter.format_summary."""
    import presentation.telegram.formatters as fmt_module

    class _Patcher:
        def __enter__(self):
            self._original = fmt_module.OnDemandSummaryFormatter.format_summary
            fmt_module.OnDemandSummaryFormatter.format_summary = staticmethod(
                lambda s: formatted_text
            )
            return self

        def __exit__(self, *_):
            fmt_module.OnDemandSummaryFormatter.format_summary = self._original

    return _Patcher()


# ---------------------------------------------------------------------------
# Tests: successful summaries
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_resumen_no_args_defaults_to_mes(handler, auth_service, summary_service, update, context):
    """No args should default to 'mes' period."""
    context.args = []
    user_config = _make_configured_user()
    auth_service.register_user.return_value = user_config
    summary_service.parse_period.return_value = "mes"

    with _patch_formatter("Resumen formateado"):
        await handler.handle_resumen_command(update, context)

    summary_service.parse_period.assert_called_once_with("")
    summary_service.generate_summary.assert_called_once_with(user_config, "mes")
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "Resumen formateado" in args[0]


@pytest.mark.anyio
async def test_resumen_dia(handler, auth_service, summary_service, update, context):
    """'/resumen dia' should pass 'dia' to the service."""
    context.args = ["dia"]
    user_config = _make_configured_user()
    auth_service.register_user.return_value = user_config
    summary_service.parse_period.return_value = "dia"

    with _patch_formatter("Resumen día"):
        await handler.handle_resumen_command(update, context)

    summary_service.parse_period.assert_called_once_with("dia")
    summary_service.generate_summary.assert_called_once_with(user_config, "dia")
    args, _ = update.message.reply_text.call_args
    assert "Resumen día" in args[0]


@pytest.mark.anyio
async def test_resumen_semana(handler, auth_service, summary_service, update, context):
    """'/resumen semana' should pass 'semana' to the service."""
    context.args = ["semana"]
    user_config = _make_configured_user()
    auth_service.register_user.return_value = user_config
    summary_service.parse_period.return_value = "semana"

    with _patch_formatter("Resumen semana"):
        await handler.handle_resumen_command(update, context)

    summary_service.parse_period.assert_called_once_with("semana")
    summary_service.generate_summary.assert_called_once_with(user_config, "semana")
    args, _ = update.message.reply_text.call_args
    assert "Resumen semana" in args[0]


@pytest.mark.anyio
async def test_resumen_mes_explicit(handler, auth_service, summary_service, update, context):
    """'/resumen mes' should pass 'mes' to the service."""
    context.args = ["mes"]
    user_config = _make_configured_user()
    auth_service.register_user.return_value = user_config
    summary_service.parse_period.return_value = "mes"

    with _patch_formatter("Resumen mes"):
        await handler.handle_resumen_command(update, context)

    summary_service.parse_period.assert_called_once_with("mes")
    summary_service.generate_summary.assert_called_once_with(user_config, "mes")
    args, _ = update.message.reply_text.call_args
    assert "Resumen mes" in args[0]


# ---------------------------------------------------------------------------
# Tests: unconfigured user
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_unconfigured_user_gets_config_message(handler, auth_service, summary_service, update, context):
    """Authorized but unconfigured user should receive configuration instructions."""
    context.args = []
    auth_service.register_user.return_value = _make_unconfigured_user()

    await handler.handle_resumen_command(update, context)

    summary_service.generate_summary.assert_not_called()
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    text = args[0].lower()
    assert "configuraci" in text or "start" in text


# ---------------------------------------------------------------------------
# Tests: invalid period
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_invalid_period_gets_usage_help(handler, auth_service, summary_service, update, context):
    """Unrecognized period argument should return usage help, not crash."""
    context.args = ["año"]
    auth_service.register_user.return_value = _make_configured_user()
    summary_service.parse_period.side_effect = ValueError("Período no reconocido")

    await handler.handle_resumen_command(update, context)

    summary_service.generate_summary.assert_not_called()
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    text = args[0].lower()
    assert "uso" in text or "resumen" in text or "período" in text or "per" in text


# ---------------------------------------------------------------------------
# Tests: YNAB API error
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ynab_api_error_handled_gracefully(handler, auth_service, summary_service, update, context):
    """YNABApiException should produce a user-friendly error, not a crash."""
    context.args = []
    auth_service.register_user.return_value = _make_configured_user()
    summary_service.parse_period.return_value = "mes"
    summary_service.generate_summary.side_effect = YNABApiException(
        "Rate limit exceeded", status_code=429
    )

    await handler.handle_resumen_command(update, context)

    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    text = args[0].lower()
    assert "ynab" in text or "error" in text or "datos" in text


# ---------------------------------------------------------------------------
# Tests: OAuth error
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_oauth_error_handled_gracefully(handler, auth_service, summary_service, update, context):
    """OAuthException should produce a session-expired message, not a crash."""
    context.args = []
    auth_service.register_user.return_value = _make_configured_user()
    summary_service.parse_period.return_value = "mes"
    summary_service.generate_summary.side_effect = OAuthException("Token expired")

    await handler.handle_resumen_command(update, context)

    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    text = args[0].lower()
    assert "sesi" in text or "ynab" in text or "conectar" in text or "expirada" in text


# ---------------------------------------------------------------------------
# Tests: handle() delegates correctly
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_handle_delegates_to_resumen_command(handler, auth_service, summary_service, update, context):
    """handle() should delegate to handle_resumen_command."""
    context.args = []
    auth_service.register_user.return_value = _make_configured_user()
    summary_service.parse_period.return_value = "mes"

    with _patch_formatter("ok"):
        await handler.handle(update, context)

    summary_service.generate_summary.assert_called_once()

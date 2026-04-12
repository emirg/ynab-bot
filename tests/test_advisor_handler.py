import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from domain.models.onboarding import OnboardingStep
from presentation.telegram.handlers.advisor_handler import AdvisorHandler


@pytest.fixture
def container():
    mock = MagicMock()
    mock.get_auth_service.return_value = MagicMock()
    mock.get_advisor_access_service.return_value = MagicMock()
    mock.get_onboarding_service.return_value = MagicMock()
    return mock


@pytest.fixture
def handler(container):
    return AdvisorHandler(container)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def update():
    mock = MagicMock(spec=Update)
    mock.effective_user = MagicMock(spec=User)
    mock.effective_user.id = 123
    message_mock = AsyncMock(spec=Message)
    mock.message = message_mock
    mock.callback_query = None
    return mock


@pytest.fixture
def context():
    return MagicMock(spec=ContextTypes.DEFAULT_TYPE)


@pytest.mark.anyio
async def test_handle_analisis_command_returns_launch_link(handler, container, update, context):
    container.get_auth_service().register_user.return_value.is_authorized.return_value = True
    container.get_onboarding_service().get_onboarding_step.return_value = OnboardingStep.COMPLETE
    container.get_advisor_access_service().create_launch_url.return_value = "https://bot.example.com/advisor/launch?token=abc"

    await handler.handle_analisis_command(update, context)

    update.message.reply_text.assert_called_once()
    assert "Abrir advisor" in update.message.reply_text.call_args.args[0]


@pytest.mark.anyio
async def test_handle_analisis_command_blocks_when_budget_missing(handler, container, update, context):
    container.get_auth_service().register_user.return_value.is_authorized.return_value = True
    container.get_onboarding_service().get_onboarding_step.return_value = OnboardingStep.NEEDS_BUDGET

    await handler.handle_analisis_command(update, context)

    update.message.reply_text.assert_called_once()
    assert "/budgets" in update.message.reply_text.call_args.args[0]

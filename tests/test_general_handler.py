import pytest
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, User, Message, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from presentation.telegram.handlers.general_handler import GeneralHandler
from domain.models.onboarding import OnboardingStep
from domain.models.user import UserConfiguration, UserStatus, YNABBudget, YNABAccount


@pytest.fixture
def container():
    mock = MagicMock()
    # Setup common services
    mock.get_auth_service.return_value = MagicMock()
    mock.get_onboarding_service.return_value = MagicMock()
    mock.get_user_config_service.return_value = MagicMock()
    mock.get_oauth_service.return_value = MagicMock()
    return mock


@pytest.fixture
def handler(container):
    return GeneralHandler(container)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def update():
    mock = MagicMock(spec=Update)
    mock.effective_user = MagicMock(spec=User)
    mock.effective_user.id = 123
    mock.effective_user.first_name = "TestUser"
    
    # Message needs to be properly mocked for async calls
    message_mock = AsyncMock(spec=Message)
    mock.message = message_mock
    mock.callback_query = None
    return mock


@pytest.fixture
def context():
    return MagicMock(spec=ContextTypes.DEFAULT_TYPE)


@pytest.mark.anyio
async def test_handle_start_command_authorized_needs_connection(handler, container, update, context):
    # Setup
    user_config = UserConfiguration(telegram_id=123, status=UserStatus.AUTHORIZED)
    container.get_auth_service().register_user.return_value = user_config
    container.get_onboarding_service().get_onboarding_step.return_value = OnboardingStep.NEEDS_YNAB_CONNECTION
    container.get_oauth_service().generate_auth_url.return_value = "http://auth.url"
    
    # Run
    await handler.handle_start_command(update, context)
    
    # Verify
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "Conectar YNAB" in args[0] or "conectar" in args[0].lower()
    assert isinstance(kwargs['reply_markup'], InlineKeyboardMarkup)
    assert kwargs['reply_markup'].inline_keyboard[0][0].url == "http://auth.url"


@pytest.mark.anyio
async def test_handle_start_command_authorized_needs_budget(handler, container, update, context):
    # Setup
    user_config = UserConfiguration(telegram_id=123, status=UserStatus.AUTHORIZED)
    container.get_auth_service().register_user.return_value = user_config
    container.get_onboarding_service().get_onboarding_step.return_value = OnboardingStep.NEEDS_BUDGET
    
    budgets = [YNABBudget(id="b1", name="Budget 1", currency_format={})]
    container.get_user_config_service().get_available_budgets.return_value = budgets
    
    # Run
    await handler.handle_start_command(update, context)
    
    # Verify
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "presupuesto" in args[0].lower()
    assert isinstance(kwargs['reply_markup'], InlineKeyboardMarkup)
    assert kwargs['reply_markup'].inline_keyboard[0][0].callback_data == "select_budget_b1"


@pytest.mark.anyio
async def test_handle_start_command_authorized_needs_account(handler, container, update, context):
    # Setup
    user_config = UserConfiguration(telegram_id=123, status=UserStatus.AUTHORIZED)
    container.get_auth_service().register_user.return_value = user_config
    container.get_onboarding_service().get_onboarding_step.return_value = OnboardingStep.NEEDS_ACCOUNT
    
    accounts = [YNABAccount(id="a1", name="Acc 1", type="checking")]
    container.get_user_config_service().get_user_accounts.return_value = (accounts, None)
    
    # Run
    await handler.handle_start_command(update, context)
    
    # Verify
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "cuenta" in args[0].lower()
    assert isinstance(kwargs['reply_markup'], InlineKeyboardMarkup)
    assert kwargs['reply_markup'].inline_keyboard[0][0].callback_data == "select_account_a1"


@pytest.mark.anyio
async def test_handle_start_command_authorized_complete(handler, container, update, context):
    # Setup
    user_config = UserConfiguration(telegram_id=123, status=UserStatus.AUTHORIZED)
    container.get_auth_service().register_user.return_value = user_config
    container.get_onboarding_service().get_onboarding_step.return_value = OnboardingStep.COMPLETE
    
    # Run
    await handler.handle_start_command(update, context)
    
    # Verify
    # send_message (inherited from BaseHandler) uses reply_text internally
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "todo listo" in args[0].lower()


@pytest.mark.anyio
async def test_handle_start_command_pending(handler, container, update, context):
    # Setup
    user_config = UserConfiguration(telegram_id=123, status=UserStatus.PENDING)
    container.get_auth_service().register_user.return_value = user_config
    
    # Run
    await handler.handle_start_command(update, context)
    
    # Verify
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "pendiente" in args[0].lower()


@pytest.mark.anyio
async def test_handle_start_command_blocked(handler, container, update, context):
    # Setup
    user_config = UserConfiguration(telegram_id=123, status=UserStatus.BLOCKED)
    container.get_auth_service().register_user.return_value = user_config
    
    # Run
    await handler.handle_start_command(update, context)
    
    # Verify
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "restringido" in args[0].lower() or "bloqueado" in args[0].lower()

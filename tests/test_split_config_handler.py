import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import Update, CallbackQuery, Message, User
from telegram.ext import ContextTypes

from presentation.telegram.handlers.split_config_handler import SplitConfigHandler
from domain.models.user import UserConfiguration, UserStatus, YNABCategory, YNABAccount
from domain.models.split_config import SplitGroup, SharedAccountConfig

@pytest.fixture
def mock_container(mock_split_config_service, mock_user_config_service, mock_auth_service):
    container = MagicMock()
    container.get_split_config_service.return_value = mock_split_config_service
    container.get_user_config_service.return_value = mock_user_config_service
    container.get_authorization_service.return_value = mock_auth_service
    return container

@pytest.fixture
def mock_split_config_service():
    service = MagicMock()
    service.get_available_categories_for_split.return_value = []
    service.get_available_accounts_for_split.return_value = []
    service.get_split_config_summary.return_value = {"groups": [], "shared_account": None, "configured": False}
    service.add_split_group.return_value = SplitGroup(id=1, telegram_id=123, category_id="c1", category_name="Cat 1", person_aliases=[])
    service.remove_split_group.return_value = True
    service.add_person_alias.return_value = True
    service.remove_person_alias.return_value = True
    service.set_shared_account.return_value = SharedAccountConfig(telegram_id=123, account_id="a1", account_name="Acc 1")
    service.remove_shared_account.return_value = True
    return service

@pytest.fixture
def mock_user_config_service():
    service = MagicMock()
    service.get_or_create_user_config.return_value = None
    return service

@pytest.fixture
def mock_auth_service():
    service = MagicMock()
    service.register_user.side_effect = lambda u: UserConfiguration(telegram_id=u.id, status=UserStatus.AUTHORIZED)
    return service

@pytest.fixture
def handler(mock_container):
    return SplitConfigHandler(mock_container)

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_handle_splitwise_command_not_configured(handler, mock_user_config_service):
    update = MagicMock(spec=Update)
    update.effective_user.id = 123
    update.message = AsyncMock(spec=Message)
    update.callback_query = None
    
    # User not configured
    mock_user_config_service.get_or_create_user_config.return_value = UserConfiguration(telegram_id=123, status=UserStatus.AUTHORIZED)
    
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handler.handle_splitwise_command(update, context)
    
    # Should send "no budget configured" message
    update.message.reply_text.assert_called_once()
    assert "Presupuesto no configurado" in update.message.reply_text.call_args[0][0]

@pytest.mark.anyio
async def test_handle_splitwise_command_success(handler, mock_user_config_service):
    update = MagicMock(spec=Update)
    update.effective_user.id = 123
    update.message = AsyncMock(spec=Message)
    update.callback_query = None
    
    # User fully configured
    mock_user_config_service.get_or_create_user_config.return_value = UserConfiguration(
        telegram_id=123, status=UserStatus.AUTHORIZED, budget_id="b1", default_account_id="a1"
    )
    
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handler.handle_splitwise_command(update, context)
    
    # Should send split panel
    update.message.reply_text.assert_called_once()
    assert "Gastos Compartidos" in update.message.reply_text.call_args[0][0]
    assert update.message.reply_text.call_args[1]['reply_markup'] is not None

@pytest.mark.anyio
async def test_handle_callback_add_group(handler, mock_split_config_service):
    query = AsyncMock(spec=CallbackQuery)
    query.data = "split_add_group"
    query.message = AsyncMock(spec=Message)
    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_user.id = 123
    update.message = None
    
    mock_split_config_service.get_available_categories_for_split.return_value = [
        YNABCategory(id="c1", name="Cat 1", group_name="G", full_name="G: Cat 1")
    ]
    
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    
    await handler.handle_callback_query(update, context)
    
    query.answer.assert_called_once()
    query.edit_message_text.assert_called_once()
    assert "Selecciona la categoría" in query.edit_message_text.call_args[0][0]

@pytest.mark.anyio
async def test_handle_alias_text_message_success(handler, mock_split_config_service):
    update = MagicMock(spec=Update)
    update.effective_user.id = 123
    update.message = AsyncMock(spec=Message)
    update.message.text = "Juan"
    update.callback_query = None
    
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {"pending_alias_category_id": "cat-123"}
    
    mock_split_config_service.get_split_config_summary.return_value = {
        "groups": [SplitGroup(id=1, telegram_id=123, category_id="cat-123", category_name="Gastos Compartidos", person_aliases=[])],
        "shared_account": None,
        "configured": True
    }
    mock_split_config_service.add_person_alias.return_value = True
    
    handled = await handler.handle_alias_text_message(update, context)
    
    assert handled is True
    assert "pending_alias_category_id" not in context.user_data
    mock_split_config_service.add_person_alias.assert_called_with(123, "cat-123", "Juan")
    # Should send confirmation and panel
    assert update.message.reply_text.call_count == 2
    assert "Alias *Juan* agregado" in update.message.reply_text.call_args_list[0][0][0]
    assert "Gastos Compartidos" in update.message.reply_text.call_args_list[1][0][0]

@pytest.mark.anyio
async def test_handle_alias_text_message_not_pending(handler):
    update = MagicMock(spec=Update)
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {} # No pending alias
    
    handled = await handler.handle_alias_text_message(update, context)
    
    assert handled is False

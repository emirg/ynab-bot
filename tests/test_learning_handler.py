import pytest
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from presentation.telegram.handlers.learning_handler import LearningHandler
from domain.models.user import UserStatus

@pytest.fixture
def container():
    mock = MagicMock()
    # Setup common services
    auth_service = MagicMock()
    # By default, authorize all users for these tests
    auth_service.get_user_status.return_value = UserStatus.AUTHORIZED
    mock.get_auth_service.return_value = auth_service
    
    # Container.get(LearningService) etc.
    mock.get.side_effect = lambda cls: MagicMock()
    return mock

@pytest.fixture
def handler(container):
    return LearningHandler(container)

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
    message_mock.text = ""
    mock.message = message_mock
    mock.callback_query = None
    return mock

@pytest.fixture
def context():
    mock = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    mock.args = []
    return mock

@pytest.mark.anyio
async def test_handle_learning_dashboard_command(handler, container, update, context):
    # Setup
    learning_service = handler.learning_service
    learning_service.format_learning_dashboard_message.return_value = "Panel content"
    
    # Run
    await handler.handle_learning_dashboard_command(update, context)
    
    # Verify
    learning_service.format_learning_dashboard_message.assert_called_once_with(123)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "Panel content" in args[0]

@pytest.mark.anyio
async def test_handle_forget_command_no_args(handler, update, context):
    # Run
    context.args = []
    await handler.handle_forget_command(update, context)
    
    # Verify
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "Uso del comando /olvidar" in args[0]

@pytest.mark.anyio
async def test_handle_forget_command_with_args(handler, update, context):
    # Setup
    context.args = ["McDonald's"]
    learning_service = handler.learning_service
    learning_service.forget_payee.return_value = True
    learning_service.format_forget_result_message.return_value = "He olvidado McDonald's"
    
    # Run
    await handler.handle_forget_command(update, context)
    
    # Verify
    learning_service.forget_payee.assert_called_once_with(123, "McDonald's")
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "He olvidado McDonald's" in args[0]

@pytest.mark.anyio
async def test_handle_correction_command_no_args(handler, update, context):
    context.args = []
    await handler.handle_correction_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "Uso del comando /corregir" in args[0]

@pytest.mark.anyio
async def test_handle_correction_command_invalid_number(handler, update, context):
    context.args = ['abc', 'Groceries']
    await handler.handle_correction_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "invalido" in args[0].lower() or "inválido" in args[0].lower()

@pytest.mark.anyio
async def test_handle_correction_command_success(handler, update, context):
    context.args = ['1', 'Groceries']
    handler.expense_service.correct_recent_transaction.return_value = {
        'payee': 'McDonalds',
        'old_category_name': 'Comida rapida',
        'new_category_name': 'Groceries',
        'ynab_updated': False,
    }
    await handler.handle_correction_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'Groceries' in args[0]

@pytest.mark.anyio
async def test_handle_correction_command_success_with_ynab_update(handler, update, context):
    context.args = ['1', 'Groceries']
    handler.expense_service.correct_recent_transaction.return_value = {
        'payee': 'McDonalds',
        'old_category_name': 'Comida rapida',
        'new_category_name': 'Groceries',
        'ynab_updated': True,
    }
    await handler.handle_correction_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'YNAB' in args[0]

@pytest.mark.anyio
async def test_handle_correction_command_category_not_found(handler, update, context):
    context.args = ['1', 'NonExistent']
    handler.expense_service.correct_recent_transaction.return_value = {
        'error': "No encontre una categoria que coincida con 'NonExistent'. Verifica el nombre e intenta de nuevo."
    }
    await handler.handle_correction_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'NonExistent' in args[0]

@pytest.mark.anyio
async def test_handle_correction_command_failure(handler, update, context):
    context.args = ['1', 'Groceries']
    handler.expense_service.correct_recent_transaction.return_value = None
    await handler.handle_correction_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "No se pudo" in args[0]

@pytest.mark.anyio
async def test_handle_routing_aprendizaje(handler, update, context):
    # Setup
    update.message.text = "/aprendizaje"
    handler.handle_learning_dashboard_command = AsyncMock()
    
    # Run
    await handler.handle(update, context)
    
    # Verify
    handler.handle_learning_dashboard_command.assert_called_once_with(update, context)

@pytest.mark.anyio
async def test_handle_routing_olvidar(handler, update, context):
    # Setup
    update.message.text = "/olvidar McDonald's"
    handler.handle_forget_command = AsyncMock()
    
    # Run
    await handler.handle(update, context)
    
    # Verify
    handler.handle_forget_command.assert_called_once_with(update, context)

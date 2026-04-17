import pytest
import base64
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
from decimal import Decimal

from presentation.telegram.handlers.expense_handler import ExpenseHandler
from domain.models.expense import Expense, ExpenseResult
from domain.exceptions import ImageProcessingException

@pytest.fixture
def container():
    mock_container = MagicMock()
    mock_auth_service = MagicMock()
    mock_auth_service.is_user_authorized.return_value = True
    mock_container.get_auth_service.return_value = mock_auth_service
    return mock_container

@pytest.fixture
def handler(container):
    with patch('presentation.telegram.handlers.expense_handler.ExpenseService'), \
         patch('presentation.telegram.handlers.expense_handler.SpeechToTextProcessor'), \
         patch('presentation.telegram.handlers.expense_handler.ExpenseResponseFormatter'), \
         patch('presentation.telegram.handlers.expense_handler.BudgetQueryFormatter'):
        h = ExpenseHandler(container)
        h.send_message = AsyncMock()
        h.send_error_message = AsyncMock()
        return h

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
class TestHandlePhotoMessage:

    async def test_handle_photo_message_success(self, handler):
        # Setup mocks
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Test User"
        update.message.caption = "almuerzo"
        update.message.reply_text = AsyncMock()
        
        photo = MagicMock()
        photo_file = AsyncMock()
        photo_file.file_size = 1024
        photo_file.download_to_drive = AsyncMock()
        photo.get_file = AsyncMock(return_value=photo_file)
        update.message.photo = [photo]
        
        expense = Expense(amount=Decimal('25000'), payee='McDonalds', memo='test', confidence=0.9)
        handler.expense_service.process_receipt_image.return_value = ExpenseResult.success_result(expense, 'txn-123')
        handler.formatter.format_success.return_value = "Success message"
        
        # Patch open to avoid actual file I/O and os.unlink
        with patch("builtins.open", mock_open(read_data=b"fake-image-data")), \
             patch("os.unlink"):
            await handler.handle_photo_message(update, None)
        
        # Verify
        handler.expense_service.process_receipt_image.assert_called_once()
        args, kwargs = handler.expense_service.process_receipt_image.call_args
        assert args[0] == 123
        assert args[1] == base64.b64encode(b"fake-image-data").decode('utf-8')
        assert args[2] == "almuerzo"
        
        update.message.reply_text.assert_any_call("📸 Analizando recibo...")
        handler.send_message.assert_called_once()
        assert "Recibo analizado" in handler.send_message.call_args[0][1]

    async def test_handle_photo_message_too_large(self, handler):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Test User"
        photo = MagicMock()
        photo_file = AsyncMock()
        photo_file.file_size = 6 * 1024 * 1024  # 6MB
        photo.get_file = AsyncMock(return_value=photo_file)
        update.message.photo = [photo]
        
        await handler.handle_photo_message(update, None)
        
        handler.send_error_message.assert_called_once()
        assert "demasiado grande" in handler.send_error_message.call_args[0][1]

    async def test_handle_photo_message_service_error(self, handler):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Test User"
        update.message.reply_text = AsyncMock()
        photo = MagicMock()
        photo_file = AsyncMock()
        photo_file.file_size = 1024
        photo_file.download_to_drive = AsyncMock()
        photo.get_file = AsyncMock(return_value=photo_file)
        update.message.photo = [photo]
        
        handler.expense_service.process_receipt_image.return_value = ExpenseResult.error_result("Service Error")
        handler.formatter.format_error.return_value = "Formatted Error"
        
        with patch("builtins.open", mock_open(read_data=b"data")), \
             patch("os.unlink"):
            await handler.handle_photo_message(update, None)
            
        handler.send_message.assert_called_once_with(update, "Formatted Error")

@pytest.mark.anyio
class TestHandleRouting:

    async def test_handle_routes_to_photo(self, handler):
        update = MagicMock()
        update.message.voice = None
        update.message.photo = [MagicMock()]
        update.message.text = None
        
        with patch.object(handler, 'handle_photo_message', new_callable=AsyncMock) as mock_photo:
            await handler.handle(update, None)
            mock_photo.assert_called_once()

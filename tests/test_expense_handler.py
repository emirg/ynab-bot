"""Tests for ExpenseHandler error handling — verifying Spanish user_message reaches the user."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from presentation.telegram.handlers.expense_handler import ExpenseHandler
from domain.exceptions import SpeechProcessingException, ImageProcessingException


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
        # Mock send_message (the actual Telegram call) but leave send_error_message real
        h.send_message = AsyncMock()
        return h


def make_update(user_id=123):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.full_name = "Test User"
    update.effective_user.username = "testuser"
    update.callback_query = None
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
class TestExpenseHandlerErrorMessages:
    """Verify that specific exception types surface their Spanish user_message to the user."""

    async def test_speech_exception_shows_user_message(self, handler):
        """SpeechProcessingException should show its Spanish user_message, not the technical string."""
        update = make_update()
        voice_file = AsyncMock()
        voice_file.file_size = 100  # small enough
        voice_file.download_to_drive = AsyncMock()
        update.message.voice.get_file = AsyncMock(return_value=voice_file)

        exc = SpeechProcessingException("whisper API timeout")

        import tempfile
        with patch('tempfile.NamedTemporaryFile') as mock_ntf, \
             patch('os.unlink'), \
             patch.object(handler.speech_processor, 'transcribe_audio', side_effect=exc):
            # make NamedTemporaryFile work as context manager
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            mock_file.name = '/tmp/fake.ogg'
            mock_ntf.return_value = mock_file

            await handler.handle_voice_message(update, None)

        handler.send_message.assert_called_once()
        sent_text = handler.send_message.call_args[0][1]
        assert "No pude procesar el mensaje de voz" in sent_text
        # Technical details should NOT appear
        assert "whisper API timeout" not in sent_text

    async def test_image_exception_shows_user_message(self, handler):
        """ImageProcessingException should show its Spanish user_message, not the technical string."""
        update = make_update()
        photo = MagicMock()
        photo_file = AsyncMock()
        photo_file.file_size = 1024
        photo_file.download_to_drive = AsyncMock()
        photo.get_file = AsyncMock(return_value=photo_file)
        update.message.photo = [photo]
        update.message.caption = None

        exc = ImageProcessingException("OpenAI vision error 503")

        with patch('builtins.open', side_effect=exc), \
             patch('os.unlink'):
            await handler.handle_photo_message(update, None)

        handler.send_message.assert_called_once()
        sent_text = handler.send_message.call_args[0][1]
        assert "No pude analizar la imagen" in sent_text
        assert "OpenAI vision error 503" not in sent_text

    async def test_generic_exception_in_text_handler_shows_fallback_spanish(self, handler):
        """Generic Exception in handle_text_message should show the Spanish fallback message."""
        update = make_update()
        update.message.text = "almuerzo 25000"

        handler.expense_service.process_message.side_effect = RuntimeError("DB connection lost")

        await handler.handle_text_message(update, None)

        handler.send_message.assert_called_once()
        sent_text = handler.send_message.call_args[0][1]
        assert "Ocurrió un error procesando tu mensaje" in sent_text
        assert "DB connection lost" not in sent_text

    async def test_generic_exception_in_voice_handler_shows_fallback_spanish(self, handler):
        """Generic Exception in handle_voice_message should show the Spanish fallback message."""
        update = make_update()
        # Make get_file raise a generic exception
        update.message.voice.get_file = AsyncMock(side_effect=RuntimeError("network error"))

        await handler.handle_voice_message(update, None)

        handler.send_message.assert_called_once()
        sent_text = handler.send_message.call_args[0][1]
        assert "Ocurrió un error procesando el mensaje de voz" in sent_text
        assert "network error" not in sent_text

    async def test_generic_exception_in_photo_handler_shows_fallback_spanish(self, handler):
        """Generic Exception in handle_photo_message should show the Spanish fallback message."""
        update = make_update()
        update.message.photo = [MagicMock()]
        update.message.photo[-1].get_file = AsyncMock(side_effect=RuntimeError("timeout"))

        await handler.handle_photo_message(update, None)

        handler.send_message.assert_called_once()
        sent_text = handler.send_message.call_args[0][1]
        assert "Ocurrió un error procesando la imagen" in sent_text
        assert "timeout" not in sent_text

    async def test_send_error_message_called_with_exception_for_speech(self, handler):
        """Verify send_error_message receives the exception kwarg for SpeechProcessingException."""
        update = make_update()
        voice_file = AsyncMock()
        voice_file.file_size = 100
        voice_file.download_to_drive = AsyncMock()
        update.message.voice.get_file = AsyncMock(return_value=voice_file)

        exc = SpeechProcessingException("test error")

        # Override send_error_message to capture arguments, but still call real impl
        original_sem = handler.send_error_message.__func__ if hasattr(handler.send_error_message, '__func__') else None
        captured_calls = []

        async def capturing_sem(upd, msg, exception=None):
            captured_calls.append({'msg': msg, 'exception': exception})
            # Also call the real implementation to test end-to-end
            from presentation.telegram.handlers.base_handler import BaseHandler
            await BaseHandler.send_error_message(handler, upd, msg, exception=exception)

        handler.send_error_message = capturing_sem

        with patch('tempfile.NamedTemporaryFile') as mock_ntf, \
             patch('os.unlink'), \
             patch.object(handler.speech_processor, 'transcribe_audio', side_effect=exc):
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            mock_file.name = '/tmp/fake.ogg'
            mock_ntf.return_value = mock_file

            await handler.handle_voice_message(update, None)

        assert len(captured_calls) == 1
        assert captured_calls[0]['exception'] is exc

    async def test_send_error_message_called_with_exception_for_image(self, handler):
        """Verify send_error_message receives the exception kwarg for ImageProcessingException."""
        update = make_update()
        photo = MagicMock()
        photo_file = AsyncMock()
        photo_file.file_size = 1024
        photo_file.download_to_drive = AsyncMock()
        photo.get_file = AsyncMock(return_value=photo_file)
        update.message.photo = [photo]
        update.message.caption = None

        exc = ImageProcessingException("processing failed")
        captured_calls = []

        async def capturing_sem(upd, msg, exception=None):
            captured_calls.append({'msg': msg, 'exception': exception})
            from presentation.telegram.handlers.base_handler import BaseHandler
            await BaseHandler.send_error_message(handler, upd, msg, exception=exception)

        handler.send_error_message = capturing_sem

        with patch('builtins.open', side_effect=exc), \
             patch('os.unlink'):
            await handler.handle_photo_message(update, None)

        assert len(captured_calls) == 1
        assert captured_calls[0]['exception'] is exc

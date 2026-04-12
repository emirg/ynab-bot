"""Tests for ExpenseHandler error handling — verifying Spanish user_message reaches the user."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call

from domain.models.expense import PreparedExpense
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


# ---------------------------------------------------------------------------
# Helpers shared by confirmation-flow tests
# ---------------------------------------------------------------------------

def make_expense_result(success=True, transaction_id=None):
    """Build a minimal mock ExpenseResult."""
    r = MagicMock()
    r.success = success
    r.transaction_id = transaction_id
    return r


def make_prepared(intent='expense'):
    """Build a minimal PreparedExpense as returned by expense_service.prepare_*."""
    expense = MagicMock()
    expense_result = make_expense_result(success=True, transaction_id=None)
    return PreparedExpense(
        expense=expense,
        budget_id='budget-1',
        account_id='account-1',
        user_config=MagicMock(),
        expense_result=expense_result,
        intent=intent,
    )


@pytest.fixture
def handler_conf(container):
    """Handler fixture for confirmation-flow tests with user_config_service mocked."""
    with patch('presentation.telegram.handlers.expense_handler.ExpenseService'), \
         patch('presentation.telegram.handlers.expense_handler.SpeechToTextProcessor'), \
         patch('presentation.telegram.handlers.expense_handler.ExpenseResponseFormatter'), \
         patch('presentation.telegram.handlers.expense_handler.BudgetQueryFormatter'):
        h = ExpenseHandler(container)
        h.send_message = AsyncMock()
        # Mock the full user_config_service on the handler
        h.user_config_service = MagicMock()
        h.user_config_service.get_user_status.return_value = {'timezone': 'America/Bogota'}
        h.user_config_service.get_confirmation_mode.return_value = False
        return h


def make_update_with_text(user_id=123, text="almuerzo 25000"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.full_name = "Test User"
    update.effective_user.username = "testuser"
    update.callback_query = None
    update.message.reply_text = AsyncMock()
    update.message.text = text
    return update


def make_context(user_data=None):
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.args = []
    return ctx


# ---------------------------------------------------------------------------
# Confirmation-flow tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestConfirmationFlow:
    """Tests for the confirmation preview + callback flow."""

    async def test_text_message_confirmation_off_commits_directly(self, handler_conf):
        """With confirmation OFF the existing process_message path is used (no pending stored)."""
        handler = handler_conf
        handler.user_config_service.get_confirmation_mode.return_value = False

        mock_result = MagicMock()
        mock_result.intent = 'expense'
        mock_result.expense_result = make_expense_result(success=True, transaction_id='txn-1')
        handler.expense_service.process_message.return_value = mock_result
        handler.formatter.format_success.return_value = "Gasto registrado"

        update = make_update_with_text()
        ctx = make_context()

        await handler.handle_text_message(update, ctx)

        handler.expense_service.process_message.assert_called_once()
        handler.expense_service.prepare_expense.assert_not_called()
        assert "pending_expense" not in ctx.user_data
        handler.send_message.assert_called_once()

    async def test_text_message_confirmation_on_shows_preview_with_keyboard(self, handler_conf):
        """With confirmation ON, prepare is called, pending stored, preview+keyboard sent, no commit."""
        handler = handler_conf
        handler.user_config_service.get_confirmation_mode.return_value = True

        prepared = make_prepared(intent='expense')
        # shared_expense prepare raises so regular prepare is used
        handler.expense_service.prepare_shared_expense.side_effect = Exception("no split group")
        handler.expense_service.prepare_expense.return_value = prepared
        handler.formatter.format_preview.return_value = "Voy a registrar: almuerzo"

        update = make_update_with_text()
        ctx = make_context()

        await handler.handle_text_message(update, ctx)

        handler.expense_service.prepare_expense.assert_called_once()
        handler.expense_service.commit_expense.assert_not_called()
        assert ctx.user_data["pending_expense"]["prepared"] is prepared
        assert ctx.user_data["pending_expense"]["source"] == "text"
        # send_message called with keyboard (reply_markup keyword arg)
        handler.send_message.assert_called_once()
        _, kwargs = handler.send_message.call_args
        assert kwargs.get('reply_markup') is not None

    async def test_new_expense_overwrites_pending(self, handler_conf):
        """Sending a second expense with confirmation ON overwrites the previous pending."""
        handler = handler_conf
        handler.user_config_service.get_confirmation_mode.return_value = True

        first_prepared = make_prepared(intent='expense')
        second_prepared = make_prepared(intent='expense')
        second_prepared.budget_id = 'budget-2'

        handler.expense_service.prepare_shared_expense.side_effect = Exception("no split")
        handler.expense_service.prepare_expense.side_effect = [first_prepared, second_prepared]
        handler.formatter.format_preview.return_value = "preview"

        update = make_update_with_text()
        ctx = make_context()

        await handler.handle_text_message(update, ctx)
        assert ctx.user_data["pending_expense"]["prepared"].budget_id == 'budget-1'

        await handler.handle_text_message(update, ctx)
        assert ctx.user_data["pending_expense"]["prepared"].budget_id == 'budget-2'

    async def test_confirm_callback_commits_and_clears_pending(self, handler_conf):
        """confirm_expense callback calls commit_expense, sends success, clears pending."""
        handler = handler_conf
        prepared = make_prepared(intent='expense')
        committed_result = make_expense_result(success=True, transaction_id='txn-42')
        handler.expense_service.commit_expense.return_value = committed_result
        handler.formatter.format_success.return_value = "Gasto registrado exitosamente"

        query = MagicMock()
        query.answer = AsyncMock()
        query.data = 'confirm_expense'
        query.message.reply_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        update.effective_user.id = 123

        ctx = make_context(user_data={"pending_expense": {'prepared': prepared, 'source': 'text'}})

        await handler.handle_confirmation_callback(update, ctx)

        handler.expense_service.commit_expense.assert_called_once_with(
            123, prepared.expense, prepared.budget_id, prepared.account_id
        )
        assert "pending_expense" not in ctx.user_data
        query.message.reply_text.assert_called_once()
        args = query.message.reply_text.call_args[0]
        assert "Gasto registrado exitosamente" in args[0]

    async def test_confirm_callback_shared_expense_calls_commit_shared(self, handler_conf):
        """confirm_expense callback routes to commit_shared_expense for shared intents."""
        handler = handler_conf
        prepared = make_prepared(intent='shared_expense')
        committed_result = make_expense_result(success=True, transaction_id='txn-99')
        handler.expense_service.commit_shared_expense.return_value = committed_result
        handler.formatter.format_success.return_value = "Gasto compartido registrado"

        query = MagicMock()
        query.answer = AsyncMock()
        query.data = 'confirm_expense'
        query.message.reply_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        update.effective_user.id = 123

        ctx = make_context(user_data={"pending_expense": {'prepared': prepared, 'source': 'text'}})

        await handler.handle_confirmation_callback(update, ctx)

        handler.expense_service.commit_shared_expense.assert_called_once()
        assert "pending_expense" not in ctx.user_data

    async def test_cancel_callback_clears_pending_and_sends_message(self, handler_conf):
        """cancel_expense callback clears pending and sends cancellation message."""
        handler = handler_conf
        prepared = make_prepared()

        query = MagicMock()
        query.answer = AsyncMock()
        query.data = 'cancel_expense'
        query.message.reply_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        update.effective_user.id = 123

        ctx = make_context(user_data={"pending_expense": {'prepared': prepared, 'source': 'text'}})

        await handler.handle_confirmation_callback(update, ctx)

        assert "pending_expense" not in ctx.user_data
        query.message.reply_text.assert_called_once()
        text = query.message.reply_text.call_args[0][0]
        assert "cancelado" in text.lower()

    async def test_stale_confirm_callback_returns_invalid_message(self, handler_conf):
        """confirm_expense with no pending_expense returns the stale-button message."""
        handler = handler_conf

        query = MagicMock()
        query.answer = AsyncMock()
        query.data = 'confirm_expense'
        query.message.reply_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        update.effective_user.id = 123

        ctx = make_context(user_data={})  # no pending

        await handler.handle_confirmation_callback(update, ctx)

        handler.expense_service.commit_expense.assert_not_called()
        query.message.reply_text.assert_called_once()
        text = query.message.reply_text.call_args[0][0]
        assert "válida" in text or "valida" in text

    async def test_stale_cancel_callback_returns_invalid_message(self, handler_conf):
        """cancel_expense with no pending_expense returns the stale-button message."""
        handler = handler_conf

        query = MagicMock()
        query.answer = AsyncMock()
        query.data = 'cancel_expense'
        query.message.reply_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        update.effective_user.id = 123

        ctx = make_context(user_data={})

        await handler.handle_confirmation_callback(update, ctx)

        query.message.reply_text.assert_called_once()
        text = query.message.reply_text.call_args[0][0]
        assert "válida" in text or "valida" in text


@pytest.mark.anyio
class TestConfirmacionCommand:
    """Tests for /confirmacion on|off command."""

    async def test_confirmacion_on_activates_and_replies(self, handler_conf):
        """'/confirmacion on' calls set_confirmation_mode(True) and shows activation message."""
        handler = handler_conf
        handler.user_config_service.set_confirmation_mode.return_value = MagicMock()

        update = make_update_with_text(text="/confirmacion on")
        ctx = make_context()
        ctx.args = ['on']

        await handler.handle_confirmacion_command(update, ctx)

        handler.user_config_service.set_confirmation_mode.assert_called_once_with(123, True)
        handler.send_message.assert_called_once()
        text = handler.send_message.call_args[0][1]
        assert "activada" in text.lower()

    async def test_confirmacion_off_deactivates_and_replies(self, handler_conf):
        """'/confirmacion off' calls set_confirmation_mode(False) and shows deactivation message."""
        handler = handler_conf
        handler.user_config_service.set_confirmation_mode.return_value = MagicMock()

        update = make_update_with_text(text="/confirmacion off")
        ctx = make_context()
        ctx.args = ['off']

        await handler.handle_confirmacion_command(update, ctx)

        handler.user_config_service.set_confirmation_mode.assert_called_once_with(123, False)
        handler.send_message.assert_called_once()
        text = handler.send_message.call_args[0][1]
        assert "desactivada" in text.lower()

    async def test_confirmacion_no_args_shows_current_state(self, handler_conf):
        """'/confirmacion' with no args shows current state and usage."""
        handler = handler_conf
        handler.user_config_service.get_confirmation_mode.return_value = False

        update = make_update_with_text(text="/confirmacion")
        ctx = make_context()
        ctx.args = []

        await handler.handle_confirmacion_command(update, ctx)

        handler.user_config_service.set_confirmation_mode.assert_not_called()
        handler.send_message.assert_called_once()
        text = handler.send_message.call_args[0][1]
        assert "confirmacion" in text.lower() or "confirmación" in text.lower()
        assert "on" in text.lower() or "off" in text.lower()

    async def test_confirmacion_invalid_arg_shows_current_state(self, handler_conf):
        """'/confirmacion maybe' with invalid arg shows current state and usage."""
        handler = handler_conf
        handler.user_config_service.get_confirmation_mode.return_value = True

        update = make_update_with_text(text="/confirmacion maybe")
        ctx = make_context()
        ctx.args = ['maybe']

        await handler.handle_confirmacion_command(update, ctx)

        handler.user_config_service.set_confirmation_mode.assert_not_called()
        handler.send_message.assert_called_once()
        text = handler.send_message.call_args[0][1]
        # Shows current state — True → "activada"
        assert "activada" in text.lower()

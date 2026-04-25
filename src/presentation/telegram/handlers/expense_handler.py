import os
import tempfile
import logging
import base64
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import ExpenseResponseFormatter, BudgetQueryFormatter
from presentation.telegram.middleware.auth_middleware import require_authentication
from presentation.telegram.keyboards import build_confirmation_keyboard
from application.services.expense_service import ExpenseService
from application.services.user_config_service import UserConfigService
from integrations.speech_to_text import SpeechToTextProcessor
from domain.exceptions import SpeechProcessingException, ImageProcessingException, ExpenseParsingException, UserNotConfiguredException
from domain.time_utils import DEFAULT_TIMEZONE

logger = logging.getLogger(__name__)


class ExpenseHandler(BaseHandler):
    """Handler for expense message processing"""

    def __init__(self, container):
        super().__init__(container)
        self.expense_service = container.get(ExpenseService)
        self.user_config_service = container.get_user_config_service()
        self.speech_processor = container.get(SpeechToTextProcessor)
        self.formatter = ExpenseResponseFormatter()
        self.query_formatter = BudgetQueryFormatter()

    def _get_user_timezone(self, user_id: int) -> str:
        """Get the user's configured timezone, falling back to default."""
        try:
            status = self.user_config_service.get_user_status(user_id)
            return status.get('timezone', DEFAULT_TIMEZONE)
        except Exception:
            return DEFAULT_TIMEZONE

    def _get_user_confirmation_mode(self, user_id: int) -> bool:
        """Return True if the user has confirmation mode enabled."""
        try:
            return bool(self.user_config_service.get_confirmation_mode(user_id))
        except Exception:
            return False

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_confirmacion_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /confirmacion on|off command."""
        self.log_handler_start("ExpenseHandler.handle_confirmacion_command", update)
        user_id = self.get_user_id(update)

        args = context.args if context.args else []
        arg = args[0].lower() if args else None

        if arg == 'on':
            self.user_config_service.set_confirmation_mode(user_id, True)
            response = (
                "✅ Confirmación activada. El bot te pedirá confirmar antes de "
                "registrar cada gasto."
            )
        elif arg == 'off':
            self.user_config_service.set_confirmation_mode(user_id, False)
            response = (
                "❌ Confirmación desactivada. Los gastos se registrarán directamente."
            )
        else:
            # Show current state and usage
            enabled = self._get_user_confirmation_mode(user_id)
            state = "activada ✅" if enabled else "desactivada ❌"
            response = (
                f"La confirmación previa está actualmente *{state}*.\n\n"
                "Uso: `/confirmacion on` o `/confirmacion off`"
            )

        await self.send_message(update, response)
        self.log_handler_success("ExpenseHandler.handle_confirmacion_command", update)

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text expense messages"""
        self.log_handler_start("ExpenseHandler.handle_text_message", update)

        try:
            user_id = self.get_user_id(update)
            message = update.message.text
            user_tz = self._get_user_timezone(user_id)

            # Try to determine intent via prepare (handles both expense and shared_expense)
            # We use process_message to keep the existing query path intact.
            # For the confirmation flow we must call prepare_* directly.

            # First, attempt shared expense path if split group matches, otherwise regular expense.
            # To keep things clean, we rely on process_message for intent detection but then
            # re-route through prepare_* when confirmation is ON.
            confirm_mode = self._get_user_confirmation_mode(user_id) and context is not None

            if not confirm_mode:
                # Original behavior: prepare + commit in one call via process_message
                result = self.expense_service.process_message(user_id, message)

                if result.intent == 'query':
                    response = self.query_formatter.format_response(result.query_result)
                    self.log_handler_success("ExpenseHandler.handle_text_message", update)
                elif result.intent in ('expense', 'shared_expense'):
                    if result.expense_result and result.expense_result.success:
                        response = self.formatter.format_success(result.expense_result, user_tz=user_tz)
                        self.log_handler_success("ExpenseHandler.handle_text_message", update)
                    else:
                        response = self.formatter.format_error(result.expense_result)
                else:
                    response = self.formatter.format_error(result.expense_result)

                await self.send_message(update, response)
                return

            # Confirmation mode ON — try prepare paths
            # First peek at intent via process_message but catch to re-route
            # Instead, we call prepare_expense and prepare_shared_expense selectively.
            # We try shared first (it raises if person alias not found), then regular.
            prepared = None
            intent = None

            try:
                prepared = self.expense_service.prepare_shared_expense(user_id, message)
                intent = 'shared_expense'
            except UserNotConfiguredException:
                raise
            except ExpenseParsingException:
                pass  # Not a shared expense — fall through to regular expense path
            except Exception as e:
                logger.debug(f"prepare_shared_expense raised unexpected exception for user {user_id}: {e}")

            if prepared is None:
                try:
                    prepared = self.expense_service.prepare_expense(user_id, message)
                    intent = 'expense'
                except UserNotConfiguredException:
                    raise
                except Exception as e:
                    # If prepare fails, fall back to process_message for error formatting
                    result = self.expense_service.process_message(user_id, message)
                    if result.intent == 'query':
                        response = self.query_formatter.format_response(result.query_result)
                    else:
                        response = self.formatter.format_error(result.expense_result)
                    await self.send_message(update, response)
                    return

            # Store pending and show preview
            context.user_data["pending_expense"] = {
                'prepared': prepared,
                'source': 'text',
            }
            preview = self.formatter.format_preview(prepared.expense_result, user_tz=user_tz)
            keyboard = build_confirmation_keyboard()
            await self.send_message(update, preview, reply_markup=keyboard)
            self.log_handler_success("ExpenseHandler.handle_text_message", update)

        except Exception as e:
            self.log_handler_error("ExpenseHandler.handle_text_message", update, e)
            await self.send_error_message(update, "Ocurrió un error procesando tu mensaje. Intenta de nuevo.", exception=e)

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice expense messages"""
        self.log_handler_start("ExpenseHandler.handle_voice_message", update)

        if not self.speech_processor:
            await self.send_error_message(update, "Procesamiento de voz no disponible")
            return

        try:
            user_id = self.get_user_id(update)

            # Download voice file
            voice_file = await update.message.voice.get_file()

            # Check file size (limit to ~1MB)
            if voice_file.file_size > 1024 * 1024:
                raise SpeechProcessingException("Archivo de voz demasiado grande (máximo 1MB)", voice_file.file_size)

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
                await voice_file.download_to_drive(temp_file.name)
                temp_file_path = temp_file.name

            try:
                # Convert speech to text
                await update.message.reply_text("🎤 Procesando mensaje de voz...")

                transcribed_text = self.speech_processor.process_telegram_audio(temp_file_path)

                if not transcribed_text or len(transcribed_text.strip()) < 5:
                    raise SpeechProcessingException("No se pudo transcribir el audio o el texto es muy corto")

                logger.debug(
                    "Voice transcribed for user",
                    extra={"user_id": user_id, "transcript_length": len(transcribed_text)},
                )

                user_tz = self._get_user_timezone(user_id)
                confirm_mode = self._get_user_confirmation_mode(user_id) and context is not None

                if not confirm_mode:
                    # Original behavior
                    result = self.expense_service.process_expense_message(user_id, transcribed_text)
                    if result.success:
                        response = f"🎤 *Transcripción:* {transcribed_text}\n\n{self.formatter.format_success(result, user_tz=user_tz)}"
                        self.log_handler_success("ExpenseHandler.handle_voice_message", update)
                    else:
                        response = f"🎤 *Transcripción:* {transcribed_text}\n\n{self.formatter.format_error(result)}"
                    await self.send_message(update, response)
                else:
                    # Confirmation mode ON — prepare and store pending
                    prepared = self.expense_service.prepare_expense(user_id, transcribed_text)
                    context.user_data["pending_expense"] = {
                        'prepared': prepared,
                        'source': 'voice',
                        'transcribed_text': transcribed_text,
                    }
                    preview = (
                        f"🎤 *Transcripción:* {transcribed_text}\n\n"
                        + self.formatter.format_preview(prepared.expense_result, user_tz=user_tz)
                    )
                    keyboard = build_confirmation_keyboard()
                    await self.send_message(update, preview, reply_markup=keyboard)
                    self.log_handler_success("ExpenseHandler.handle_voice_message", update)

            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")

        except SpeechProcessingException as e:
            self.log_handler_error("ExpenseHandler.handle_voice_message", update, e)
            await self.send_error_message(update, str(e), exception=e)
        except Exception as e:
            self.log_handler_error("ExpenseHandler.handle_voice_message", update, e)
            await self.send_error_message(update, "Ocurrió un error procesando el mensaje de voz. Intenta de nuevo.", exception=e)

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo receipt messages"""
        self.log_handler_start("ExpenseHandler.handle_photo_message", update)

        try:
            user_id = self.get_user_id(update)

            # Get the highest resolution photo
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()

            # Check file size (limit to 5MB)
            if photo_file.file_size > 5 * 1024 * 1024:
                raise ImageProcessingException("La imagen es demasiado grande (máximo 5MB)", photo_file.file_size)

            # Send processing message
            await update.message.reply_text("📸 Analizando recibo...")

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                await photo_file.download_to_drive(temp_file.name)
                temp_file_path = temp_file.name

            try:
                # Read and encode to base64
                with open(temp_file_path, "rb") as image_file:
                    image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

                caption = update.message.caption
                user_tz = self._get_user_timezone(user_id)
                confirm_mode = self._get_user_confirmation_mode(user_id) and context is not None

                if not confirm_mode:
                    # Original behavior
                    result = self.expense_service.process_receipt_image(user_id, image_base64, caption)
                    if result.success:
                        response = f"📸 *Recibo analizado*\n\n{self.formatter.format_success(result, user_tz=user_tz)}"
                        self.log_handler_success("ExpenseHandler.handle_photo_message", update)
                    else:
                        response = self.formatter.format_error(result)
                    await self.send_message(update, response)
                else:
                    # Confirmation mode ON — prepare and store pending
                    prepared = self.expense_service.prepare_receipt(user_id, image_base64, caption)
                    context.user_data["pending_expense"] = {
                        'prepared': prepared,
                        'source': 'receipt',
                    }
                    preview = (
                        "📸 *Recibo analizado*\n\n"
                        + self.formatter.format_preview(prepared.expense_result, user_tz=user_tz)
                    )
                    keyboard = build_confirmation_keyboard()
                    await self.send_message(update, preview, reply_markup=keyboard)
                    self.log_handler_success("ExpenseHandler.handle_photo_message", update)

            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")

        except ImageProcessingException as e:
            self.log_handler_error("ExpenseHandler.handle_photo_message", update, e)
            await self.send_error_message(update, str(e), exception=e)
        except Exception as e:
            self.log_handler_error("ExpenseHandler.handle_photo_message", update, e)
            await self.send_error_message(update, "Ocurrió un error procesando la imagen. Intenta de nuevo.", exception=e)

    async def handle_confirmation_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle confirm_expense / cancel_expense inline keyboard callbacks."""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = update.effective_user.id
        user_tz = self._get_user_timezone(user_id)

        if data == 'confirm_expense':
            pending = context.user_data.get("pending_expense")
            prepared = pending.get("prepared") if pending else None
            if not prepared:
                await query.message.reply_text("Esta confirmación ya no es válida.")
                return

            try:
                if prepared.intent == 'shared_expense':
                    result = self.expense_service.commit_shared_expense(user_id, prepared)
                else:
                    result = self.expense_service.commit_expense(
                        user_id,
                        prepared.expense,
                        prepared.budget_id,
                        prepared.account_id,
                    )

                context.user_data.pop("pending_expense", None)
                response = self.formatter.format_success(result, user_tz=user_tz)
                await query.message.reply_text(response, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"commit_expense failed for user {user_id}: {e}")
                await query.message.reply_text(
                    "❌ *Error:* No se pudo registrar el gasto. Intenta de nuevo.",
                    parse_mode='Markdown',
                )

        elif data == 'cancel_expense':
            pending = context.user_data.pop("pending_expense", None)
            if pending is None:
                await query.message.reply_text("Esta confirmación ya no es válida.")
            else:
                await query.message.reply_text("Registro cancelado.")

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main handler entry point"""
        if not update.message:
            return

        if update.message.voice:
            await self.handle_voice_message(update, context)
        elif update.message.photo:
            await self.handle_photo_message(update, context)
        elif update.message.text:
            await self.handle_text_message(update, context)
        else:
            await self.send_error_message(update, "Tipo de mensaje no soportado")

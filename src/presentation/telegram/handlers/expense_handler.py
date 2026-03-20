import os
import tempfile
import logging
import base64
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import ExpenseResponseFormatter, BudgetQueryFormatter
from presentation.telegram.middleware.auth_middleware import require_authentication
from application.services.expense_service import ExpenseService
from application.services.user_config_service import UserConfigService
from integrations.speech_to_text import SpeechToTextProcessor
from domain.exceptions import SpeechProcessingException, ImageProcessingException
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

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text expense messages"""
        self.log_handler_start("ExpenseHandler.handle_text_message", update)

        try:
            user_id = self.get_user_id(update)
            message = update.message.text

            result = self.expense_service.process_message(user_id, message)
            user_tz = self._get_user_timezone(user_id)

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
                
                transcribed_text = self.speech_processor.transcribe_audio(temp_file_path)
                
                if not transcribed_text or len(transcribed_text.strip()) < 5:
                    raise SpeechProcessingException("No se pudo transcribir el audio o el texto es muy corto")
                
                logger.debug(f"Voice transcribed for user {user_id}: '{transcribed_text}'")
                
                # Process as text expense
                result = self.expense_service.process_expense_message(user_id, transcribed_text)
                user_tz = self._get_user_timezone(user_id)

                # Format response with transcription info
                if result.success:
                    response = f"🎤 *Transcripción:* {transcribed_text}\n\n{self.formatter.format_success(result, user_tz=user_tz)}"
                    self.log_handler_success("ExpenseHandler.handle_voice_message", update)
                else:
                    response = f"🎤 *Transcripción:* {transcribed_text}\n\n{self.formatter.format_error(result)}"
                
                await self.send_message(update, response)
                
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
                
                # Process receipt image
                result = self.expense_service.process_receipt_image(user_id, image_base64, caption)
                user_tz = self._get_user_timezone(user_id)

                if result.success:
                    response = f"📸 *Recibo analizado*\n\n{self.formatter.format_success(result, user_tz=user_tz)}"
                    self.log_handler_success("ExpenseHandler.handle_photo_message", update)
                else:
                    response = self.formatter.format_error(result)
                
                await self.send_message(update, response)
                
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

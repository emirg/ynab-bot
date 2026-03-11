import os
import tempfile
import logging
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import ExpenseResponseFormatter, BudgetQueryFormatter
from presentation.telegram.middleware.auth_middleware import require_authentication
from application.services.expense_service import ExpenseService
from integrations.speech_to_text import SpeechToTextProcessor
from domain.exceptions import SpeechProcessingException

logger = logging.getLogger(__name__)


class ExpenseHandler(BaseHandler):
    """Handler for expense message processing"""
    
    def __init__(self, container):
        super().__init__(container)
        self.expense_service = container.get(ExpenseService)
        self.speech_processor = container.get(SpeechToTextProcessor)
        self.formatter = ExpenseResponseFormatter()
        self.query_formatter = BudgetQueryFormatter()
    
    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text expense messages"""
        self.log_handler_start("ExpenseHandler.handle_text_message", update)
        
        try:
            user_id = self.get_user_id(update)
            message = update.message.text

            result = self.expense_service.process_message(user_id, message)

            if result.intent == 'query':
                response = self.query_formatter.format_response(result.query_result)
                self.log_handler_success("ExpenseHandler.handle_text_message", update)
            elif result.expense_result and result.expense_result.success:
                response = self.formatter.format_success(result.expense_result)
                self.log_handler_success("ExpenseHandler.handle_text_message", update)
            else:
                response = self.formatter.format_error(result.expense_result)

            await self.send_message(update, response)

        except Exception as e:
            self.log_handler_error("ExpenseHandler.handle_text_message", update, e)
            await self.send_error_message(update, "Ocurrió un error procesando tu mensaje. Intenta de nuevo.")
    
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
                
                # Format response with transcription info
                if result.success:
                    response = f"🎤 *Transcripción:* {transcribed_text}\n\n{self.formatter.format_success(result)}"
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
            await self.send_error_message(update, f"Error procesando voz: {str(e)}")
        except Exception as e:
            self.log_handler_error("ExpenseHandler.handle_voice_message", update, e)
            await self.send_error_message(update, "Ocurrió un error procesando el mensaje de voz. Intenta de nuevo.")
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main handler entry point"""
        if update.message.voice:
            await self.handle_voice_message(update, context)
        elif update.message.text:
            await self.handle_text_message(update, context)
        else:
            await self.send_error_message(update, "Tipo de mensaje no soportado")
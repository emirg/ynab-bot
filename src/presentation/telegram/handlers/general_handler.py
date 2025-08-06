import logging
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import GeneralResponseFormatter

logger = logging.getLogger(__name__)


class GeneralHandler(BaseHandler):
    """Handler for general commands like /start and /help"""
    
    def __init__(self, container):
        super().__init__(container)
        self.formatter = GeneralResponseFormatter()
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        self.log_handler_start("GeneralHandler.handle_start_command", update)
        
        try:
            message = self.formatter.format_welcome_message()
            await self.send_message(update, message)
            self.log_handler_success("GeneralHandler.handle_start_command", update)
            
        except Exception as e:
            self.log_handler_error("GeneralHandler.handle_start_command", update, e)
            await self.send_error_message(update, f"Error mostrando mensaje de bienvenida: {str(e)}")
    
    async def handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        self.log_handler_start("GeneralHandler.handle_help_command", update)
        
        try:
            message = self.formatter.format_help_message()
            await self.send_message(update, message)
            self.log_handler_success("GeneralHandler.handle_help_command", update)
            
        except Exception as e:
            self.log_handler_error("GeneralHandler.handle_help_command", update, e)
            await self.send_error_message(update, f"Error mostrando ayuda: {str(e)}")
    
    async def handle_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands"""
        self.log_handler_start("GeneralHandler.handle_unknown_command", update)
        
        try:
            command = update.message.text.split()[0] if update.message.text else ""
            
            message = f"""
❓ *Comando no reconocido:* `{command}`

🔹 *Comandos disponibles:*
• `/start` - Mensaje de bienvenida
• `/help` - Ayuda y ejemplos
• `/config` - Configurar presupuesto y cuentas
• `/status` - Ver configuración actual
• `/stats` - Estadísticas de aprendizaje
• `/recent` - Ver transacciones recientes
• `/corregir` - Corregir categorías

💡 *O simplemente envía un mensaje de gasto:*
"Gasté $40000 en comida en Éxito"
            """.strip()
            
            await self.send_message(update, message)
            self.log_handler_success("GeneralHandler.handle_unknown_command", update)
            
        except Exception as e:
            self.log_handler_error("GeneralHandler.handle_unknown_command", update, e)
            await self.send_error_message(update, f"Error procesando comando: {str(e)}")
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main handler entry point"""
        message_text = update.message.text or ""
        
        if message_text.startswith('/start'):
            await self.handle_start_command(update, context)
        elif message_text.startswith('/help'):
            await self.handle_help_command(update, context)
        else:
            await self.handle_unknown_command(update, context)
import logging
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import LearningResponseFormatter
from application.services.learning_service import LearningService
from application.services.expense_service import ExpenseService

logger = logging.getLogger(__name__)


class LearningHandler(BaseHandler):
    """Handler for learning system commands"""
    
    def __init__(self, container):
        super().__init__(container)
        self.learning_service = container.get(LearningService)
        self.expense_service = container.get(ExpenseService)
        self.formatter = LearningResponseFormatter()
    
    async def handle_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - show learning statistics"""
        self.log_handler_start("LearningHandler.handle_stats_command", update)
        
        try:
            stats_message = self.learning_service.format_statistics_message()
            await self.send_message(update, stats_message)
            self.log_handler_success("LearningHandler.handle_stats_command", update)
            
        except Exception as e:
            self.log_handler_error("LearningHandler.handle_stats_command", update, e)
            await self.send_error_message(update, f"Error obteniendo estadísticas: {str(e)}")
    
    async def handle_recent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /recent command - show recent transactions"""
        self.log_handler_start("LearningHandler.handle_recent_command", update)
        
        try:
            # Get limit from command args (default 5)
            limit = 5
            if context.args and len(context.args) > 0:
                try:
                    limit = int(context.args[0])
                    limit = max(1, min(limit, 20))  # Clamp between 1 and 20
                except ValueError:
                    await self.send_error_message(update, "Formato inválido. Usa: `/recent <número>`")
                    return
            
            recent_message = self.learning_service.format_recent_transactions_message(limit)
            await self.send_message(update, recent_message)
            self.log_handler_success("LearningHandler.handle_recent_command", update)
            
        except Exception as e:
            self.log_handler_error("LearningHandler.handle_recent_command", update, e)
            await self.send_error_message(update, f"Error obteniendo transacciones recientes: {str(e)}")
    
    async def handle_correction_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /corregir command - correct recent transaction category"""
        self.log_handler_start("LearningHandler.handle_correction_command", update)
        
        try:
            if not context.args or len(context.args) < 2:
                help_message = """
📝 *Uso del comando /corregir:*

`/corregir <número> <nueva_categoría>`

*Ejemplo:*
`/corregir 1 Groceries`

*Pasos:*
1. Usa `/recent` para ver transacciones recientes
2. Identifica el número de la transacción a corregir
3. Usa `/corregir` con el número y la nueva categoría

💡 *Tip:* La nueva categoría debe ser exactamente como aparece en YNAB
                """.strip()
                await self.send_message(update, help_message)
                return
            
            # Parse arguments
            try:
                transaction_index = int(context.args[0]) - 1  # Convert to 0-based index
                new_category_id = " ".join(context.args[1:])  # Join remaining args as category
            except ValueError:
                await self.send_error_message(update, "Número de transacción inválido")
                return
            
            if transaction_index < 0:
                await self.send_error_message(update, "El número de transacción debe ser mayor a 0")
                return
            
            user_id = self.get_user_id(update)
            
            # Attempt correction
            success = self.expense_service.correct_recent_transaction(
                user_id, transaction_index, new_category_id
            )
            
            if success:
                response = self.formatter.format_correction_success(
                    "Transacción", "Categoría anterior", new_category_id
                )
                await self.send_message(update, response)
                self.log_handler_success("LearningHandler.handle_correction_command", update)
            else:
                await self.send_error_message(update, "No se pudo procesar la corrección. Verifica el número de transacción.")
            
        except Exception as e:
            self.log_handler_error("LearningHandler.handle_correction_command", update, e)
            await self.send_error_message(update, f"Error procesando corrección: {str(e)}")
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main handler entry point"""
        # Determine which command was called
        message_text = update.message.text or ""
        
        if message_text.startswith('/stats'):
            await self.handle_stats_command(update, context)
        elif message_text.startswith('/recent'):
            await self.handle_recent_command(update, context)
        elif message_text.startswith('/corregir'):
            await self.handle_correction_command(update, context)
        else:
            await self.send_error_message(update, "Comando de aprendizaje no reconocido")
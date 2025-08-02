import os
import logging
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

from ynab_client import YNABClient
from smart_expense_parser import SmartExpenseParser

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class YNABTelegramBot:
    """Bot de Telegram para registrar gastos en YNAB con aprendizaje adaptativo"""
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.ynab_token = os.getenv('YNAB_ACCESS_TOKEN')
        self.default_budget_id = os.getenv('YNAB_BUDGET_ID')
        
        if not self.telegram_token or not self.ynab_token:
            raise ValueError("Faltan tokens de configuración. Revisa tu archivo .env")
        
        self.ynab_client = YNABClient(self.ynab_token)
        self.expense_parser = SmartExpenseParser(ynab_client=self.ynab_client)
        
        # Cache para datos del usuario
        self.user_data = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start - Mensaje de bienvenida"""
        welcome_message = """
¡Hola! 👋 Soy tu bot de YNAB para registrar gastos.

🔹 **Comandos disponibles:**
/start - Mostrar este mensaje
/help - Ayuda y ejemplos
/config - Configurar cuentas y categorías
/status - Ver configuración actual

🔹 **Para registrar un gasto, envía un mensaje como:**
• "Gasté $40000 en comida en Éxito"
• "$25000 transporte Uber"
• "30000,50 pesos entretenimiento Netflix"
• "Compré ropa por $80000 en Falabella"

¡Empecemos! Usa /config para configurar tus cuentas y categorías.
        """
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help - Ayuda y ejemplos"""
        examples = self.expense_parser.get_expense_examples()
        help_text = "📝 **Ejemplos de mensajes válidos:**\n\n"
        
        for i, example in enumerate(examples, 1):
            help_text += f"{i}. {example}\n"
        
        help_text += "\n💡 **Consejos:**\n"
        help_text += "• Incluye la cantidad, categoría y lugar (opcional)\n"
        help_text += "• Usa formato colombiano: $40000 o 40000,56 (coma para decimales)\n"
        help_text += "• Puedes usar jerga: '25 lucas', '80k', '150 mil'\n"
        help_text += "• El bot entiende lenguaje natural: 'Almorzé en McDonald's, 25 lucas'\n"
        help_text += "• Reconoce categorías automáticamente con IA\n"
        help_text += "• Usa /config para configurar tus cuentas predeterminadas"
        
        await update.message.reply_text(help_text)
    
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /config - Configuración de cuentas y presupuestos"""
        user_id = update.effective_user.id
        
        try:
            # Obtener presupuestos
            budgets = self.ynab_client.get_budgets()
            if not budgets:
                await update.message.reply_text("❌ No se pudieron obtener los presupuestos. Verifica tu token de YNAB.")
                return
            
            # Crear botones para seleccionar presupuesto
            keyboard = []
            for budget in budgets:
                keyboard.append([InlineKeyboardButton(
                    f"📊 {budget['name']}", 
                    callback_data=f"budget_{budget['id']}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🔧 **Configuración**\n\nSelecciona tu presupuesto:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error en configuración: {e}")
            await update.message.reply_text("❌ Error al obtener la configuración. Verifica tu token de YNAB.")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status - Mostrar configuración actual"""
        user_id = update.effective_user.id
        user_config = self.user_data.get(user_id, {})
        
        status_text = "📊 **Estado actual:**\n\n"
        
        if 'budget_id' in user_config:
            status_text += f"✅ Presupuesto configurado\n"
        else:
            status_text += f"❌ Presupuesto no configurado\n"
        
        if 'default_account_id' in user_config:
            status_text += f"✅ Cuenta predeterminada configurada\n"
        else:
            status_text += f"❌ Cuenta predeterminada no configurada\n"
        
        status_text += f"\n💡 Usa /config para configurar el bot."
        
        await update.message.reply_text(status_text)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los callbacks de botones inline"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if data.startswith('budget_'):
            budget_id = data.replace('budget_', '')
            
            # Guardar presupuesto seleccionado
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            self.user_data[user_id]['budget_id'] = budget_id
            
            # Cargar categorías YNAB para el parser inteligente
            if self.expense_parser.load_ynab_categories(budget_id):
                logger.info(f"Categorías YNAB cargadas para usuario {user_id}")
            else:
                logger.warning(f"No se pudieron cargar categorías YNAB para usuario {user_id}")
            
            # Obtener cuentas del presupuesto
            accounts = self.ynab_client.get_accounts(budget_id)
            if not accounts:
                await query.edit_message_text("❌ No se pudieron obtener las cuentas.")
                return
            
            # Crear botones para seleccionar cuenta
            keyboard = []
            for account in accounts:
                if not account.get('deleted', False) and not account.get('closed', False):
                    keyboard.append([InlineKeyboardButton(
                        f"💳 {account['name']}", 
                        callback_data=f"account_{account['id']}"
                    )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "✅ Presupuesto seleccionado.\n\nAhora selecciona tu cuenta predeterminada:",
                reply_markup=reply_markup
            )
        
        elif data.startswith('account_'):
            account_id = data.replace('account_', '')
            
            # Guardar cuenta seleccionada
            self.user_data[user_id]['default_account_id'] = account_id
            
            await query.edit_message_text(
                "✅ ¡Configuración completada!\n\n"
                "Ya puedes enviarme mensajes de gastos y los registraré automáticamente en YNAB.\n\n"
                "Ejemplo: 'Gasté $50 en comida en Walmart'"
            )
    
    async def handle_expense_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa mensajes de gastos"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Verificar configuración del usuario
        user_config = self.user_data.get(user_id, {})
        budget_id = user_config.get('budget_id') or self.default_budget_id
        account_id = user_config.get('default_account_id')
        
        if not budget_id:
            await update.message.reply_text(
                "❌ Primero configura tu presupuesto con /config"
            )
            return
        
        if not account_id:
            await update.message.reply_text(
                "❌ Primero configura tu cuenta predeterminada con /config"
            )
            return
        
        # Parsear el mensaje
        expense_data = self.expense_parser.parse_expense(message_text)
        
        if not expense_data:
            await update.message.reply_text(
                "❌ No pude entender el formato del gasto.\n\n"
                "Usa /help para ver ejemplos de formatos válidos."
            )
            return
        
        # Buscar categoría en YNAB
        category_id = self.ynab_client.find_category_by_name(budget_id, expense_data['category'])
        
        if not category_id:
            await update.message.reply_text(
                f"❌ No encontré la categoría '{expense_data['category']}' en tu presupuesto.\n\n"
        )
        
    elif data.startswith('account_'):
        account_id = data.replace('account_', '')
            
        # Guardar cuenta seleccionada
        self.user_data[user_id]['default_account_id'] = account_id
            
        await query.edit_message_text(
            "✅ ¡Configuración completada!\n\n"
            "Ya puedes enviarme mensajes de gastos y los registraré automáticamente en YNAB.\n\n"
            "Ejemplo: 'Gasté $50 en comida en Walmart'"
        )
    
async def handle_expense_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa mensajes de gastos"""
    user_id = update.effective_user.id
    message_text = update.message.text
        
    # Verificar configuración del usuario
    user_config = self.user_data.get(user_id, {})
    budget_id = user_config.get('budget_id') or self.default_budget_id
    account_id = user_config.get('default_account_id')
        # Registrar handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("config", self.config_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_expense_message))
        
        logger.info("🤖 Bot iniciado. Presiona Ctrl+C para detener.")
        application.run_polling()


if __name__ == "__main__":
    try:
        bot = YNABTelegramBot()
        bot.run()
    except Exception as e:
        logger.error(f"Error iniciando el bot: {e}")
        print("❌ Error: Verifica que hayas configurado correctamente el archivo .env")

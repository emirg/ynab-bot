import os
import sys
import logging
import tempfile
from datetime import datetime
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# Importaciones absolutas para la nueva estructura
from integrations.ynab_client import YNABClient
from parsers.smart_expense_parser import SmartExpenseParser
from integrations.speech_to_text import SpeechToTextProcessor

# Cargar variables de entorno desde config/
config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
load_dotenv(config_path)

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
        
        # Inicializar procesador de speech-to-text
        try:
            self.speech_processor = SpeechToTextProcessor()
            logger.info("🎤 Speech-to-Text processor inicializado")
        except Exception as e:
            logger.error(f"⚠️ No se pudo inicializar Speech-to-Text: {e}")
            self.speech_processor = None
        
        # Cache para datos del usuario
        self.user_data = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start - Mensaje de bienvenida"""
        welcome_message = """
🤖 ¡Hola! Soy tu bot inteligente de YNAB para registrar gastos.

🧠 **Características avanzadas:**
• 🔍 Parseo inteligente con IA (OpenAI GPT)
• 🧩 Aprendizaje adaptativo por lugar
• 📊 Categorías reales de tu presupuesto YNAB
• 💬 Entiende lenguaje natural y jerga colombiana

🔹 **Comandos disponibles:**
/start - Mostrar este mensaje
/help - Ayuda y ejemplos
/config - Configurar cuentas y categorías
/status - Ver configuración actual
/stats - Estadísticas de aprendizaje

🔹 **Para registrar un gasto, envía un mensaje como:**
• "Gasté $40000 en comida en Éxito"
• "$25000 transporte Uber"
• "30 lucas almuerzo McDonald's"
• "Compré ropa por 80k en Falabella"

¡Empecemos! Usa /config para configurar tus cuentas.
        """
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help - Ayuda y ejemplos"""
        help_text = """
📝 **Ejemplos de mensajes válidos:**

1. "Gasté $40000 en comida en Éxito"
2. "$25000 transporte Uber"
3. "30000,56 pesos entretenimiento Netflix"
4. "Compré ropa por $80000 en Falabella"
5. "25 lucas almuerzo McDonald's"
6. "80k gasolina estación Terpel"
7. "150 mil supermercado Carulla"

💡 **Consejos:**
• Incluye la cantidad, lugar y opcionalmente categoría
• Usa formato colombiano: $40000 o 40000,56 (coma para decimales)
• Puedes usar jerga: '25 lucas', '80k', '150 mil'
• El bot entiende lenguaje natural completo
• 🧠 **Aprende automáticamente**: Si siempre compras en "Éxito" → "Groceries", recordará esta asociación
• Reconoce tus categorías YNAB reales automáticamente
• Usa /config para configurar tus cuentas predeterminadas
• Usa /stats para ver qué ha aprendido el bot
        """
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
        
        # Estadísticas de aprendizaje
        if hasattr(self.expense_parser, 'get_learning_stats'):
            stats = self.expense_parser.get_learning_stats()
            if stats:
                status_text += f"\n🧠 **Aprendizaje adaptativo:**\n"
                status_text += f"• Lugares aprendidos: {stats.get('total_payees_learned', 0)}\n"
                status_text += f"• Transacciones procesadas: {stats.get('total_transactions', 0)}\n"
                status_text += f"• Precisión alta: {stats.get('high_confidence_payees', 0)} lugares\n"
        
        status_text += f"\nUsa /config para configurar o /stats para más detalles."
        
        await update.message.reply_text(status_text)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats - Estadísticas detalladas de aprendizaje"""
        if not hasattr(self.expense_parser, 'get_learning_stats'):
            await update.message.reply_text("❌ Sistema de aprendizaje no disponible.")
            return
        
        stats = self.expense_parser.get_learning_stats()
        if not stats:
            await update.message.reply_text("📊 Aún no hay estadísticas de aprendizaje.\n\nRegistra algunos gastos para que el bot comience a aprender.")
            return
        
        stats_text = "🧠 **Estadísticas de Aprendizaje Adaptativo:**\n\n"
        stats_text += f"📈 **Resumen general:**\n"
        stats_text += f"• Total transacciones: {stats.get('total_transactions', 0)}\n"
        stats_text += f"• Lugares aprendidos: {stats.get('total_payees_learned', 0)}\n"
        stats_text += f"• Asociaciones de alta confianza: {stats.get('high_confidence_payees', 0)}\n"
        stats_text += f"• Tasa de precisión: {stats.get('confidence_rate', 0):.1%}\n"
        stats_text += f"• Correcciones del usuario: {stats.get('total_corrections', 0)}\n"
        stats_text += f"• Mejoras de precisión: {stats.get('accuracy_improvements', 0)}\n\n"
        
        stats_text += "💡 **¿Cómo funciona?**\n"
        stats_text += "El bot aprende automáticamente de cada gasto que registras. "
        stats_text += "Si siempre compras en 'Éxito' y lo categorizas como 'Groceries', "
        stats_text += "la próxima vez que menciones 'Éxito' automáticamente sugerirá 'Groceries'.\n\n"
        stats_text += "¡Entre más uses el bot, más inteligente se vuelve! 🚀"
        
        await update.message.reply_text(stats_text)
    
    async def correct_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando para corregir categorías de transacciones recientes"""
        try:
            # Obtener transacciones recientes
            recent_transactions = self.expense_parser.adaptive_learner.get_recent_transactions(5)
            
            if not recent_transactions:
                await update.message.reply_text(
                    "📝 No hay transacciones recientes para corregir.\n\n"
                    "Registra algunos gastos primero y luego podrás corregir las categorías si es necesario."
                )
                return
            
            # Crear botones para cada transacción
            keyboard = []
            message = "🔧 **Transacciones Recientes para Corregir:**\n\n"
            
            for i, transaction in enumerate(recent_transactions, 1):
                payee = transaction['payee'].title()
                category = transaction['category_name']
                amount = transaction['amount']
                timestamp = transaction['timestamp'][:16].replace('T', ' ')
                corrected = "✅" if transaction.get('corrected', False) else "❌"
                
                message += f"{i}. **{payee}** - ${amount:,.0f}\n"
                message += f"   📂 {category} {corrected}\n"
                message += f"   🕐 {timestamp}\n\n"
                
                # Solo agregar botón si no está corregida
                if not transaction.get('corrected', False):
                    keyboard.append([
                        InlineKeyboardButton(
                            f"🔧 Corregir #{i}: {payee}",
                            callback_data=f"correct_{transaction['id']}"
                        )
                    ])
            
            if not keyboard:
                message += "✅ Todas las transacciones recientes ya han sido corregidas."
                reply_markup = None
            else:
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message, 
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error en comando corregir: {e}")
            await update.message.reply_text(
                "❌ Error obteniendo transacciones. Intenta de nuevo."
            )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los callbacks de los botones interactivos"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data.startswith("correct_"):
                # Extraer ID de transacción
                transaction_id = query.data.replace("correct_", "")
                
                # Obtener transacción
                transactions = self.expense_parser.adaptive_learner.get_recent_transactions(10)
                transaction = None
                for t in transactions:
                    if t["id"] == transaction_id:
                        transaction = t
                        break
                
                if not transaction:
                    await query.edit_message_text(
                        "❌ Transacción no encontrada. Usa /corregir para ver transacciones actuales."
                    )
                    return
                
                # Obtener categorías YNAB disponibles
                categories = self.expense_parser.category_manager.get_categories_list()
                
                if not categories:
                    await query.edit_message_text(
                        "❌ Error obteniendo categorías de YNAB. Intenta de nuevo."
                    )
                    return
                
                # Crear botones de categorías (máximo 20 para no sobrecargar)
                keyboard = []
                payee = transaction['payee'].title()
                amount = transaction['amount']
                old_category = transaction['category_name']
                
                message = f"🔧 **Corrigiendo: {payee}** (${amount:,.0f})\n"
                message += f"📂 Categoría actual: {old_category}\n\n"
                message += "🎯 **Selecciona la categoría correcta:**"
                
                # Agrupar categorías por grupo para mejor organización
                category_groups = {}
                for category in categories:
                    cat_id = category['id']
                    cat_name = category['name']
                    group = category.get('group', 'Otros')
                    if group not in category_groups:
                        category_groups[group] = []
                    category_groups[group].append((cat_id, cat_name))
                
                # Crear botones de todas las categorías disponibles
                button_count = 0
                
                # Crear mapeo temporal para IDs cortos (para evitar límite de callback_data)
                if not hasattr(self, 'temp_category_mapping'):
                    self.temp_category_mapping = {}
                
                # Mostrar todas las categorías de todos los grupos
                for group_name, group_categories in category_groups.items():
                    for cat_id, cat_name in group_categories:
                        
                        # Crear ID corto para el callback
                        short_id = f"cat_{button_count}"
                        self.temp_category_mapping[short_id] = cat_id
                        
                        # Mostrar grupo y categoría para mayor claridad
                        display_name = f"{group_name}: {cat_name}"
                        if len(display_name) > 35:
                            display_name = f"{cat_name[:30]}..."
                        
                        keyboard.append([
                            InlineKeyboardButton(
                                display_name,
                                callback_data=f"set_cat_{transaction_id[-8:]}_{short_id}"
                            )
                        ])
                        button_count += 1
                
                # Botón de cancelar
                keyboard.append([
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel_correction")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
            elif query.data.startswith("set_cat_"):
                # Procesar corrección de categoría
                logger.info(f"Procesando corrección con callback_data: {query.data}")
                callback_content = query.data.replace("set_cat_", "")
                
                # Buscar la última ocurrencia de "cat_" para separar correctamente
                last_cat_index = callback_content.rfind("cat_")
                if last_cat_index == -1:
                    logger.error(f"Formato de callback_data inválido: {query.data}")
                    await query.edit_message_text("❌ Error en el formato de corrección.")
                    return
                
                # Separar transaction_id_short y short_category_id correctamente
                transaction_id_short = callback_content[:last_cat_index-1]  # -1 para quitar el _ antes de cat_
                short_category_id = callback_content[last_cat_index:]  # desde cat_ en adelante
                
                logger.info(f"ID transacción corto: {transaction_id_short}, ID categoría corto: {short_category_id}")
                
                # Obtener el ID real de categoría del mapeo temporal
                if not hasattr(self, 'temp_category_mapping'):
                    logger.error("temp_category_mapping no existe")
                    await query.edit_message_text("❌ Error: Mapeo de categorías no encontrado.")
                    return
                
                if short_category_id not in self.temp_category_mapping:
                    logger.error(f"short_category_id '{short_category_id}' no encontrado en mapeo. Mapeo disponible: {list(self.temp_category_mapping.keys())}")
                    await query.edit_message_text("❌ Error: Categoría no encontrada.")
                    return
                
                new_category_id = self.temp_category_mapping[short_category_id]
                
                # Buscar la transacción por el ID corto (buscar por los últimos 8 caracteres)
                recent_transactions = self.expense_parser.adaptive_learner.get_recent_transactions()
                transaction_id = None
                for trans in recent_transactions:
                    if trans['id'][-8:] == transaction_id_short:
                        transaction_id = trans['id']
                        break
                
                if not transaction_id:
                    await query.edit_message_text("❌ Error: Transacción no encontrada.")
                    return
                
                # Obtener información de la nueva categoría
                category_info = self.expense_parser.category_manager.get_category_by_id(new_category_id)
                if not category_info:
                    await query.edit_message_text("❌ Categoría no válida.")
                    return
                
                new_category_name = category_info['name']
                
                # Aplicar corrección
                success = self.expense_parser.adaptive_learner.correct_category(
                    transaction_id, new_category_id, new_category_name
                )
                
                if success:
                    await query.edit_message_text(
                        f"✅ **Corrección aplicada exitosamente!**\n\n"
                        f"🔄 Categoría actualizada a: **{new_category_name}**\n\n"
                        f"🧠 El bot aprenderá de esta corrección para futuras transacciones similares.",
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        "❌ Error aplicando la corrección. Intenta de nuevo."
                    )
                    
            elif query.data == "cancel_correction":
                await query.edit_message_text(
                    "❌ Corrección cancelada.\n\nUsa /corregir cuando quieras corregir alguna transacción."
                )
            else:
                # Mantener funcionalidad existente para otros callbacks
                user_id = update.effective_user.id
                data = query.data
                
                if data.startswith('budget_'):
                    budget_id = data.replace('budget_', '')
                    
                    # Guardar presupuesto seleccionado
                    if user_id not in self.user_data:
                        self.user_data[user_id] = {}
                    self.user_data[user_id]['budget_id'] = budget_id
                    
                    # Cargar categorías YNAB para este presupuesto
                    if hasattr(self.expense_parser, 'category_manager'):
                        success = self.expense_parser.category_manager.load_categories(budget_id)
                        if success:
                            logger.info(f"Categorías YNAB cargadas para usuario {user_id}")
                    
                    # Obtener cuentas del presupuesto
                    accounts = self.ynab_client.get_accounts(budget_id)
                    if not accounts:
                        await query.edit_message_text("❌ No se pudieron obtener las cuentas del presupuesto.")
                        return
                    
                    # Crear botones para seleccionar cuenta
                    keyboard = []
                    for account in accounts:
                        if not account.get('closed', False):  # Solo cuentas activas
                            keyboard.append([InlineKeyboardButton(
                                f"🏦 {account['name']}", 
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
                    if user_id not in self.user_data:
                        self.user_data[user_id] = {}
                    self.user_data[user_id]['default_account_id'] = account_id
                    
                    await query.edit_message_text(
                        "✅ ¡Configuración completada!\n\n"
                        "🧠 El bot ahora conoce tus categorías YNAB reales y comenzará a aprender de tus gastos.\n\n"
                        "**Ejemplo:** 'Gasté $50000 en comida en Éxito'\n\n"
                        "¡Cada gasto que registres hará al bot más inteligente! 🚀"
                    )
                else:
                    # Funcionalidad básica para otros callbacks
                    await query.edit_message_text(
                        "⚙️ Funcionalidad en desarrollo."
                    )
                    
        except Exception as e:
            logger.error(f"Error en callback query: {e}")
            await query.edit_message_text(
                "❌ Error procesando la acción. Intenta de nuevo."
            )
    
    async def handle_expense_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes de gastos del usuario"""
        message_text = update.message.text
        await self._process_expense_text(update, context, message_text)
    
    async def handle_audio_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes de audio convirtiéndolos a texto y procesándolos como gastos"""
        if not self.speech_processor:
            await update.message.reply_text(
                "❌ El procesamiento de audio no está disponible. "
                "Envía tu gasto como mensaje de texto."
            )
            return
        
        user_id = update.effective_user.id
        
        # Mostrar mensaje de procesamiento
        processing_msg = await update.message.reply_text(
            "🎤 Procesando audio... Por favor espera."
        )
        
        try:
            # Obtener el archivo de audio
            if update.message.voice:
                audio_file = update.message.voice
                file_extension = "ogg"
                duration = audio_file.duration
            elif update.message.audio:
                audio_file = update.message.audio
                file_extension = "mp3"
                duration = getattr(audio_file, 'duration', 0)
            else:
                await processing_msg.edit_text(
                    "❌ Tipo de audio no soportado. Usa mensajes de voz."
                )
                return
            
            # Verificar duración del audio (máximo 60 segundos)
            if duration and duration > 60:
                await processing_msg.edit_text(
                    f"⏱️ Audio demasiado largo ({duration}s).\n\n"
                    f"💡 Por favor envía un audio de máximo 60 segundos "
                    f"o escribe tu gasto como mensaje de texto."
                )
                return
            
            # Descargar el archivo de audio
            file = await context.bot.get_file(audio_file.file_id)
            
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=False) as temp_file:
                temp_file_path = temp_file.name
                await file.download_to_drive(temp_file_path)
            
            # Transcribir el audio a texto
            transcribed_text = self.speech_processor.process_telegram_audio(temp_file_path)
            
            # Limpiar archivo temporal
            os.unlink(temp_file_path)
            
            # Manejar errores específicos
            if transcribed_text == "timeout_error":
                await processing_msg.edit_text(
                    "⏱️ El audio tardó demasiado en procesarse.\n\n"
                    "💡 Intenta con un audio más corto (máximo 30 segundos) "
                    "o envía tu gasto como mensaje de texto."
                )
                return
            elif transcribed_text == "rate_limit_error":
                await processing_msg.edit_text(
                    "🚫 Límite de procesamiento de audio alcanzado.\n\n"
                    "⏳ Espera un momento e intenta de nuevo, "
                    "o envía tu gasto como mensaje de texto."
                )
                return
            elif not transcribed_text:
                await processing_msg.edit_text(
                    "❌ No pude entender el audio.\n\n"
                    "💡 Intenta hablar más claro, más cerca del micrófono, "
                    "o envía un mensaje de texto."
                )
                return
            
            # Actualizar mensaje con la transcripción
            await processing_msg.edit_text(
                f"🎤 Audio transcrito: \"{transcribed_text}\"\n\n"
                f"📝 Procesando gasto..."
            )
            
            # Procesar el texto transcrito como un gasto normal
            await self._process_expense_text(update, context, transcribed_text, processing_msg)
            
        except Exception as e:
            logger.error(f"Error procesando audio: {e}")
            await processing_msg.edit_text(
                f"❌ Error procesando el audio: {str(e)}\n\n"
                f"Intenta enviar tu gasto como mensaje de texto."
            )
    
    async def _process_expense_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   message_text: str, reply_message=None):
        """Función auxiliar para procesar texto de gasto (usado por mensajes de texto y audio)"""
        user_id = update.effective_user.id
        
        # Verificar configuración del usuario
        user_config = self.user_data.get(user_id, {})
        budget_id = user_config.get('budget_id') or self.default_budget_id
        account_id = user_config.get('default_account_id')
        
        if not budget_id:
            error_msg = "❌ Primero configura tu presupuesto con /config"
            if reply_message:
                await reply_message.edit_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        if not account_id:
            error_msg = "❌ Primero configura tu cuenta predeterminada con /config"
            if reply_message:
                await reply_message.edit_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        # Parsear el mensaje con IA y aprendizaje adaptativo
        result = self.expense_parser.parse_expense(message_text)
        
        if not result:
            error_msg = (
                "❌ No pude entender el formato del gasto.\n\n"
                "Usa /help para ver ejemplos de formatos válidos."
            )
            if reply_message:
                await reply_message.edit_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        # Usar cuenta detectada por LLM si está disponible, sino usar cuenta predeterminada
        final_account_id = result.get('account_id', account_id)
        
        # Crear transacción en YNAB
        success = self.ynab_client.create_transaction(
            budget_id=budget_id,
            account_id=final_account_id,
            category_id=result.get('category_id'),
            payee_name=result['payee'],
            amount=result['amount'],
            memo=result.get('memo', '')
        )
        
        if success:
            # Registrar transacción para posible corrección
            if hasattr(self.expense_parser, 'adaptive_learner'):
                self.expense_parser.adaptive_learner.track_transaction(
                    payee=result['payee'],
                    category_id=result.get('category_id', ''),
                    category_name=result.get('category', 'Sin categoría'),
                    amount=result['amount'],
                    memo=result.get('memo', ''),
                    transaction_id=f"ynab_{result['payee']}_{int(result['amount'])}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                logger.info(f"📝 Transacción registrada para corrección: {result['payee']}")
            
            # Aprender de la transacción exitosa
            if hasattr(self.expense_parser, 'learn_from_transaction'):
                confidence = result.get('confidence', 0.8)
                self.expense_parser.learn_from_transaction(
                    payee=result['payee'],
                    category_id=result.get('category_id', ''),
                    category_name=result.get('category', ''),
                    confidence=confidence
                )
            
            # Formatear respuesta de confirmación
            amount_formatted = f"${result['amount']:,.0f}".replace(',', '.')
            
            # Información del parser usado
            parser_info = "🤖 IA"
            
            # Información de predicción adaptativa
            prediction_source = result.get('prediction_source', '')
            if prediction_source == 'adaptive_learning':
                parser_info += " + 🧠 Aprendido"
            elif prediction_source == 'ynab_search':
                parser_info += " + 📊 YNAB"
            
            confidence_info = f" (confianza: {result.get('confidence', 0):.0%})"
            
            # Información de cuenta
            account_info = ""
            if result.get('account_id') != account_id:
                detected_account = result.get('account_name', 'Cuenta detectada')
                account_confidence = result.get('account_confidence', 0)
                account_info = f"🏦 Cuenta: {detected_account} (detectada automáticamente, confianza: {account_confidence:.0%})\n"
            
            response = (
                f"✅ *Gasto registrado exitosamente*\n\n"
                f"💰 Monto: {amount_formatted}\n"
                f"🏪 Lugar: {result['payee']}\n"
                f"📂 Categoría: {result.get('category', 'Sin categoría')}\n"
                f"{account_info}"
                f"📝 Nota: {result.get('memo', 'Sin nota')}\n\n"
                f"🔍 Parser: {parser_info}{confidence_info}\n"
                f"💡 El bot recordó que '{result['payee']}' suele ser '{result.get('category', 'Sin categoría')}'"
            )
            
            if reply_message:
                await reply_message.edit_text(response, parse_mode='Markdown')
            else:
                await update.message.reply_text(response, parse_mode='Markdown')
        else:
            error_msg = "❌ No se pudo registrar el gasto en YNAB. Inténtalo de nuevo."
            if reply_message:
                await reply_message.edit_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
    
    def run(self):
        """Inicia el bot"""
        application = Application.builder().token(self.telegram_token).build()
        
        # Registrar handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("config", self.config_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(CommandHandler("corregir", self.correct_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_expense_message))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_audio_message))
        application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_expense_message))
        
        # Handler para mensajes de audio
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_audio_message))
        
        logger.info("🤖 Bot inteligente iniciado con aprendizaje adaptativo. Presiona Ctrl+C para detener.")
        application.run_polling()


if __name__ == "__main__":
    try:
        bot = YNABTelegramBot()
        bot.run()
    except Exception as e:
        logger.error(f"Error iniciando el bot: {e}")
        print("❌ Error: Verifica que hayas configurado correctamente el archivo .env")

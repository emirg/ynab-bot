"""Response formatters for Telegram messages"""

from typing import List
from decimal import Decimal

from domain.models.expense import ExpenseResult
from domain.models.user import YNABBudget, YNABAccount


class ExpenseResponseFormatter:
    """Formatter for expense-related responses"""
    
    @staticmethod
    def format_success(result: ExpenseResult) -> str:
        """Format successful expense processing"""
        if not result.success or not result.expense:
            return "❌ Error procesando respuesta"
        
        expense = result.expense
        confidence_emoji = "🔥" if expense.confidence > 0.8 else "✅" if expense.confidence > 0.5 else "⚠️"
        
        message = f"""
✅ *Gasto registrado exitosamente*

💰 *Monto:* ${expense.amount:,.0f}
🏪 *Lugar:* {expense.payee}
📁 *Categoría:* {expense.category_name or 'Sin categoría'}
💳 *Cuenta:* {expense.account_name or 'Cuenta por defecto'}
{confidence_emoji} *Confianza:* {expense.confidence*100:.0f}%
🤖 *Procesado por:* {expense.parser_source.upper()}

📝 *Memo:* {expense.memo}
        """
        
        return message.strip()
    
    @staticmethod
    def format_error(result: ExpenseResult) -> str:
        """Format error response"""
        if result.success:
            return "✅ Procesado exitosamente"
        
        error_message = result.error_message or "Error desconocido"
        
        # Customize error messages
        if "not configured" in error_message.lower():
            return """
❌ *Usuario no configurado*

Para usar el bot, primero configura tu presupuesto:
• Usa `/config` para ver opciones de configuración
• Selecciona tu presupuesto YNAB
• Configura tu cuenta por defecto

💡 *Tip:* Usa `/help` para ver ejemplos de uso
            """.strip()
        
        elif "parse" in error_message.lower():
            return """
❌ *No pude entender el formato del gasto*

📝 *Ejemplos válidos:*
• "Gasté $40000 en comida en Éxito"
• "$25000 transporte Uber"
• "30 lucas almuerzo McDonald's"
• "Compré ropa por 80k en Falabella"

💡 *Tip:* Incluye monto, lugar y opcionalmente categoría
            """.strip()
        
        elif "ynab" in error_message.lower():
            return f"""
❌ *Error conectando con YNAB*

{error_message}

💡 *Sugerencias:*
• Verifica tu conexión a internet
• Revisa que tu token YNAB sea válido
• Intenta de nuevo en unos segundos
            """.strip()
        
        return f"❌ *Error:* {error_message}"


class ConfigResponseFormatter:
    """Formatter for configuration-related responses"""
    
    @staticmethod
    def format_budgets_list(budgets: List[YNABBudget]) -> str:
        """Format list of available budgets"""
        if not budgets:
            return "❌ No se encontraron presupuestos en tu cuenta YNAB"
        
        message = "💰 *Presupuestos disponibles:*\n\n"
        
        for i, budget in enumerate(budgets, 1):
            message += f"{i}. *{budget.name}*\n"
            message += f"   ID: `{budget.id}`\n\n"
        
        message += "💡 Para seleccionar un presupuesto, usa: `/budget <número>`"
        
        return message
    
    @staticmethod
    def format_accounts_list(accounts: List[YNABAccount]) -> str:
        """Format list of available accounts"""
        if not accounts:
            return "❌ No se encontraron cuentas en tu presupuesto"
        
        message = "💳 *Cuentas disponibles:*\n\n"
        
        for i, account in enumerate(accounts, 1):
            balance = account.balance / 1000  # Convert from milliunits
            balance_emoji = "💰" if balance > 0 else "💸" if balance < 0 else "➖"
            
            message += f"{i}. *{account.name}* {balance_emoji}\n"
            message += f"   Tipo: {account.type}\n"
            message += f"   Saldo: ${balance:,.0f}\n"
            message += f"   ID: `{account.id}`\n\n"
        
        message += "💡 Para seleccionar cuenta por defecto, usa: `/account <número>`"
        
        return message
    
    @staticmethod
    def format_user_status(status: dict) -> str:
        """Format user configuration status"""
        configured_emoji = "✅" if status.get("configured") else "⚠️"
        
        message = f"{configured_emoji} *Estado de configuración*\n\n"
        
        # Budget info
        if status.get("budget_id"):
            budget_name = status.get("budget_name", "Desconocido")
            message += f"💰 *Presupuesto:* {budget_name}\n"
        else:
            message += "💰 *Presupuesto:* ❌ No configurado\n"
        
        # Account info
        if status.get("default_account_id"):
            account_name = status.get("default_account_name", "Desconocido")
            message += f"💳 *Cuenta por defecto:* {account_name}\n"
        else:
            message += "💳 *Cuenta por defecto:* ❌ No configurada\n"
        
        message += f"\n📊 *Estado:* {status.get('message', 'Desconocido')}\n"
        
        if status.get("created_at"):
            message += f"📅 *Creado:* {status['created_at'][:10]}\n"
        
        if not status.get("configured"):
            message += "\n💡 *Próximos pasos:*\n"
            if not status.get("budget_id"):
                message += "• Usa `/budgets` para ver presupuestos disponibles\n"
            if not status.get("default_account_id"):
                message += "• Usa `/accounts` para ver cuentas disponibles\n"
        
        return message.strip()


class LearningResponseFormatter:
    """Formatter for learning system responses"""
    
    @staticmethod
    def format_stats_response(stats_message: str) -> str:
        """Format learning statistics response"""
        return stats_message
    
    @staticmethod
    def format_recent_transactions_response(recent_message: str) -> str:
        """Format recent transactions response"""
        return recent_message
    
    @staticmethod
    def format_correction_success(payee: str, old_category: str, new_category: str) -> str:
        """Format successful correction response"""
        return f"""
✅ *Corrección registrada*

🏪 *Comercio:* {payee}
📁 *Categoría anterior:* {old_category}
📁 *Nueva categoría:* {new_category}

🧠 *El sistema ha aprendido de esta corrección*
        """.strip()
    
    @staticmethod
    def format_correction_error(error_message: str) -> str:
        """Format correction error response"""
        return f"❌ *Error en corrección:* {error_message}"


class GeneralResponseFormatter:
    """Formatter for general responses"""
    
    @staticmethod
    def format_welcome_message() -> str:
        """Format welcome message"""
        return """
🤖 *¡Hola! Soy tu bot inteligente de YNAB*

🧠 *Características avanzadas:*
• 🔍 Parseo inteligente con IA (OpenAI GPT)
• 🧩 Aprendizaje adaptativo por comercio
• 📊 Categorías reales de tu presupuesto YNAB
• 💬 Entiende lenguaje natural y jerga colombiana
• 🎤 Procesamiento de mensajes de voz

🔹 *Comandos disponibles:*
/start - Mostrar este mensaje
/help - Ayuda y ejemplos
/config - Configurar cuentas y categorías
/status - Ver configuración actual
/stats - Estadísticas de aprendizaje

🔹 *Para registrar un gasto:*
Envía un mensaje como:
• "Gasté $40000 en comida en Éxito"
• "$25000 transporte Uber"
• "30 lucas almuerzo McDonald's"

¡Empecemos! Usa `/config` para configurar.
        """.strip()
    
    @staticmethod
    def format_help_message() -> str:
        """Format help message"""
        return """
📝 *Ejemplos de mensajes válidos:*

💰 *Con formato colombiano:*
• "Gasté $40000 en comida en Éxito"
• "$25000 transporte Uber"
• "30000,56 pesos entretenimiento Netflix"
• "Compré ropa por $80000 en Falabella"

🗣️ *Con jerga colombiana:*
• "25 lucas almuerzo McDonald's"
• "80k gasolina estación Terpel"
• "150 mil supermercado Carulla"

🎤 *Mensajes de voz:*
• También puedes enviar mensajes de voz
• El bot los convertirá a texto automáticamente

💡 *Consejos:*
• Incluye monto, lugar y opcionalmente categoría
• Usa formato colombiano: $40000 o 40000,56 (coma para decimales)
• El bot entiende lenguaje natural completo
• 🧠 *Aprende automáticamente* de tus patrones

🔧 *Comandos útiles:*
/config - Configurar presupuesto y cuentas
/status - Ver tu configuración actual
/stats - Ver estadísticas de aprendizaje
/corregir - Corregir transacciones recientes
        """.strip()
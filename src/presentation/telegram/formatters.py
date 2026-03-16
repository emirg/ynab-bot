"""Response formatters for Telegram messages"""

from typing import List
from decimal import Decimal

from domain.models.expense import ExpenseResult
from domain.models.budget_query import BudgetQueryResult
from domain.models.user import YNABBudget, YNABAccount
from domain.models.onboarding import OnboardingStep


class ExpenseResponseFormatter:
    """Formatter for expense-related responses"""
    
    @staticmethod
    def format_success(result: ExpenseResult) -> str:
        """Format successful expense processing"""
        if not result.success or not result.expense:
            return "❌ Error procesando respuesta"

        expense = result.expense
        confidence_emoji = "🔥" if expense.confidence > 0.8 else "✅" if expense.confidence > 0.5 else "⚠️"

        if expense.is_split:
            user_pct = int(expense.split_proportion * 100)
            split_pct = 100 - user_pct
            user_share = int(expense.amount * expense.split_proportion)
            split_share = int(expense.amount) - user_share
            message = f"""
✅ *Gasto compartido registrado*

💰 *Total:* ${expense.amount:,.0f}
🤝 *Compartido con:* {expense.split_person}
📊 *Tu parte ({user_pct}%):* ${user_share:,.0f} → {expense.category_name or 'Sin categoría'}
📊 *Splitwise ({split_pct}%):* ${split_share:,.0f} → {expense.split_category_name or 'Gastos Compartidos'}
🏪 *Lugar:* {expense.payee}
💳 *Cuenta:* {expense.account_name or 'Cuenta por defecto'}
{confidence_emoji} *Razon:* {expense.category_explanation or 'desconocido'}

📝 *Memo:* {expense.memo}
            """
        else:
            message = f"""
✅ *Gasto registrado exitosamente*

💰 *Monto:* ${expense.amount:,.0f}
🏪 *Lugar:* {expense.payee}
📁 *Categoría:* {expense.category_name or 'Sin categoría'}
💳 *Cuenta:* {expense.account_name or 'Cuenta por defecto'}
{confidence_emoji} *Razon:* {expense.category_explanation or 'desconocido'}

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


class BudgetQueryFormatter:
    """Formatter for budget query responses"""

    @staticmethod
    def format_response(result: BudgetQueryResult) -> str:
        if not result.success:
            return BudgetQueryFormatter.format_error(result)

        formatters = {
            'category_balance': BudgetQueryFormatter._format_category_balance,
            'account_balance': BudgetQueryFormatter._format_account_balance,
            'budget_summary': BudgetQueryFormatter._format_budget_summary,
        }
        formatter = formatters.get(result.query_type)
        if formatter:
            return formatter(result.data)
        return BudgetQueryFormatter.format_error(result)

    @staticmethod
    def _format_category_balance(data: dict) -> str:
        budgeted = data['budgeted'] / 1000
        activity = data['activity'] / 1000
        balance = data['balance'] / 1000
        balance_emoji = "✅" if balance > 0 else "⚠️" if balance == 0 else "🔴"

        return f"""
{balance_emoji} *{data['name']}* ({data['group_name']})

💰 *Presupuestado:* ${budgeted:,.0f}
📉 *Gastado:* ${abs(activity):,.0f}
💵 *Disponible:* ${balance:,.0f}
        """.strip()

    @staticmethod
    def _format_account_balance(data: dict) -> str:
        balance = data['balance'] / 1000
        cleared = data['cleared_balance'] / 1000
        uncleared = data['uncleared_balance'] / 1000
        balance_emoji = "💰" if balance >= 0 else "💸"

        return f"""
{balance_emoji} *{data['name']}*

💳 *Saldo:* ${balance:,.0f}
✅ *Confirmado:* ${cleared:,.0f}
⏳ *Pendiente:* ${uncleared:,.0f}
        """.strip()

    @staticmethod
    def _format_budget_summary(data: dict) -> str:
        total_budgeted = data['total_budgeted'] / 1000
        total_activity = data['total_activity'] / 1000
        total_balance = data['total_balance'] / 1000
        balance_emoji = "✅" if total_balance > 0 else "⚠️"

        message = f"""
{balance_emoji} *Resumen de presupuesto*

💰 *Total presupuestado:* ${total_budgeted:,.0f}
📉 *Total gastado:* ${abs(total_activity):,.0f}
💵 *Total disponible:* ${total_balance:,.0f}
📊 *Categorías activas:* {data['category_count']}
        """.strip()

        top = data.get('top_spending', [])
        if top:
            message += "\n\n📊 *Top gastos:*"
            for i, cat in enumerate(top, 1):
                spent = abs(cat['activity'] / 1000)
                remaining = cat['balance'] / 1000
                message += f"\n{i}. *{cat['name']}* — ${spent:,.0f} gastado, ${remaining:,.0f} disponible"

        return message

    @staticmethod
    def format_error(result: BudgetQueryResult) -> str:
        error = result.error_message or "Error desconocido en la consulta"
        return f"❌ *{error}*"


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
        
        # Split info
        split_count = status.get("split_group_count", 0)
        if split_count > 0:
            message += f"🤝 *Gastos compartidos:* {split_count} grupos configurados\n"
        
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


class SplitConfigResponseFormatter:
    """Formatter for split configuration-related responses"""

    @staticmethod
    def format_split_panel() -> str:
        """Main panel message text for split configuration"""
        return """
*Configuración de Gastos Compartidos* 🤝

Aquí puedes configurar cómo el bot maneja los gastos que divides con otras personas (Splitwise style).

1️⃣ *Grupos Splitwise:* Asocia categorías de YNAB (ej: "Gastos Compartidos") con personas (ej: "Juan").
2️⃣ *Cuenta Compartida:* Define en qué cuenta se registran estos gastos (ej: "Nu Savings").
3️⃣ *Detección Inteligente:* Cuando digas "con Juan", el bot usará automáticamente la categoría y cuenta configuradas.

Selecciona una opción abajo para empezar:
        """.strip()

    @staticmethod
    def format_split_summary(summary: dict) -> str:
        """Format the split configuration summary"""
        message = "*Configuración de Gastos Compartidos*\n\n"

        groups = summary.get("groups", [])
        if groups:
            message += "*Grupos Splitwise:*\n"
            for i, group in enumerate(groups, 1):
                aliases = ", ".join(group.person_aliases) if group.person_aliases else "Sin aliases"
                message += f"{i}. *{group.category_name}* (aliases: {aliases})\n"
        else:
            message += "*Grupos Splitwise:* ❌ Ninguno configurado\n"

        message += "\n"

        shared_account = summary.get("shared_account")
        if shared_account:
            message += f"*Cuenta compartida:* {shared_account.account_name}\n"
        else:
            message += "*Cuenta compartida:* ❌ No configurada\n"

        message += "\n*División por defecto:* 50/50"

        if not summary.get("configured"):
            message += "\n\n⚠️ *Nota:* Debes configurar al menos un grupo para activar la detección de gastos compartidos."

        return message.strip()

    @staticmethod
    def format_group_added(category_name: str) -> str:
        """Confirmation message when a group is added"""
        return f"✅ Grupo *{category_name}* agregado exitosamente."

    @staticmethod
    def format_group_removed(category_name: str) -> str:
        """Confirmation message when a group is removed"""
        return f"🗑️ Grupo *{category_name}* eliminado."

    @staticmethod
    def format_alias_added(alias: str, category_name: str) -> str:
        """Confirmation message when an alias is added"""
        return f"✅ Alias *{alias}* agregado al grupo *{category_name}*."

    @staticmethod
    def format_alias_removed(alias: str, category_name: str) -> str:
        """Confirmation message when an alias is removed"""
        return f"🗑️ Alias *{alias}* eliminado del grupo *{category_name}*."

    @staticmethod
    def format_shared_account_set(account_name: str) -> str:
        """Confirmation message when shared account is set"""
        return f"✅ Cuenta compartida configurada como: *{account_name}*."

    @staticmethod
    def format_shared_account_removed() -> str:
        """Confirmation message when shared account is removed"""
        return "🗑️ Cuenta compartida eliminada. Se usará la cuenta por defecto."

    @staticmethod
    def format_no_budget_configured() -> str:
        """Error message when no budget is configured"""
        return """
❌ *Presupuesto no configurado*

Para configurar gastos compartidos, primero debes seleccionar un presupuesto de YNAB.

Usa `/config` o `/budgets` para empezar.
        """.strip()

    @staticmethod
    def format_ask_alias(category_name: str = "") -> str:
        """Message asking for an alias"""
        group_info = f" para el grupo *{category_name}*" if category_name else ""
        return f"👤 Por favor, escribe el nombre de la persona (alias){group_info}:"


class GeneralResponseFormatter:
    """Formatter for general responses"""
    
    @staticmethod
    def format_welcome_message() -> str:
        """Format welcome message"""
        return """
🤖 *¡Hola! Soy tu bot inteligente de YNAB*

🧠 *Características avanzadas:*
• 🔍 Parseo inteligente con IA (OpenAI GPT)
• 📸 Análisis de fotos de recibos/tickets
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
• 📸 O simplemente envía una foto de un recibo

¡Empecemos! Usa `/config` para configurar.
        """.strip()
    
    @staticmethod
    def format_help_message() -> str:
        """Format help message"""
        return f"""
📖 *Guía de uso de YNAB Bot*

{GeneralResponseFormatter.format_command_list()}

💡 *Tip:* Si el bot se equivoca de categoría, usa `/corregir`. ¡Así aprenderá para la próxima vez!
        """.strip()

    @staticmethod
    def format_command_list() -> str:
        """Returns the base list of available commands"""
        return """
🔧 *Configuración*
• `/connect` - Conectar cuenta YNAB
• `/config` - Panel de configuración
• `/status` - Ver estado actual
• `/budgets` - Ver presupuestos
• `/accounts` - Ver cuentas
• `/disconnect` - Cerrar sesión

💰 *Registro de Gastos*
• Texto, fotos de recibos o mensajes de voz

🤝 *Gastos Compartidos*
• `/splitwise` - Configurar grupos y cuenta

📊 *Consultas*
• Saldo de cuentas o categorías en lenguaje natural

🧠 *Aprendizaje*
• `/aprendizaje` - Panel de aprendizaje
• `/olvidar` - Borrar asociaciones
• `/corregir` - Corregir categorías
• `/recent` - Últimos gastos
• `/stats` - Estadísticas
        """.strip()

    @staticmethod
    def format_onboarding_welcome(user_name: str, step: OnboardingStep) -> str:
        """Format the appropriate welcome message based on onboarding step"""
        if step == OnboardingStep.NEEDS_YNAB_CONNECTION:
            return f"""
👋 *¡Hola {user_name}!* 

Soy tu bot inteligente de YNAB. Para empezar, necesito conectarme con tu cuenta de YNAB de forma segura.

Presiona el botón de abajo o usa `/connect` para autorizar el acceso.
            """.strip()

        elif step == OnboardingStep.NEEDS_BUDGET:
            return "✅ *¡YNAB conectado!* Ahora, selecciona el presupuesto que quieres usar:"

        elif step == OnboardingStep.NEEDS_ACCOUNT:
            return "📝 *Presupuesto seleccionado.* Ahora elige la cuenta por defecto donde se registrarán tus gastos:"

        elif step == OnboardingStep.COMPLETE:
            return f"""
✅ *¡Todo listo, {user_name}!* 

Ya configuramos tu presupuesto y cuenta por defecto. Ya puedes empezar a registrar gastos.

💰 *Prueba enviando algo como:*
• "almuerzo 25000"
• "45000 gasolina"
• "supermercado 120000"

¡Disfruta de tu control financiero! 🚀
            """.strip()

        return "👋 ¡Hola! Usa `/help` para ver cómo empezar."

    @staticmethod
    def format_post_oauth_message() -> str:
        """Message sent after OAuth success"""
        return "🎉 *¡Cuenta YNAB conectada exitosamente!* \n\nAhora vamos a configurar tu presupuesto. Selecciona uno de la lista:"

    @staticmethod
    def format_onboarding_complete() -> str:
        """Final congratulations message with usage example"""
        return """
✨ *¡Configuración completada con éxito!*

Ya puedes empezar a registrar gastos enviando mensajes de texto, voz o fotos de recibos.

💰 *Ejemplo:* "comida 35000"
        """.strip()
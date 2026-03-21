import logging
import re
from decimal import Decimal, InvalidOperation
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import LearningResponseFormatter
from presentation.telegram.middleware.auth_middleware import require_authentication
from application.services.learning_service import LearningService
from application.services.expense_service import ExpenseService

logger = logging.getLogger(__name__)

_KEYWORDS = {"monto", "comercio", "categoria", "cuenta"}


def _parse_amount(token: str) -> Decimal:
    """Parse an amount string supporting plain numbers, mil/lucas/k suffix, and comma decimals.

    Examples:
        "40000" -> Decimal("40000")
        "40mil" -> Decimal("40000")
        "40k"   -> Decimal("40000")
        "40lucas" -> Decimal("40000")
        "1,5"   -> Decimal("1.5")
        "1.5"   -> Decimal("1.5")

    Raises:
        ValueError: if the token cannot be parsed.
    """
    token = token.strip()
    # Detect suffix: mil, lucas, or k (case-insensitive)
    multiplier = 1
    suffix_match = re.match(r"^([\d.,]+)(mil|lucas|k)$", token, re.IGNORECASE)
    if suffix_match:
        number_part = suffix_match.group(1)
        multiplier = 1000
    else:
        number_part = token

    # Replace comma decimal separator with dot
    number_part = number_part.replace(",", ".")

    try:
        return Decimal(number_part) * multiplier
    except InvalidOperation:
        raise ValueError(f"Monto invalido: '{token}'")


class LearningHandler(BaseHandler):
    """Handler for learning system commands"""

    def __init__(self, container):
        super().__init__(container)
        self.learning_service = container.get(LearningService)
        self.expense_service = container.get(ExpenseService)
        self.formatter = LearningResponseFormatter()

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - show learning statistics"""
        self.log_handler_start("LearningHandler.handle_stats_command", update)

        try:
            user_id = self.get_user_id(update)
            stats_message = self.learning_service.format_statistics_message(user_id)
            await self.send_message(update, stats_message)
            self.log_handler_success("LearningHandler.handle_stats_command", update)

        except Exception as e:
            self.log_handler_error("LearningHandler.handle_stats_command", update, e)
            await self.send_error_message(update, f"Error obteniendo estadísticas: {str(e)}")

    @require_authentication(lambda self: self.container.get_auth_service())
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

            user_id = self.get_user_id(update)
            recent_message = self.learning_service.format_recent_transactions_message(user_id, limit)
            await self.send_message(update, recent_message)
            self.log_handler_success("LearningHandler.handle_recent_command", update)

        except Exception as e:
            self.log_handler_error("LearningHandler.handle_recent_command", update, e)
            await self.send_error_message(update, f"Error obteniendo transacciones recientes: {str(e)}")

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_edit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /editar command - edit a recent transaction field(s)"""
        self.log_handler_start("LearningHandler.handle_edit_command", update)

        try:
            args = list(context.args) if context.args else []

            # --- Index parsing ---
            transaction_index = 0
            if args and args[0].isdigit():
                transaction_index = int(args[0]) - 1  # Convert 1-based to 0-based
                args = args[1:]

            # --- Keyword parsing ---
            parsed: dict[str, str] = {}
            current_keyword = None
            value_tokens: list[str] = []

            def _flush():
                if current_keyword and value_tokens:
                    parsed[current_keyword] = " ".join(value_tokens)

            for token in args:
                if token.lower() in _KEYWORDS:
                    _flush()
                    current_keyword = token.lower()
                    value_tokens = []
                elif current_keyword is not None:
                    # For monto, only take the first token
                    if current_keyword == "monto" and not value_tokens:
                        value_tokens.append(token)
                    elif current_keyword != "monto":
                        value_tokens.append(token)
                # Unknown tokens before any keyword are silently ignored

            _flush()

            # No recognized keywords found — show help
            if not parsed:
                await self.send_message(update, self.formatter.format_edit_help())
                return

            # --- Amount parsing ---
            new_amount = None
            if "monto" in parsed:
                try:
                    new_amount = _parse_amount(parsed["monto"])
                except ValueError as e:
                    await self.send_error_message(update, str(e))
                    return

            new_payee = parsed.get("comercio") or None
            new_category = parsed.get("categoria") or None
            new_account = parsed.get("cuenta") or None

            user_id = self.get_user_id(update)

            result = self.expense_service.edit_last_transaction(
                user_id,
                transaction_index,
                new_amount,
                new_payee,
                new_category,
                new_account,
            )

            if result is None:
                await self.send_error_message(update, "No se pudo editar la transaccion. Intenta de nuevo.")
                return

            if "error" in result:
                error_code = result["error"]
                if error_code == "time_window_exceeded":
                    await self.send_error_message(update, self.formatter.format_time_window_error())
                elif error_code == "no_recent_transactions":
                    await self.send_error_message(update, self.formatter.format_no_recent_transaction_error())
                elif error_code == "index_out_of_range":
                    await self.send_error_message(update, "El indice de transaccion esta fuera de rango.")
                elif error_code in ("category_not_found", "account_not_found"):
                    await self.send_error_message(update, result.get("message", error_code))
                else:
                    await self.send_error_message(update, result.get("message", error_code))
                return

            response = self.formatter.format_edit_success(result["payee"], result["changes"])
            await self.send_message(update, response)
            self.log_handler_success("LearningHandler.handle_edit_command", update)

        except Exception as e:
            self.log_handler_error("LearningHandler.handle_edit_command", update, e)
            await self.send_error_message(update, f"Error editando transaccion: {str(e)}")

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_undo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /deshacer command - undo the last transaction"""
        self.log_handler_start("LearningHandler.handle_undo_command", update)

        try:
            user_id = self.get_user_id(update)
            result = self.expense_service.undo_last_transaction(user_id)

            if result is None:
                await self.send_error_message(update, "No se pudo deshacer la transaccion. Intenta de nuevo.")
                return

            if 'error' in result:
                error_code = result['error']
                if error_code == 'time_window_exceeded':
                    await self.send_error_message(update, self.formatter.format_time_window_error())
                elif error_code == 'no_recent_transactions':
                    await self.send_error_message(update, self.formatter.format_no_recent_transaction_error())
                else:
                    await self.send_error_message(update, error_code)
                return

            response = self.formatter.format_undo_success(
                result['payee'], result['amount'], result['category_name']
            )
            await self.send_message(update, response)
            self.log_handler_success("LearningHandler.handle_undo_command", update)

        except Exception as e:
            self.log_handler_error("LearningHandler.handle_undo_command", update, e)
            await self.send_error_message(update, f"Error deshaciendo transaccion: {str(e)}")

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_learning_dashboard_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /aprendizaje command - show learned payee-category associations"""
        self.log_handler_start("LearningHandler.handle_learning_dashboard_command", update)

        try:
            user_id = self.get_user_id(update)
            message = self.learning_service.format_learning_dashboard_message(user_id)
            await self.send_message(update, message)
            self.log_handler_success(
                "LearningHandler.handle_learning_dashboard_command", update
            )

        except Exception as e:
            self.log_handler_error(
                "LearningHandler.handle_learning_dashboard_command", update, e
            )
            await self.send_error_message(
                update, f"Error obteniendo panel de aprendizaje: {str(e)}"
            )

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_forget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /olvidar command - delete incorrect associations for a payee"""
        self.log_handler_start("LearningHandler.handle_forget_command", update)

        try:
            if not context.args:
                help_message = """
🗑️ *Uso del comando /olvidar:*

`/olvidar <comercio>`

*Ejemplo:*
`/olvidar McDonald's`

Borraré todo lo que he aprendido sobre ese comercio y la próxima vez te preguntaré la categoría.
                """.strip()
                await self.send_message(update, help_message)
                return

            payee = " ".join(context.args)
            user_id = self.get_user_id(update)

            success = self.learning_service.forget_payee(user_id, payee)
            message = self.learning_service.format_forget_result_message(payee, success)

            await self.send_message(update, message)
            self.log_handler_success("LearningHandler.handle_forget_command", update)

        except Exception as e:
            self.log_handler_error("LearningHandler.handle_forget_command", update, e)
            await self.send_error_message(update, f"Error olvidando comercio: {str(e)}")

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main handler entry point"""
        # Determine which command was called
        message_text = update.message.text or ""

        if message_text.startswith("/stats"):
            await self.handle_stats_command(update, context)
        elif message_text.startswith("/recent"):
            await self.handle_recent_command(update, context)
        elif message_text.startswith("/editar"):
            await self.handle_edit_command(update, context)
        elif message_text.startswith("/deshacer"):
            await self.handle_undo_command(update, context)
        elif message_text.startswith("/aprendizaje"):
            await self.handle_learning_dashboard_command(update, context)
        elif message_text.startswith("/olvidar"):
            await self.handle_forget_command(update, context)
        else:
            await self.send_error_message(update, "Comando de aprendizaje no reconocido")

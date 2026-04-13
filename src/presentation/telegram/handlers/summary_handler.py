import logging
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import OnDemandSummaryFormatter
from presentation.telegram.keyboards import build_monthly_summary_keyboard
from presentation.telegram.middleware.auth_middleware import require_authentication
from domain.exceptions import YNABApiException, OAuthException

logger = logging.getLogger(__name__)

_USAGE_HELP = (
    "❓ *Uso del comando /resumen:*\n\n"
    "• `/resumen` — mes actual\n"
    "• `/resumen dia` — hoy\n"
    "• `/resumen semana` — semana actual\n"
    "• `/resumen mes` — mes actual\n\n"
    "_Períodos válidos: dia, semana, mes_"
)

_NOT_CONFIGURED_MSG = (
    "⚙️ *Configuración incompleta*\n\n"
    "Aún no has configurado tu presupuesto YNAB.\n\n"
    "Usa /start para completar la configuración."
)


class SummaryHandler(BaseHandler):
    """Handler for the /resumen command."""

    def __init__(self, container):
        super().__init__(container)
        self.summary_service = container.get_on_demand_summary_service()
        self.auth_service = container.get_auth_service()

    def _get_user_config_for_callback(self, user_id: int):
        user_config = self.auth_service.user_repository.find_by_telegram_id(user_id)
        if not user_config or not user_config.is_authorized():
            return None
        return user_config

    @staticmethod
    def _format_monthly_view(summary, view: str) -> tuple[str, object]:
        if view == "categorias":
            return (
                OnDemandSummaryFormatter.format_monthly_categories_detail(summary),
                build_monthly_summary_keyboard("categorias"),
            )
        if view == "presupuesto":
            return (
                OnDemandSummaryFormatter.format_monthly_budget_detail(summary),
                build_monthly_summary_keyboard("presupuesto"),
            )
        return (
            OnDemandSummaryFormatter.format_summary(summary),
            build_monthly_summary_keyboard("resumen"),
        )

    @require_authentication(lambda self: self.auth_service)
    async def handle_resumen_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resumen [dia|semana|mes]"""
        self.log_handler_start("SummaryHandler.handle_resumen_command", update)

        # 1. Get user config (already registered by auth middleware, call again is safe)
        user_config = self.auth_service.register_user(update.effective_user)

        # 2. Check that user has completed setup
        if not user_config.is_configured():
            await self.send_message(update, _NOT_CONFIGURED_MSG)
            return

        # 3. Parse period argument
        period_arg = " ".join(context.args) if context.args else ""
        try:
            period_type = self.summary_service.parse_period(period_arg)
        except ValueError:
            await self.send_message(update, _USAGE_HELP)
            return

        # 4-6. Generate and format summary
        try:
            summary = self.summary_service.generate_summary(user_config, period_type)
            message = OnDemandSummaryFormatter.format_summary(summary)
            reply_markup = None
            if period_type == "mes" and summary.has_transactions:
                reply_markup = build_monthly_summary_keyboard("resumen")
            await self.send_message(update, message, reply_markup=reply_markup)
            self.log_handler_success("SummaryHandler.handle_resumen_command", update)

        except OAuthException as e:
            logger.warning(f"OAuth error for user {update.effective_user.id}: {e}")
            await self.send_message(
                update,
                "🔐 *Sesión expirada*\n\n"
                "Tu sesión de YNAB ha expirado. Usa /start para volver a conectar tu cuenta.",
            )
        except YNABApiException as e:
            logger.error(f"YNAB API error for user {update.effective_user.id}: {e}")
            await self.send_message(
                update,
                "⚠️ *Error al consultar YNAB*\n\n"
                "No fue posible obtener los datos de tu presupuesto. "
                "Intenta de nuevo en unos momentos.",
            )

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle monthly /resumen drill-down callbacks."""
        query = update.callback_query
        await query.answer()

        user_config = self._get_user_config_for_callback(query.from_user.id)
        if not user_config:
            await query.edit_message_text("🚫 No tienes autorización para realizar esta acción.")
            return

        if not user_config.is_configured():
            await query.edit_message_text(_NOT_CONFIGURED_MSG, parse_mode="Markdown")
            return

        data = query.data or ""
        if data not in {"resumen_mes_resumen", "resumen_mes_categorias", "resumen_mes_presupuesto"}:
            await query.edit_message_text("❌ Esta acción ya no es válida.")
            return

        view = data.replace("resumen_mes_", "")
        try:
            summary = self.summary_service.generate_summary(user_config, "mes")
            if not summary.has_transactions:
                await query.edit_message_text(
                    OnDemandSummaryFormatter.format_summary(summary),
                    parse_mode="Markdown",
                )
                return

            message, reply_markup = self._format_monthly_view(summary, view)
            await query.edit_message_text(
                message,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
        except OAuthException as e:
            logger.warning(f"OAuth error for user {query.from_user.id}: {e}")
            await query.edit_message_text(
                "🔐 *Sesión expirada*\n\n"
                "Tu sesión de YNAB ha expirado. Usa /start para volver a conectar tu cuenta.",
                parse_mode="Markdown",
            )
        except YNABApiException as e:
            logger.error(f"YNAB API error for user {query.from_user.id}: {e}")
            await query.edit_message_text(
                "⚠️ *Error al consultar YNAB*\n\n"
                "No fue posible obtener los datos de tu presupuesto. "
                "Intenta de nuevo en unos momentos.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error handling resumen callback for user {query.from_user.id}: {e}")
            await query.edit_message_text(
                "❌ Ocurrió un error procesando el resumen.",
            )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Satisfies BaseHandler abstract method for command and callback entrypoints."""
        if update.callback_query:
            await self.handle_callback_query(update, context)
        else:
            await self.handle_resumen_command(update, context)

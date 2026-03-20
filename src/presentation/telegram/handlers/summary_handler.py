import logging
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import OnDemandSummaryFormatter
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
            await self.send_message(update, message)
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

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Satisfies BaseHandler abstract method — delegates to handle_resumen_command."""
        await self.handle_resumen_command(update, context)

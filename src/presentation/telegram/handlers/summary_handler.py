import logging
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.middleware.auth_middleware import require_authentication

logger = logging.getLogger(__name__)

_DISABLED_MSG = (
    "⏸️ *`/resumen` está deshabilitado temporalmente*\n\n"
    "Todavía vemos diferencias frente a YNAB Reflect, así que lo desactivamos por ahora.\n"
    "Más adelante lo revisaremos y lo volveremos a habilitar cuando sea confiable."
)


class SummaryHandler(BaseHandler):
    """Handler for the /resumen command."""

    def __init__(self, container):
        super().__init__(container)
        self.auth_service = container.get_auth_service()

    @require_authentication(lambda self: self.auth_service)
    async def handle_resumen_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resumen while the feature is temporarily disabled."""
        self.log_handler_start("SummaryHandler.handle_resumen_command", update)
        await self.send_message(update, _DISABLED_MSG)
        self.log_handler_success("SummaryHandler.handle_resumen_command", update)

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle stale monthly /resumen callbacks while the feature is disabled."""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "⏸️ `/resumen` está deshabilitado temporalmente.",
            parse_mode="Markdown",
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Satisfies BaseHandler abstract method for command and callback entrypoints."""
        if update.callback_query:
            await self.handle_callback_query(update, context)
        else:
            await self.handle_resumen_command(update, context)

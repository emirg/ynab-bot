import logging

from telegram import Update
from telegram.ext import ContextTypes

from domain.models.onboarding import OnboardingStep
from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.middleware.auth_middleware import require_authentication

logger = logging.getLogger(__name__)


class AdvisorHandler(BaseHandler):
    def __init__(self, container):
        super().__init__(container)
        self._advisor_access_service = container.get_advisor_access_service()
        self._onboarding_service = container.get_onboarding_service()

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_analisis_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.log_handler_start("AdvisorHandler.handle_analisis_command", update)
        try:
            user_id = self.get_user_id(update)
            onboarding_step = self._onboarding_service.get_onboarding_step(user_id)
            if onboarding_step != OnboardingStep.COMPLETE:
                await self.send_message(update, self._build_blocked_message(onboarding_step))
                return

            launch_url = self._advisor_access_service.create_launch_url(user_id)
            await self.send_message(
                update,
                "📊 *Advisor financiero*\n\n"
                "Tu acceso web ya está listo. Abre este enlace para entrar al advisor:\n\n"
                f"[Abrir advisor]({launch_url})\n\n"
                "_El enlace es personal y vence pronto por seguridad._",
            )
            self.log_handler_success("AdvisorHandler.handle_analisis_command", update)
        except Exception as exc:
            self.log_handler_error("AdvisorHandler.handle_analisis_command", update, exc)
            await self.send_error_message(update, "No pude abrir el advisor en este momento.")

    @staticmethod
    def _build_blocked_message(step: OnboardingStep) -> str:
        if step == OnboardingStep.NEEDS_YNAB_CONNECTION:
            return "📊 *Advisor financiero*\n\nPrimero debes conectar tu cuenta de YNAB con `/connect`."
        if step == OnboardingStep.NEEDS_BUDGET:
            return "📊 *Advisor financiero*\n\nPrimero debes elegir un presupuesto con `/budgets`."
        return "📊 *Advisor financiero*\n\nPrimero debes configurar tu cuenta por defecto con `/accounts`."

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_analisis_command(update, context)

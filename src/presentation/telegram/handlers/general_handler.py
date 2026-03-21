import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import GeneralResponseFormatter
from presentation.telegram.keyboards import (
    build_budget_selection_keyboard,
    build_account_selection_keyboard
)
from presentation.telegram.middleware.auth_middleware import require_authentication
from domain.models.onboarding import OnboardingStep

logger = logging.getLogger(__name__)


class GeneralHandler(BaseHandler):
    """Handler for general commands like /start and /help"""
    
    def __init__(self, container):
        super().__init__(container)
        self.formatter = GeneralResponseFormatter()
        self.onboarding_service = container.get_onboarding_service()
        self.user_config_service = container.get_user_config_service()
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - registration/welcome for all users"""
        self.log_handler_start("GeneralHandler.handle_start_command", update)
        
        # Special handling for /start - allow all users to register/see welcome
        user = update.effective_user
        if user:
            auth_service = self.container.get_auth_service()
            user_config = auth_service.register_user(user)
            
            # Show appropriate message based on user status
            if user_config.is_authorized():
                # Authorized user gets guided onboarding
                try:
                    user_id = user.id
                    step = self.onboarding_service.get_onboarding_step(user_id)
                    user_name = user.first_name or user_config.get_display_name()
                    
                    message = self.formatter.format_onboarding_welcome(user_name, step)
                    
                    if step == OnboardingStep.NEEDS_YNAB_CONNECTION:
                        # Add connect button
                        oauth_service = self.container.get_oauth_service()
                        auth_url = oauth_service.generate_auth_url(user_id)
                        keyboard = [[InlineKeyboardButton("🔗 Conectar YNAB", url=auth_url)]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                        
                    elif step == OnboardingStep.NEEDS_BUDGET:
                        # Auto-show budgets
                        budgets = self.user_config_service.get_available_budgets(user_id)
                        reply_markup = build_budget_selection_keyboard(budgets)
                        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                        
                    elif step == OnboardingStep.NEEDS_ACCOUNT:
                        # Auto-show accounts
                        accounts, error = self.user_config_service.get_user_accounts(user_id)
                        if error:
                            await self.send_error_message(update, error)
                            return
                        reply_markup = build_account_selection_keyboard(accounts)
                        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                        
                    else: # COMPLETE
                        await self.send_message(update, message)
                        
                    self.log_handler_success("GeneralHandler.handle_start_command", update)
                    return
                except Exception as e:
                    self.log_handler_error("GeneralHandler.handle_start_command", update, e)
                    await self.send_error_message(update, f"Error mostrando mensaje de bienvenida: {str(e)}")
                    return
            
            elif user_config.is_pending():
                # Pending user gets registration confirmation
                await update.message.reply_text(
                    f"👋 *¡Hola {user_config.get_display_name()}!*\n\n"
                    "📝 Te has registrado exitosamente en el bot YNAB.\n\n"
                    "⏳ *Tu solicitud está pendiente de aprobación por un administrador.*\n\n"
                    f"*Tu ID:* `{user.id}`\n"
                    "*Estado:* Pendiente\n\n"
                    "Te notificaremos tan pronto como tu acceso sea aprobado.",
                    parse_mode='Markdown'
                )
                return
            
            elif user_config.is_blocked():
                # Blocked user gets blocked message
                await update.message.reply_text(
                    "🚫 *Acceso Bloqueado*\n\n"
                    "Tu acceso a este bot ha sido restringido por un administrador.\n\n"
                    "Si crees que esto es un error, contacta al administrador del bot.",
                    parse_mode='Markdown'
                )
                return
        
        # Fallback for any error
        await update.message.reply_text("❌ Error procesando registro.")
    
    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        self.log_handler_start("GeneralHandler.handle_help_command", update)
        
        try:
            message = self.formatter.format_help_message()
            await self.send_message(update, message)
            self.log_handler_success("GeneralHandler.handle_help_command", update)
            
        except Exception as e:
            self.log_handler_error("GeneralHandler.handle_help_command", update, e)
            await self.send_error_message(update, f"Error mostrando ayuda: {str(e)}")
    
    async def handle_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands - check auth first"""
        self.log_handler_start("GeneralHandler.handle_unknown_command", update)
        
        # Check authorization for unknown commands
        user = update.effective_user
        if user:
            auth_service = self.container.get_auth_service()
            if not auth_service.is_authorized(user.id):
                middleware = self.container.get_auth_service()
                user_config = middleware.register_user(user)
                
                if user_config.is_pending():
                    await update.message.reply_text(
                        "⏳ Tu solicitud está pendiente de aprobación.\n"
                        "Usa /start para ver el estado de tu registro."
                    )
                elif user_config.is_blocked():
                    await update.message.reply_text(
                        "🚫 No tienes acceso a este bot."
                    )
                else:
                    await update.message.reply_text(
                        "❌ Necesitas autorización para usar este bot.\n"
                        "Usa /start para registrarte."
                    )
                return
        
        try:
            command = update.message.text.split()[0] if update.message.text else ""
            
            # Check if user is admin to show admin commands
            auth_service = self.container.get_auth_service()
            is_admin = auth_service.is_admin(user.id)
            
            admin_commands = ""
            if is_admin:
                admin_commands = """

🔐 *Comandos de administrador:*
• `/admin` - Panel de administración
• `/pending` - Ver usuarios pendientes
• `/users` - Ver todos los usuarios
• `/approve <user_id>` - Aprobar usuario
• `/block <user_id>` - Bloquear usuario"""
            
            message = f"""
❓ *Comando no reconocido:* `{command}`

🔹 *Comandos disponibles:*
{self.formatter.format_command_list()}{admin_commands}

💡 *O simplemente envía un mensaje de gasto:*
"Gasté $40000 en comida en Éxito"
            """.strip()
            
            await self.send_message(update, message)
            self.log_handler_success("GeneralHandler.handle_unknown_command", update)
            
        except Exception as e:
            self.log_handler_error("GeneralHandler.handle_unknown_command", update, e)
            await self.send_error_message(update, f"Error procesando comando: {str(e)}")
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main handler entry point"""
        message_text = update.message.text or ""
        
        if message_text.startswith('/start'):
            await self.handle_start_command(update, context)
        elif message_text.startswith('/help'):
            await self.handle_help_command(update, context)
        else:
            await self.handle_unknown_command(update, context)
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import ConfigResponseFormatter, GeneralResponseFormatter
from presentation.telegram.keyboards import (
    build_budget_selection_keyboard, 
    build_account_selection_keyboard
)
from presentation.telegram.middleware.auth_middleware import require_authentication
from application.services.user_config_service import UserConfigService
from application.services.oauth_service import YNABOAuthService
from domain.exceptions import YNABApiException, OAuthException

logger = logging.getLogger(__name__)


class ConfigHandler(BaseHandler):
    """Handler for user configuration commands"""

    def __init__(self, container):
        super().__init__(container)
        self.user_config_service = container.get_user_config_service()
        self.split_config_service = container.get_split_config_service()
        self.oauth_service = container.get_oauth_service()
        self.auth_service = container.get_auth_service()
        self.formatter = ConfigResponseFormatter()
    
    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /config command - show configuration options"""
        self.log_handler_start("ConfigHandler.handle_config_command", update)
        
        try:
            keyboard = [
                [InlineKeyboardButton("💰 Ver presupuestos", callback_data="config_budgets")],
                [InlineKeyboardButton("💳 Ver cuentas", callback_data="config_accounts")],
                [InlineKeyboardButton("📊 Ver estado actual", callback_data="config_status")],
                [InlineKeyboardButton("🔄 Reiniciar configuración", callback_data="config_reset")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = """
🔧 *Panel de Configuración*

Selecciona una opción para configurar tu bot:

💰 *Presupuestos* - Ver y seleccionar tu presupuesto YNAB
💳 *Cuentas* - Ver y configurar cuenta por defecto
📊 *Estado* - Ver tu configuración actual
🔄 *Reiniciar* - Limpiar toda la configuración

💡 También puedes usar comandos directos:
• `/budgets` - Ver presupuestos
• `/accounts` - Ver cuentas
• `/status` - Ver estado
            """.strip()
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            self.log_handler_success("ConfigHandler.handle_config_command", update)
            
        except Exception as e:
            self.log_handler_error("ConfigHandler.handle_config_command", update, e)
            await self.send_error_message(update, "Ocurrió un error mostrando la configuración.")
    
    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /connect command - generate YNAB OAuth URL"""
        self.log_handler_start("ConfigHandler.handle_connect_command", update)
        try:
            user_id = self.get_user_id(update)
            auth_url = self.oauth_service.generate_auth_url(user_id)
            message = (
                "🔗 *Conectar cuenta YNAB*\n\n"
                "Haz clic en el siguiente enlace para autorizar el acceso a tu cuenta YNAB:\n\n"
                f"[Conectar YNAB]({auth_url})\n\n"
                "_Después de autorizar, serás redirigido a una página de confirmación._"
            )
            await update.message.reply_text(message, parse_mode='Markdown')
            self.log_handler_success("ConfigHandler.handle_connect_command", update)
        except Exception as e:
            self.log_handler_error("ConfigHandler.handle_connect_command", update, e)
            await self.send_error_message(update, "Ocurrió un error generando el enlace de conexión.")

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_disconnect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /disconnect command - remove YNAB OAuth tokens"""
        self.log_handler_start("ConfigHandler.handle_disconnect_command", update)
        try:
            user_id = self.get_user_id(update)
            success = self.oauth_service.disconnect_user(user_id)
            if success:
                await update.message.reply_text(
                    "✅ *Cuenta YNAB desconectada*\n\nUsa /connect para vincular otra cuenta.",
                    parse_mode='Markdown'
                )
            else:
                await self.send_error_message(update, "No se pudo desconectar la cuenta.")
            self.log_handler_success("ConfigHandler.handle_disconnect_command", update)
        except Exception as e:
            self.log_handler_error("ConfigHandler.handle_disconnect_command", update, e)
            await self.send_error_message(update, "Ocurrió un error desconectando la cuenta.")

    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_budgets_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /budgets command - show available budgets"""
        self.log_handler_start("ConfigHandler.handle_budgets_command", update)

        try:
            user_id = self.get_user_id(update)
            budgets = self.user_config_service.get_available_budgets(user_id)
            response = self.formatter.format_budgets_list(budgets)
            
            # Create inline keyboard for budget selection
            reply_markup = build_budget_selection_keyboard(budgets) if budgets else None
            
            await self.send_message(update, response)
            if reply_markup:
                await update.message.reply_text(
                    "👆 *Selecciona un presupuesto tocando el botón correspondiente*",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
            self.log_handler_success("ConfigHandler.handle_budgets_command", update)
            
        except YNABApiException as e:
            self.log_handler_error("ConfigHandler.handle_budgets_command", update, e)
            await self.send_error_message(update, str(e))
        except Exception as e:
            self.log_handler_error("ConfigHandler.handle_budgets_command", update, e)
            await self.send_error_message(update, "Ocurrió un error obteniendo los presupuestos.")
    
    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /accounts command - show available accounts"""
        self.log_handler_start("ConfigHandler.handle_accounts_command", update)
        
        try:
            user_id = self.get_user_id(update)
            accounts, error = self.user_config_service.get_user_accounts(user_id)
            
            if error:
                await self.send_error_message(update, error)
                return
            
            response = self.formatter.format_accounts_list(accounts)
            
            # Create inline keyboard for account selection
            reply_markup = build_account_selection_keyboard(accounts) if accounts else None
            
            await self.send_message(update, response)
            if reply_markup:
                await update.message.reply_text(
                    "👆 *Selecciona una cuenta tocando el botón correspondiente*",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
            self.log_handler_success("ConfigHandler.handle_accounts_command", update)
            
        except Exception as e:
            self.log_handler_error("ConfigHandler.handle_accounts_command", update, e)
            await self.send_error_message(update, "Ocurrió un error obteniendo las cuentas.")
    
    @require_authentication(lambda self: self.container.get_auth_service())
    async def handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show user configuration status"""
        self.log_handler_start("ConfigHandler.handle_status_command", update)
        
        try:
            user_id = self.get_user_id(update)
            status = self.user_config_service.get_user_status(user_id)
            
            # Add split config info
            summary = self.split_config_service.get_split_config_summary(user_id)
            status["split_group_count"] = len(summary.get("groups", []))
            
            response = self.formatter.format_user_status(status)
            
            await self.send_message(update, response)
            self.log_handler_success("ConfigHandler.handle_status_command", update)
            
        except Exception as e:
            self.log_handler_error("ConfigHandler.handle_status_command", update, e)
            await self.send_error_message(update, "Ocurrió un error obteniendo el estado.")
    
    @require_authentication(lambda self: self.container.get_auth_service())
    async def zona_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /zona command - view or update user timezone"""
        self.log_handler_start("ConfigHandler.zona_command", update)

        try:
            user_id = self.get_user_id(update)
            args = context.args

            if not args:
                # Show current timezone
                status = self.user_config_service.get_user_status(user_id)
                tz = status.get('timezone', 'No configurada')
                await self.send_message(
                    update,
                    f"🕐 *Zona horaria actual:* `{tz}`\n\n"
                    "Para cambiarla, usa:\n`/zona America/Bogota`"
                )
            else:
                timezone_str = args[0]
                try:
                    self.user_config_service.update_timezone(user_id, timezone_str)
                    await self.send_message(
                        update,
                        f"✅ Zona horaria actualizada a `{timezone_str}`"
                    )
                except ValueError as e:
                    await self.send_error_message(update, str(e))

            self.log_handler_success("ConfigHandler.zona_command", update)

        except Exception as e:
            self.log_handler_error("ConfigHandler.zona_command", update, e)
            await self.send_error_message(update, "Ocurrio un error con la zona horaria.")

    async def handle_budgets_callback(self, query):
        """Handle budgets callback from inline keyboard"""
        try:
            user_id = query.from_user.id
            budgets = self.user_config_service.get_available_budgets(user_id)
            response = self.formatter.format_budgets_list(budgets)
            
            # Create inline keyboard for budget selection
            reply_markup = build_budget_selection_keyboard(budgets) if budgets else None
            
            await self.send_callback_message(query, response)
            if reply_markup:
                await query.message.reply_text(
                    "👆 *Selecciona un presupuesto tocando el botón correspondiente*",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except YNABApiException as e:
            await self.send_callback_error(query, str(e))
        except Exception as e:
            await self.send_callback_error(query, "Ocurrió un error obteniendo los presupuestos.")
    
    async def handle_accounts_callback(self, query):
        """Handle accounts callback from inline keyboard"""
        try:
            user_id = query.from_user.id
            accounts, error = self.user_config_service.get_user_accounts(user_id)
            
            if error:
                await self.send_callback_error(query, error)
                return
            
            response = self.formatter.format_accounts_list(accounts)
            
            # Create inline keyboard for account selection
            reply_markup = build_account_selection_keyboard(accounts) if accounts else None
            
            await self.send_callback_message(query, response)
            if reply_markup:
                await query.message.reply_text(
                    "👆 *Selecciona una cuenta tocando el botón correspondiente*",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            await self.send_callback_error(query, "Ocurrió un error obteniendo las cuentas.")
    
    async def handle_status_callback(self, query):
        """Handle status callback from inline keyboard"""
        try:
            user_id = query.from_user.id
            status = self.user_config_service.get_user_status(user_id)
            
            # Add split config info
            summary = self.split_config_service.get_split_config_summary(user_id)
            status["split_group_count"] = len(summary.get("groups", []))
            
            response = self.formatter.format_user_status(status)
            
            await self.send_callback_message(query, response)
            
        except Exception as e:
            await self.send_callback_error(query, "Ocurrió un error obteniendo el estado.")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()

        # Verify user is still authorized before processing callback
        user_id = query.from_user.id
        user_config = self.auth_service.user_repository.find_by_telegram_id(user_id)
        if not user_config or not user_config.is_authorized():
            await query.edit_message_text("🚫 No tienes autorización para realizar esta acción.")
            return

        try:
            data = query.data
            
            if data == "config_budgets":
                await self.handle_budgets_callback(query)
                
            elif data == "config_accounts":
                await self.handle_accounts_callback(query)
                
            elif data == "config_status":
                await self.handle_status_callback(query)
                
            elif data == "config_reset":
                success = self.user_config_service.reset_user_config(user_id)
                if success:
                    await query.edit_message_text("✅ *Configuración reiniciada exitosamente*\n\nUsa `/config` para configurar de nuevo.", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ *Error reiniciando configuración*", parse_mode='Markdown')
                    
            elif data.startswith("select_budget_"):
                budget_id = data.replace("select_budget_", "")
                try:
                    self.user_config_service.set_user_budget(user_id, budget_id)
                    # Step 8: Auto-show accounts after budget selection
                    accounts, error = self.user_config_service.get_user_accounts(user_id)
                    if error:
                        await query.edit_message_text(f"✅ *Presupuesto configurado!*\n\n⚠️ Pero hubo un error al obtener cuentas: {error}", parse_mode='Markdown')
                        return
                    
                    reply_markup = build_account_selection_keyboard(accounts)
                    await query.edit_message_text(
                        "✅ *Presupuesto configurado exitosamente!*\n\n"
                        "Ahora selecciona tu cuenta por defecto:",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                except YNABApiException as e:
                    await query.edit_message_text(f"❌ *Error:* {str(e)}", parse_mode='Markdown')

            elif data.startswith("select_account_"):
                account_id = data.replace("select_account_", "")
                try:
                    self.user_config_service.set_default_account(user_id, account_id)
                    # Step 9: Show onboarding complete message
                    message = GeneralResponseFormatter.format_onboarding_complete()
                    await query.edit_message_text(message, parse_mode='Markdown')
                except YNABApiException as e:
                    await query.edit_message_text(f"❌ *Error:* {str(e)}", parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            await query.edit_message_text("❌ Ocurrió un error procesando la acción.")
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main handler entry point"""
        if update.callback_query:
            await self.handle_callback_query(update, context)
        elif update.message:
            command = context.args[0] if context.args else "config"
            
            if command == "budgets":
                await self.handle_budgets_command(update, context)
            elif command == "accounts":
                await self.handle_accounts_command(update, context)
            elif command == "status":
                await self.handle_status_command(update, context)
            else:
                await self.handle_config_command(update, context)
from __future__ import annotations

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.middleware.auth_middleware import require_admin
from domain.models.user import UserStatus

logger = logging.getLogger(__name__)


class AdminHandler(BaseHandler):
    """Handler for admin-only commands"""
    
    def __init__(self, container: DIContainer):
        super().__init__(container)
        self.auth_service = container.get_auth_service()
    
    @require_admin(lambda self: self.auth_service)
    async def handle_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin panel"""
        admin_menu = """
🔐 *Panel de Administración*

*Comandos disponibles:*
• `/pending` - Ver usuarios pendientes de aprobación
• `/users` - Ver todos los usuarios registrados
• `/approve <user_id>` - Aprobar usuario
• `/block <user_id>` - Bloquear usuario
• `/stats` - Estadísticas del sistema

*Información:*
• Solo los administradores pueden ejecutar estos comandos
• Los cambios se aplican inmediatamente
• Los usuarios serán notificados de cambios de estado
        """
        await update.message.reply_text(admin_menu, parse_mode='Markdown')
    
    @require_admin(lambda self: self.auth_service)
    async def handle_pending_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show users pending approval"""
        pending_users = self.auth_service.get_pending_users()
        
        if not pending_users:
            await update.message.reply_text(
                "✅ *Sin usuarios pendientes*\n\n"
                "No hay usuarios esperando aprobación en este momento.",
                parse_mode='Markdown'
            )
            return
        
        message = f"⏳ *Usuarios Pendientes ({len(pending_users)})*\n\n"
        
        # Create inline keyboard for approvals
        keyboard = []
        
        for user in pending_users[:10]:  # Limit to 10 users to avoid message too long
            user_info = f"• *{user.get_display_name()}* (ID: `{user.telegram_id}`)\n"
            user_info += f"  Registrado: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            message += user_info + "\n"
            
            # Add approval/block buttons
            keyboard.append([
                InlineKeyboardButton(f"✅ Aprobar {user.get_display_name()[:20]}", 
                                   callback_data=f"approve_{user.telegram_id}"),
                InlineKeyboardButton(f"🚫 Bloquear", 
                                   callback_data=f"block_{user.telegram_id}")
            ])
        
        if len(pending_users) > 10:
            message += f"\n... y {len(pending_users) - 10} usuarios más.\n"
            message += "Usa `/users` para ver todos los usuarios."
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(
            message, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    @require_admin(lambda self: self.auth_service)
    async def handle_all_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all registered users"""
        all_users = self.auth_service.get_all_users()
        
        if not all_users:
            await update.message.reply_text("📝 No hay usuarios registrados.")
            return
        
        # Group users by status
        users_by_status = {
            UserStatus.AUTHORIZED: [],
            UserStatus.PENDING: [],
            UserStatus.BLOCKED: []
        }
        
        for user in all_users:
            users_by_status[user.status].append(user)
        
        message = f"👥 *Usuarios Registrados ({len(all_users)} total)*\n\n"
        
        # Show authorized users
        authorized = users_by_status[UserStatus.AUTHORIZED]
        if authorized:
            message += f"✅ *Autorizados ({len(authorized)}):*\n"
            for user in authorized[:5]:
                message += f"• {user.get_display_name()} (ID: `{user.telegram_id}`)\n"
            if len(authorized) > 5:
                message += f"  ... y {len(authorized) - 5} más\n"
            message += "\n"
        
        # Show pending users
        pending = users_by_status[UserStatus.PENDING]
        if pending:
            message += f"⏳ *Pendientes ({len(pending)}):*\n"
            for user in pending[:5]:
                message += f"• {user.get_display_name()} (ID: `{user.telegram_id}`)\n"
            if len(pending) > 5:
                message += f"  ... y {len(pending) - 5} más\n"
            message += "\n"
        
        # Show blocked users
        blocked = users_by_status[UserStatus.BLOCKED]
        if blocked:
            message += f"🚫 *Bloqueados ({len(blocked)}):*\n"
            for user in blocked[:3]:
                message += f"• {user.get_display_name()} (ID: `{user.telegram_id}`)\n"
            if len(blocked) > 3:
                message += f"  ... y {len(blocked) - 3} más\n"
            message += "\n"
        
        message += "*Comandos útiles:*\n"
        message += "• `/pending` - Ver solo pendientes\n"
        message += "• `/approve <user_id>` - Aprobar usuario\n"
        message += "• `/block <user_id>` - Bloquear usuario"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    @require_admin(lambda self: self.auth_service)
    async def handle_approve_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Approve a user"""
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso incorrecto*\n\n"
                "Uso: `/approve <user_id>`\n"
                "Ejemplo: `/approve 123456789`",
                parse_mode='Markdown'
            )
            return
        
        try:
            user_id = int(context.args[0])
            admin_id = update.effective_user.id
            
            success = self.auth_service.authorize_user(user_id, admin_id)
            
            if success:
                # Get user info for confirmation
                user = self.auth_service.user_repository.find_by_telegram_id(user_id)
                user_name = user.get_display_name() if user else f"User {user_id}"
                
                await update.message.reply_text(
                    f"✅ *Usuario Aprobado*\n\n"
                    f"*Usuario:* {user_name}\n"
                    f"*ID:* `{user_id}`\n"
                    f"*Aprobado por:* {update.effective_user.first_name}\n\n"
                    f"El usuario ya puede usar el bot.",
                    parse_mode='Markdown'
                )

                # Try to notify the user (this might fail if bot can't message them)
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🎉 *¡Acceso Aprobado!*\n\n"
                             f"Tu solicitud de acceso al bot YNAB ha sido aprobada.\n\n"
                             f"Ya puedes comenzar a usar todas las funciones del bot. "
                             f"Usa /start para ver los comandos disponibles.",
                        parse_mode='Markdown'
                    )
                    logger.info(f"User {user_id} notified of approval")
                except Exception as e:
                    logger.warning(f"Could not notify user {user_id} of approval: {e}")
            else:
                await update.message.reply_text(
                    f"❌ *Error*\n\n"
                    f"No se pudo aprobar el usuario `{user_id}`.\n"
                    f"Verifica que el ID sea correcto y que el usuario esté registrado.",
                    parse_mode='Markdown'
                )

        except ValueError:
            await update.message.reply_text(
                "❌ *ID inválido*\n\n"
                "El ID de usuario debe ser un número.\n"
                "Ejemplo: `/approve 123456789`",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error approving user: {e}")
            await update.message.reply_text(
                "❌ Error interno al aprobar usuario."
            )
    
    @require_admin(lambda self: self.auth_service)
    async def handle_block_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Block a user"""
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso incorrecto*\n\n"
                "Uso: `/block <user_id>`\n"
                "Ejemplo: `/block 123456789`",
                parse_mode='Markdown'
            )
            return
        
        try:
            user_id = int(context.args[0])
            admin_id = update.effective_user.id
            
            success = self.auth_service.block_user(user_id, admin_id)
            
            if success:
                # Get user info for confirmation
                user = self.auth_service.user_repository.find_by_telegram_id(user_id)
                user_name = user.get_display_name() if user else f"User {user_id}"
                
                await update.message.reply_text(
                    f"🚫 *Usuario Bloqueado*\n\n"
                    f"*Usuario:* {user_name}\n"
                    f"*ID:* `{user_id}`\n"
                    f"*Bloqueado por:* {update.effective_user.first_name}\n\n"
                    f"El usuario ya no puede usar el bot.",
                    parse_mode='Markdown'
                )

                # Try to notify the user
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🚫 *Acceso Bloqueado*\n\n"
                             f"Tu acceso al bot YNAB ha sido restringido por un administrador.\n\n"
                             f"Si crees que esto es un error, contacta al administrador del bot.",
                        parse_mode='Markdown'
                    )
                    logger.info(f"User {user_id} notified of being blocked")
                except Exception as e:
                    logger.warning(f"Could not notify user {user_id} of being blocked: {e}")
            else:
                await update.message.reply_text(
                    f"❌ *Error*\n\n"
                    f"No se pudo bloquear el usuario `{user_id}`.\n"
                    f"Verifica que el ID sea correcto y que el usuario esté registrado.",
                    parse_mode='Markdown'
                )

        except ValueError:
            await update.message.reply_text(
                "❌ *ID inválido*\n\n"
                "El ID de usuario debe ser un número.\n"
                "Ejemplo: `/block 123456789`",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error blocking user: {e}")
            await update.message.reply_text(
                "❌ Error interno al bloquear usuario."
            )
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel callback queries"""
        query = update.callback_query
        await query.answer()
        
        if not self.auth_service.is_admin(update.effective_user.id):
            await query.edit_message_text("🚫 Sin permisos de administrador.")
            return
        
        data = query.data
        
        try:
            if data.startswith("approve_"):
                user_id = int(data.replace("approve_", ""))
                admin_id = update.effective_user.id
                
                success = self.auth_service.authorize_user(user_id, admin_id)
                
                if success:
                    # Get user info
                    user = self.auth_service.user_repository.find_by_telegram_id(user_id)
                    user_name = user.get_display_name() if user else f"User {user_id}"
                    
                    await query.edit_message_text(
                        f"✅ *Usuario Aprobado*\n\n"
                        f"*Usuario:* {user_name}\n"
                        f"*ID:* `{user_id}`\n"
                        f"*Aprobado por:* {update.effective_user.first_name}",
                        parse_mode='Markdown'
                    )

                    # Notify user
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"🎉 *¡Acceso Aprobado!*\n\n"
                                 f"Tu solicitud de acceso ha sido aprobada. "
                                 f"Ya puedes usar el bot. Usa /start para comenzar.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify user {user_id}: {e}")
                else:
                    await query.edit_message_text(
                        f"❌ Error aprobando usuario {user_id}"
                    )
            
            elif data.startswith("block_"):
                user_id = int(data.replace("block_", ""))
                admin_id = update.effective_user.id
                
                success = self.auth_service.block_user(user_id, admin_id)
                
                if success:
                    # Get user info
                    user = self.auth_service.user_repository.find_by_telegram_id(user_id)
                    user_name = user.get_display_name() if user else f"User {user_id}"
                    
                    await query.edit_message_text(
                        f"🚫 *Usuario Bloqueado*\n\n"
                        f"*Usuario:* {user_name}\n"
                        f"*ID:* `{user_id}`\n"
                        f"*Bloqueado por:* {update.effective_user.first_name}",
                        parse_mode='Markdown'
                    )

                    # Notify user
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"🚫 *Acceso Bloqueado*\n\n"
                                 f"Tu acceso al bot ha sido restringido. "
                                 f"Contacta al administrador si crees que es un error.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify user {user_id}: {e}")
                else:
                    await query.edit_message_text(
                        f"❌ Error bloqueando usuario {user_id}"
                    )
        
        except ValueError:
            await query.edit_message_text("❌ ID de usuario inválido")
        except Exception as e:
            logger.error(f"Error in admin callback: {e}")
            await query.edit_message_text("❌ Error procesando acción")
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main handler entry point for admin commands"""
        message_text = update.message.text or ""
        
        if message_text.startswith('/admin'):
            await self.handle_admin_command(update, context)
        elif message_text.startswith('/pending'):
            await self.handle_pending_users(update, context)
        elif message_text.startswith('/users'):
            await self.handle_all_users(update, context)
        elif message_text.startswith('/approve'):
            await self.handle_approve_user(update, context)
        elif message_text.startswith('/block'):
            await self.handle_block_user(update, context)
        else:
            await self.send_error_message(update, "Comando de administración no reconocido")
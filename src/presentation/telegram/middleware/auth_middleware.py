from functools import wraps
from typing import Callable, List
from telegram import Update
from telegram.ext import ContextTypes
import logging

from domain.services.auth_service import AuthorizationService

logger = logging.getLogger(__name__)


def require_authentication(auth_service_getter: Callable):
    """Decorator to require user authentication for bot commands"""
    def decorator(handler_func: Callable):
        @wraps(handler_func)
        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                await update.message.reply_text("❌ Error de autenticación.")
                return
            
            # Get auth service from the handler instance
            auth_service = auth_service_getter(self)
            
            # Register or update user info
            user_config = auth_service.register_user(user)
            
            # Check if user is authorized
            if not user_config.is_authorized():
                if user_config.is_pending():
                    await update.message.reply_text(
                        "⏳ *Acceso Pendiente*\n\n"
                        "Tu solicitud de acceso está pendiente de aprobación por un administrador.\n\n"
                        "📝 *Información registrada:*\n"
                        f"• ID: `{user.id}`\n"
                        f"• Nombre: {user_config.get_display_name()}\n\n"
                        "Por favor espera a que un administrador apruebe tu acceso.",
                        parse_mode='Markdown'
                    )
                elif user_config.is_blocked():
                    await update.message.reply_text(
                        "🚫 *Acceso Bloqueado*\n\n"
                        "Tu acceso a este bot ha sido bloqueado por un administrador.\n\n"
                        "Si crees que esto es un error, contacta al administrador del bot.",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "❌ *Sin Autorización*\n\n"
                        "No tienes autorización para usar este bot. "
                        "Un administrador debe aprobar tu acceso primero.",
                        parse_mode='Markdown'
                    )
                return
            
            # User is authorized, proceed with the command
            return await handler_func(self, update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def require_admin(auth_service_getter: Callable):
    """Decorator to require admin privileges for bot commands"""
    def decorator(handler_func: Callable):
        @wraps(handler_func)
        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                await update.message.reply_text("❌ Error de autenticación.")
                return
            
            # Get auth service from the handler instance
            auth_service = auth_service_getter(self)
            
            # Check if user is admin
            if not auth_service.is_admin(user.id):
                await update.message.reply_text(
                    "🚫 *Acceso Restringido*\n\n"
                    "Este comando está disponible solo para administradores.",
                    parse_mode='Markdown'
                )
                logger.warning(f"User {user.id} (@{user.username}) attempted admin command without privileges")
                return
            
            # User is admin, proceed with the command
            return await handler_func(self, update, context, *args, **kwargs)
        
        return wrapper
    return decorator


class AuthenticationMiddleware:
    """Middleware for handling authentication in Telegram bot handlers"""
    
    def __init__(self, auth_service: AuthorizationService):
        self.auth_service = auth_service
    
    async def check_authorization(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is authorized to use the bot"""
        user = update.effective_user
        if not user:
            return False
        
        # Register or update user info
        user_config = self.auth_service.register_user(user)
        
        return user_config.is_authorized()
    
    async def handle_unauthorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unauthorized access attempts"""
        user = update.effective_user
        if not user:
            await update.message.reply_text("❌ Error de autenticación.")
            return
        
        user_config = self.auth_service.register_user(user)
        
        if user_config.is_pending():
            await update.message.reply_text(
                "⏳ *Solicitud Pendiente*\n\n"
                f"Hola {user_config.get_display_name()}, tu solicitud de acceso está pendiente.\n\n"
                "Un administrador debe aprobar tu acceso antes de que puedas usar el bot.\n\n"
                f"*Tu ID:* `{user.id}`\n"
                f"*Estado:* Pendiente de aprobación\n\n"
                "Te notificaremos cuando tu acceso sea aprobado.",
                parse_mode='Markdown'
            )
        elif user_config.is_blocked():
            await update.message.reply_text(
                "🚫 *Acceso Bloqueado*\n\n"
                "Tu acceso ha sido bloqueado por un administrador.\n\n"
                "Si crees que esto es un error, contacta al administrador del bot.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ *Sin Autorización*\n\n"
                "Necesitas autorización para usar este bot.\n\n"
                f"*Tu ID:* `{user.id}`\n"
                f"*Nombre:* {user_config.get_display_name()}\n\n"
                "Un administrador debe aprobar tu acceso.",
                parse_mode='Markdown'
            )
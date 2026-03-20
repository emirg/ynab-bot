import logging
from abc import ABC, abstractmethod
from telegram import Update
from telegram.ext import ContextTypes

from infrastructure.container import DIContainer
from infrastructure.logging_config import log_with_context

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """Base class for Telegram command handlers"""
    
    def __init__(self, container: DIContainer):
        self.container = container
    
    @abstractmethod
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the command/message"""
        pass
    
    def get_user_id(self, update: Update) -> int:
        """Get Telegram user ID from update"""
        return update.effective_user.id
    
    def get_user_name(self, update: Update) -> str:
        """Get user's display name"""
        user = update.effective_user
        return user.full_name or user.username or f"User {user.id}"
    
    async def send_message(self, update: Update, message: str, parse_mode: str = 'Markdown', reply_markup=None):
        """Send formatted message to user"""
        try:
            if update.callback_query:
                # For callback queries, reply to the original message
                await update.callback_query.message.reply_text(message, parse_mode=parse_mode, reply_markup=reply_markup)
            else:
                # For regular messages
                await update.message.reply_text(message, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            # Fallback without formatting
            try:
                if update.callback_query:
                    await update.callback_query.message.reply_text(message, reply_markup=reply_markup)
                else:
                    await update.message.reply_text(message, reply_markup=reply_markup)
            except Exception as e2:
                logger.error(f"Failed to send fallback message: {e2}")
    
    async def send_callback_message(self, query, message: str, parse_mode: str = 'Markdown', reply_markup=None):
        """Send message as reply to callback query"""
        try:
            await query.message.reply_text(message, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to send callback message: {e}")
            # Fallback without formatting
            try:
                await query.message.reply_text(message, reply_markup=reply_markup)
            except Exception as e2:
                logger.error(f"Failed to send fallback callback message: {e2}")
    
    async def send_error_message(self, update: Update, error_message: str, exception: Exception = None):
        """Send error message to user"""
        display_message = error_message
        if exception is not None and hasattr(exception, 'user_message'):
            display_message = exception.user_message
        message = f"❌ *Error:* {display_message}"
        await self.send_message(update, message)
    
    async def send_callback_error(self, query, error_message: str):
        """Send error message as callback response"""
        message = f"❌ *Error:* {error_message}"
        await self.send_callback_message(query, message)
    
    def log_handler_start(self, handler_name: str, update: Update):
        """Log handler execution start"""
        user_id = self.get_user_id(update)
        user_name = self.get_user_name(update)
        log_with_context(
            logger,
            logging.INFO,
            f"{handler_name} started for user {user_id} ({user_name})",
            user_id=user_id,
            operation=handler_name,
        )

    def log_handler_error(self, handler_name: str, update: Update, error: Exception):
        """Log handler execution error"""
        user_id = self.get_user_id(update)
        log_with_context(
            logger,
            logging.ERROR,
            f"{handler_name} failed for user {user_id}: {error}",
            user_id=user_id,
            operation=handler_name,
            error_type=type(error).__name__,
        )

    def log_handler_success(self, handler_name: str, update: Update):
        """Log handler execution success"""
        user_id = self.get_user_id(update)
        log_with_context(
            logger,
            logging.INFO,
            f"{handler_name} completed successfully for user {user_id}",
            user_id=user_id,
            operation=handler_name,
        )
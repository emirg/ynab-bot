import logging
from abc import ABC, abstractmethod
from telegram import Update
from telegram.ext import ContextTypes

from infrastructure.container import DIContainer

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
    
    async def send_message(self, update: Update, message: str, parse_mode: str = 'Markdown'):
        """Send formatted message to user"""
        try:
            if update.callback_query:
                # For callback queries, reply to the original message
                await update.callback_query.message.reply_text(message, parse_mode=parse_mode)
            else:
                # For regular messages
                await update.message.reply_text(message, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            # Fallback without formatting
            try:
                if update.callback_query:
                    await update.callback_query.message.reply_text(message)
                else:
                    await update.message.reply_text(message)
            except Exception as e2:
                logger.error(f"Failed to send fallback message: {e2}")
    
    async def send_callback_message(self, query, message: str, parse_mode: str = 'Markdown'):
        """Send message as reply to callback query"""
        try:
            await query.message.reply_text(message, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Failed to send callback message: {e}")
            # Fallback without formatting
            try:
                await query.message.reply_text(message)
            except Exception as e2:
                logger.error(f"Failed to send fallback callback message: {e2}")
    
    async def send_error_message(self, update: Update, error_message: str):
        """Send error message to user"""
        message = f"❌ *Error:* {error_message}"
        await self.send_message(update, message)
    
    async def send_callback_error(self, query, error_message: str):
        """Send error message as callback response"""
        message = f"❌ *Error:* {error_message}"
        await self.send_callback_message(query, message)
    
    def log_handler_start(self, handler_name: str, update: Update):
        """Log handler execution start"""
        user_id = self.get_user_id(update)
        user_name = self.get_user_name(update)
        logger.info(f"{handler_name} started for user {user_id} ({user_name})")
    
    def log_handler_error(self, handler_name: str, update: Update, error: Exception):
        """Log handler execution error"""
        user_id = self.get_user_id(update)
        logger.error(f"{handler_name} failed for user {user_id}: {error}")
    
    def log_handler_success(self, handler_name: str, update: Update):
        """Log handler execution success"""
        user_id = self.get_user_id(update)
        logger.info(f"{handler_name} completed successfully for user {user_id}")
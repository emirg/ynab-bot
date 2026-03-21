import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Lightweight Telegram notifier that uses the raw HTTP API.
    Designed to be used from synchronous contexts (like the health server thread)
    without needing the full python-telegram-bot async infrastructure.
    """

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(
        self, 
        chat_id: int, 
        text: str, 
        parse_mode: str = 'Markdown', 
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Sends a message via the Telegram Bot API.
        
        Args:
            chat_id: Telegram user ID to send the message to.
            text: Message text.
            parse_mode: Formatting mode (Markdown, HTML, etc.).
            reply_markup: Optional dict representing the inline keyboard.
            
        Returns:
            True if successful, False otherwise.
        """
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        try:
            logger.info(f"Sending Telegram notification to user {chat_id}")
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Telegram API response: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False

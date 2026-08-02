#!/usr/bin/env python3
"""
YNAB Telegram Bot main entrypoint.
Intelligent bot for logging YNAB expenses with AI and speech-to-text.
"""

import sys
import os

from project_bootstrap import ensure_src_path

ensure_src_path()

# Configure structured logging (JSON on Railway, plain text locally).
from infrastructure.logging_config import redact_sensitive_data, setup_logging
setup_logging()

import logging
logger = logging.getLogger(__name__)

# Import the layered architecture.
from infrastructure.container import create_container
from infrastructure.health import start_health_server, set_advisor_page_handler, set_oauth_service, set_on_oauth_success
from infrastructure.telegram_notifier import TelegramNotifier
from presentation.http.handlers.advisor_page_handler import AdvisorPageHandler
from presentation.http.server import configure_http_api
from presentation.telegram.bot import YNABTelegramBot
from presentation.telegram.keyboards import budget_keyboard_to_dict
from presentation.telegram.formatters import GeneralResponseFormatter


def main():
    """Start the bot using the layered architecture."""
    try:
        logger.info("Starting YNAB Telegram Bot with layered architecture...")

        # Start the public health check server.
        port = int(os.environ.get("PORT", 8080))
        start_health_server(port)

        # Create the dependency injection container.
        container = create_container('config/.env')
        config = container.get_config()

        # Expose the HTTP API on the same public server used by Railway.
        configure_http_api(container)
        set_advisor_page_handler(AdvisorPageHandler(container))

        # Attach the OAuth service to the public server when live integrations are enabled.
        if config.use_live_integrations:
            set_oauth_service(container.get_oauth_service())
        else:
            set_oauth_service(None)

        # Configure the Telegram notifier for post-OAuth events.
        notifier = TelegramNotifier(config.telegram_token) if config.telegram_token else None
        
        def on_oauth_success(telegram_user_id: int):
            """Handle the post-OAuth flow after a user connects YNAB successfully."""
            if notifier is None:
                logger.info("Skipping post-OAuth Telegram notification in non-Telegram mode")
                return
            try:
                logger.info("Processing post-OAuth notification for user %s", telegram_user_id)
                
                # Load the budgets available for the user.
                user_config_service = container.get_user_config_service()
                try:
                    budgets = user_config_service.get_available_budgets(telegram_user_id)
                    keyboard = budget_keyboard_to_dict(budgets)
                    message = GeneralResponseFormatter.format_post_oauth_message()
                    
                    # Send the Telegram message with budget buttons.
                    notifier.send_message(
                        chat_id=telegram_user_id,
                        text=message,
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error("Failed to load post-OAuth budgets: %s", e)
                    # Graceful degradation: fall back to a plain Telegram message.
                    fallback_msg = "✅ *¡Cuenta YNAB conectada!* \n\nUsa `/start` para continuar con la configuración de tu presupuesto."
                    notifier.send_message(chat_id=telegram_user_id, text=fallback_msg)
            
            except Exception as e:
                logger.error("Fatal error in on_oauth_success callback: %s", e)

        # Register the callback on the public server.
        set_on_oauth_success(on_oauth_success)

        if config.telegram_enabled:
            # Create and initialize the bot.
            bot = YNABTelegramBot(container)
            bot.run()
        else:
            logger.info(
                "Application started in %s mode with Telegram polling disabled",
                config.app_mode,
            )
            threading_event = os.environ.get("APP_HOLD_OPEN", "1")
            if threading_event != "0":
                import time
                while True:
                    time.sleep(3600)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\nBot stopped by user")
    except Exception as e:
        logger.error("Critical error while starting the bot: %s", e, exc_info=True)
        print(redact_sensitive_data(f"Error starting the bot: {e}"))
        sys.exit(1)


if __name__ == "__main__":
    main()

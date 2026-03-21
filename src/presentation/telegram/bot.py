import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from infrastructure.container import DIContainer
from infrastructure.scheduler import weekly_summary_tick
from presentation.telegram.handlers.general_handler import GeneralHandler
from presentation.telegram.handlers.config_handler import ConfigHandler
from presentation.telegram.handlers.learning_handler import LearningHandler
from presentation.telegram.handlers.expense_handler import ExpenseHandler
from presentation.telegram.handlers.split_config_handler import SplitConfigHandler
from presentation.telegram.handlers.admin_handler import AdminHandler
from presentation.telegram.handlers.summary_handler import SummaryHandler

logger = logging.getLogger(__name__)


class YNABTelegramBot:
    """Main Telegram bot class using layered architecture"""
    
    def __init__(self, container: DIContainer):
        self.container = container
        self.config = container.get_config()
        
        # Initialize handlers
        self.general_handler = GeneralHandler(container)
        self.config_handler = ConfigHandler(container)
        self.learning_handler = LearningHandler(container)
        self.expense_handler = ExpenseHandler(container)
        self.split_config_handler = SplitConfigHandler(container)
        self.admin_handler = AdminHandler(container)
        self.summary_handler = SummaryHandler(container)

        # Initialize Telegram application
        self.application = Application.builder().token(self.config.telegram_token).build()
        self._register_handlers()
        self._register_jobs()

        logger.info("YNAB Telegram Bot initialized with layered architecture")

    def _register_jobs(self):
        """Register periodic job queue tasks."""
        # Store container in bot_data so tick jobs can access DI.
        self.application.bot_data["container"] = self.container

        self.application.job_queue.run_repeating(
            weekly_summary_tick,
            interval=900,
            first=10,
            name="weekly_summary_tick",
        )
        logger.info("Registered job: weekly_summary_tick (interval=900s, first=10s)")
    
    def _register_handlers(self):
        """Register all command and message handlers"""
        
        # General commands
        self.application.add_handler(CommandHandler("start", self.general_handler.handle_start_command))
        self.application.add_handler(CommandHandler("help", self.general_handler.handle_help_command))
        self.application.add_handler(CommandHandler("resumen", self.summary_handler.handle_resumen_command))
        
        # Configuration commands
        self.application.add_handler(CommandHandler("connect", self.config_handler.handle_connect_command))
        self.application.add_handler(CommandHandler("disconnect", self.config_handler.handle_disconnect_command))
        self.application.add_handler(CommandHandler("config", self.config_handler.handle_config_command))
        self.application.add_handler(CommandHandler("budgets", self.config_handler.handle_budgets_command))
        self.application.add_handler(CommandHandler("accounts", self.config_handler.handle_accounts_command))
        self.application.add_handler(CommandHandler("status", self.config_handler.handle_status_command))
        self.application.add_handler(CommandHandler("zona", self.config_handler.zona_command))

        # Split configuration commands
        self.application.add_handler(CommandHandler("splitwise", self.split_config_handler.handle_splitwise_command))
        
        # Learning system commands
        self.application.add_handler(CommandHandler("stats", self.learning_handler.handle_stats_command))
        self.application.add_handler(CommandHandler("recent", self.learning_handler.handle_recent_command))
        self.application.add_handler(CommandHandler("deshacer", self.learning_handler.handle_undo_command))
        self.application.add_handler(CommandHandler("editar", self.learning_handler.handle_edit_command))
        self.application.add_handler(CommandHandler("aprendizaje", self.learning_handler.handle_learning_dashboard_command))
        self.application.add_handler(CommandHandler("olvidar", self.learning_handler.handle_forget_command))

        # Expense flow commands
        self.application.add_handler(CommandHandler("confirmacion", self.expense_handler.handle_confirmacion_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_handler.handle_admin_command))
        self.application.add_handler(CommandHandler("pending", self.admin_handler.handle_pending_users))
        self.application.add_handler(CommandHandler("users", self.admin_handler.handle_all_users))
        self.application.add_handler(CommandHandler("approve", self.admin_handler.handle_approve_user))
        self.application.add_handler(CommandHandler("block", self.admin_handler.handle_block_user))
        
        # Callback query handlers for inline keyboards (pattern filters route to correct handler)
        self.application.add_handler(CallbackQueryHandler(
            self.config_handler.handle_callback_query,
            pattern=r"^(config_|select_)"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.split_config_handler.handle_callback_query,
            pattern=r"^split_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.admin_handler.handle_admin_callback,
            pattern=r"^(approve_|block_)"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.expense_handler.handle_confirmation_callback,
            pattern=r"^(confirm|cancel)_expense$"
        ))
        
        # Message handlers (order matters - more specific first)
        self.application.add_handler(MessageHandler(filters.VOICE, self.expense_handler.handle_voice_message))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.expense_handler.handle_photo_message))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_dispatch))
        
        # Unknown command handler (should be last)
        self.application.add_handler(MessageHandler(filters.COMMAND, self.general_handler.handle_unknown_command))
        
        logger.info("All Telegram handlers registered successfully")
    
    async def handle_text_dispatch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Dispatch text messages to either split config (if pending alias) or expense handler"""
        if context.user_data.get("pending_alias_category_id"):
            await self.split_config_handler.handle_alias_text_message(update, context)
        else:
            await self.expense_handler.handle_text_message(update, context)

    async def post_init(self):
        """Post-initialization tasks"""
        try:
            # Test basic services
            bot_info = await self.application.bot.get_me()
            logger.info(f"Bot initialized: @{bot_info.username} ({bot_info.first_name})")
            
            # Test configuration
            logger.info(f"Configuration loaded: {self.config.database_path}")
            
        except Exception as e:
            logger.error(f"Post-initialization failed: {e}")
            raise
    
    def run(self):
        """Run the bot"""
        try:
            logger.info("Starting YNAB Telegram Bot...")
            
            # Start the bot (run_polling manages its own event loop)
            self.application.run_polling(
                allowed_updates=['message', 'callback_query'],
                drop_pending_updates=True
            )
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            raise
        finally:
            logger.info("Bot shutdown complete")
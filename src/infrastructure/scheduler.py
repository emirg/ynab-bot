"""Scheduler tick functions for periodic bot tasks."""

import logging

from telegram.ext import ContextTypes

from application.services.weekly_summary_service import WeeklySummaryService
from domain.models.user import UserStatus
from presentation.telegram.formatters import WeeklySummaryFormatter

logger = logging.getLogger(__name__)


async def weekly_summary_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic tick (every 15 minutes) that sends weekly summaries to eligible users.

    Retrieves the DI container from ``context.bot_data["container"]``, iterates
    over all authorized users, and sends the weekly spending summary to those
    whose ``should_send_summary`` check passes.

    Each user is processed inside its own try/except so that a failure for one
    user never blocks the others.  The entire function is also wrapped in a
    top-level try/except so that any unexpected error is logged and swallowed —
    the job must never crash the bot.
    """
    try:
        container = context.bot_data["container"]
        user_repository = container.get_user_repository()
        service: WeeklySummaryService = container.get_weekly_summary_service()

        users = user_repository.find_by_status(UserStatus.AUTHORIZED)

        total = len(users)
        successes = 0
        failures = 0

        logger.info("weekly_summary_tick: processing %d authorized user(s)", total)

        for user in users:
            try:
                if not service.should_send_summary(user):
                    continue

                summary = service.generate_summary(user)
                message = WeeklySummaryFormatter.format_summary(summary)

                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode="Markdown",
                )

                service.mark_summary_sent(user)
                successes += 1
                logger.info(
                    "weekly_summary_tick: summary sent to user %d", user.telegram_id
                )

            except Exception as exc:  # noqa: BLE001
                failures += 1
                logger.error(
                    "weekly_summary_tick: failed for user %d: %s",
                    user.telegram_id,
                    exc,
                    exc_info=True,
                )

        logger.info(
            "weekly_summary_tick: finished — total=%d successes=%d failures=%d",
            total,
            successes,
            failures,
        )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "weekly_summary_tick: unexpected top-level error: %s", exc, exc_info=True
        )

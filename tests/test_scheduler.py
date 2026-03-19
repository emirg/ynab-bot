"""Tests for src/infrastructure/scheduler.py — weekly_summary_tick."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from domain.models.user import UserConfiguration, UserStatus
from infrastructure.scheduler import weekly_summary_tick


@pytest.fixture
def anyio_backend():
    return 'asyncio'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(telegram_id: int, status: UserStatus = UserStatus.AUTHORIZED) -> UserConfiguration:
    """Return a minimal UserConfiguration for testing."""
    return UserConfiguration(
        telegram_id=telegram_id,
        status=status,
        budget_id="budget-123",
        default_account_id="account-456",
        ynab_access_token="tok",
    )


def _make_context(users, should_send_map=None, raise_for=None):
    """Build a mock PTB context with a container attached to bot_data.

    Args:
        users: list of UserConfiguration objects returned by find_by_status.
        should_send_map: dict mapping telegram_id -> bool for should_send_summary.
                         Defaults to True for all users.
        raise_for: optional telegram_id for which generate_summary should raise.
    """
    if should_send_map is None:
        should_send_map = {u.telegram_id: True for u in users}

    # --- service mock ---
    service = MagicMock()
    service.should_send_summary.side_effect = lambda u: should_send_map.get(u.telegram_id, True)
    service.generate_summary.side_effect = (
        lambda u: (__ for __ in ()).throw(RuntimeError("boom"))
        if (raise_for and u.telegram_id == raise_for)
        else MagicMock(name="summary")
    )
    service.mark_summary_sent = MagicMock()

    # --- user repository mock ---
    user_repo = MagicMock()
    user_repo.find_by_status.return_value = users

    # --- container mock ---
    container = MagicMock()
    container.get_user_repository.return_value = user_repo
    container.get_weekly_summary_service.return_value = service

    # --- bot mock ---
    bot = AsyncMock()

    # --- context mock ---
    context = MagicMock()
    context.bot_data = {"container": container}
    context.bot = bot

    return context, service, bot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWeeklySummaryTick:

    @pytest.mark.anyio
    async def test_sends_message_to_eligible_user(self):
        """Eligible user receives a message and mark_summary_sent is called."""
        user = _make_user(telegram_id=111)
        context, service, bot = _make_context([user])

        with patch(
            "infrastructure.scheduler.WeeklySummaryFormatter.format_summary",
            return_value="formatted message",
        ):
            await weekly_summary_tick(context)

        bot.send_message.assert_awaited_once_with(
            chat_id=111,
            text="formatted message",
            parse_mode="Markdown",
        )
        service.mark_summary_sent.assert_called_once_with(user)

    @pytest.mark.anyio
    async def test_skips_user_when_should_send_false(self):
        """User with should_send_summary=False receives no message."""
        user = _make_user(telegram_id=222)
        context, service, bot = _make_context([user], should_send_map={222: False})

        await weekly_summary_tick(context)

        bot.send_message.assert_not_awaited()
        service.mark_summary_sent.assert_not_called()

    @pytest.mark.anyio
    async def test_processes_multiple_users_independently(self):
        """Both eligible and ineligible users among a list are handled correctly."""
        u1 = _make_user(101)
        u2 = _make_user(102)
        u3 = _make_user(103)
        context, service, bot = _make_context(
            [u1, u2, u3],
            should_send_map={101: True, 102: False, 103: True},
        )

        with patch(
            "infrastructure.scheduler.WeeklySummaryFormatter.format_summary",
            return_value="msg",
        ):
            await weekly_summary_tick(context)

        assert bot.send_message.await_count == 2
        sent_ids = {c.kwargs["chat_id"] for c in bot.send_message.await_args_list}
        assert sent_ids == {101, 103}

        assert service.mark_summary_sent.call_count == 2

    @pytest.mark.anyio
    async def test_one_user_error_does_not_block_others(self):
        """An error for user A must not prevent user B from receiving their summary."""
        u1 = _make_user(201)
        u2 = _make_user(202)
        context, service, bot = _make_context([u1, u2], raise_for=201)

        with patch(
            "infrastructure.scheduler.WeeklySummaryFormatter.format_summary",
            return_value="msg",
        ):
            await weekly_summary_tick(context)

        # u1 failed, u2 should still be processed
        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.kwargs["chat_id"] == 202
        # mark_summary_sent only called for the successful user
        service.mark_summary_sent.assert_called_once_with(u2)

    @pytest.mark.anyio
    async def test_mark_summary_sent_not_called_on_failure(self):
        """mark_summary_sent must NOT be called when generate_summary raises."""
        user = _make_user(301)
        context, service, bot = _make_context([user], raise_for=301)

        await weekly_summary_tick(context)

        service.mark_summary_sent.assert_not_called()

    @pytest.mark.anyio
    async def test_top_level_exception_is_swallowed(self):
        """A top-level error (e.g. broken container) must not propagate."""
        context = MagicMock()
        context.bot_data = {}  # Missing "container" key → KeyError

        # Should not raise
        await weekly_summary_tick(context)

    @pytest.mark.anyio
    async def test_no_users_runs_without_error(self):
        """An empty user list produces no messages and no errors."""
        context, service, bot = _make_context([])

        await weekly_summary_tick(context)

        bot.send_message.assert_not_awaited()
        service.mark_summary_sent.assert_not_called()

    @pytest.mark.anyio
    async def test_find_by_status_called_with_authorized(self):
        """find_by_status must be called with UserStatus.AUTHORIZED."""
        context, service, bot = _make_context([])

        await weekly_summary_tick(context)

        container = context.bot_data["container"]
        user_repo = container.get_user_repository()
        user_repo.find_by_status.assert_called_once_with(UserStatus.AUTHORIZED)

    @pytest.mark.anyio
    async def test_send_message_error_does_not_call_mark_sent(self):
        """If bot.send_message raises, mark_summary_sent must NOT be called."""
        user = _make_user(401)
        context, service, bot = _make_context([user])
        bot.send_message.side_effect = Exception("Telegram API error")

        with patch(
            "infrastructure.scheduler.WeeklySummaryFormatter.format_summary",
            return_value="msg",
        ):
            await weekly_summary_tick(context)

        service.mark_summary_sent.assert_not_called()

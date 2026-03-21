"""Tests for src/presentation/telegram/bot.py — YNABTelegramBot initialization."""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.scheduler import weekly_summary_tick


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_container():
    """Return a minimal DIContainer mock with the attributes bot.py accesses."""
    config = MagicMock()
    config.telegram_token = "fake-token"
    config.database_path = "/tmp/test.db"

    container = MagicMock()
    container.get_config.return_value = config
    return container


def _make_bot(container):
    """Construct a YNABTelegramBot with all PTB I/O mocked out.

    We patch:
    - ``Application.builder`` so no real HTTP client is created.
    - All handler classes so their constructors don't touch the DB/YNAB.
    """
    job_queue = MagicMock()

    app = MagicMock()
    app.job_queue = job_queue
    app.bot_data = {}

    builder = MagicMock()
    builder.token.return_value = builder
    builder.build.return_value = app

    patches = [
        patch("presentation.telegram.bot.Application.builder", return_value=builder),
        patch("presentation.telegram.bot.GeneralHandler"),
        patch("presentation.telegram.bot.ConfigHandler"),
        patch("presentation.telegram.bot.LearningHandler"),
        patch("presentation.telegram.bot.ExpenseHandler"),
        patch("presentation.telegram.bot.SplitConfigHandler"),
        patch("presentation.telegram.bot.AdminHandler"),
    ]

    # Start all patches and track them so we can stop them after the test.
    started = [p.start() for p in patches]

    from presentation.telegram.bot import YNABTelegramBot
    bot = YNABTelegramBot(container)

    # Attach patches for cleanup in the fixture
    bot._test_patches = patches
    bot._test_started = started
    return bot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def container():
    return _make_container()


@pytest.fixture
def bot(container):
    b = _make_bot(container)
    yield b
    for p in b._test_patches:
        p.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBotJobRegistration:

    def test_container_stored_in_bot_data(self, bot, container):
        """Container must be stored under bot_data['container'] for tick jobs."""
        assert bot.application.bot_data["container"] is container

    def test_weekly_summary_tick_job_registered(self, bot):
        """A job named 'weekly_summary_tick' must be registered on the job queue."""
        job_queue = bot.application.job_queue
        job_queue.run_repeating.assert_called_once()

        call_kwargs = job_queue.run_repeating.call_args
        # First positional argument is the callback function
        callback = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("callback")
        assert callback is weekly_summary_tick

    def test_weekly_summary_tick_interval_is_900(self, bot):
        """Job must be scheduled with a 900-second (15-minute) interval."""
        call_kwargs = bot.application.job_queue.run_repeating.call_args
        interval = call_kwargs.kwargs.get("interval") or call_kwargs.args[1]
        assert interval == 900

    def test_weekly_summary_tick_first_delay_is_10(self, bot):
        """Job must have a 10-second startup delay (first=10)."""
        call_kwargs = bot.application.job_queue.run_repeating.call_args
        first = call_kwargs.kwargs.get("first")
        assert first == 10

    def test_weekly_summary_tick_job_name(self, bot):
        """Job must be registered with the name 'weekly_summary_tick'."""
        call_kwargs = bot.application.job_queue.run_repeating.call_args
        name = call_kwargs.kwargs.get("name")
        assert name == "weekly_summary_tick"

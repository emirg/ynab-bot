"""Tests for WeeklySummaryService."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from application.services.weekly_summary_service import WeeklySummaryService, _monday_of_week
from domain.models.user import UserConfiguration, UserStatus
from domain.models.weekly_summary import WeeklySummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(
    *,
    status: UserStatus = UserStatus.AUTHORIZED,
    budget_id: str = "budget-1",
    account_id: str = "acct-1",
    ynab_access_token: str = "token-123",
    timezone: str = "UTC",
    last_weekly_summary_sent: datetime = None,
) -> UserConfiguration:
    user = UserConfiguration(telegram_id=12345)
    user.status = status
    user.budget_id = budget_id
    user.default_account_id = account_id
    user.ynab_access_token = ynab_access_token
    user.timezone = timezone
    user.last_weekly_summary_sent = last_weekly_summary_sent
    return user


def _make_txn(amount: int, category_name: str, txn_date: str) -> dict:
    return {"amount": amount, "category_name": category_name, "date": txn_date, "deleted": False}


def _make_service(transactions=None):
    """Return a WeeklySummaryService with mocked dependencies."""
    mock_factory = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_transactions.return_value = transactions or []
    mock_factory.get_repository.return_value = mock_repo

    mock_user_repo = MagicMock()

    service = WeeklySummaryService(ynab_factory=mock_factory, user_repository=mock_user_repo)
    return service, mock_repo, mock_user_repo


# ---------------------------------------------------------------------------
# _monday_of_week helper
# ---------------------------------------------------------------------------

class TestMondayOfWeek:
    def test_monday_returns_itself(self):
        d = date(2026, 3, 16)  # a Monday
        assert _monday_of_week(d) == d

    def test_sunday_returns_preceding_monday(self):
        d = date(2026, 3, 22)  # Sunday
        assert _monday_of_week(d) == date(2026, 3, 16)

    def test_wednesday_returns_monday(self):
        d = date(2026, 3, 18)  # Wednesday
        assert _monday_of_week(d) == date(2026, 3, 16)


# ---------------------------------------------------------------------------
# generate_summary — date range computation
# ---------------------------------------------------------------------------

class TestGenerateSummaryGuards:
    """Verify input validation in generate_summary."""

    def test_raises_value_error_when_budget_id_is_none(self):
        service, _, _ = _make_service()
        user = _make_user(budget_id=None)
        with pytest.raises(ValueError, match="budget_id is required"):
            service.generate_summary(user)


class TestGenerateSummaryDateRange:
    """Verify correct date ranges are sent to the YNAB API."""

    def _run_on_date(self, today_str: str, tz: str = "UTC"):
        """Invoke generate_summary with today patched to *today_str*."""
        service, mock_repo, _ = _make_service(transactions=[])
        user = _make_user(timezone=tz)

        with patch("application.services.weekly_summary_service.user_today", return_value=date.fromisoformat(today_str)):
            summary = service.generate_summary(user)

        return summary, mock_repo

    def test_since_date_is_two_mondays_ago(self):
        # today = 2026-03-19 (Thursday). This Monday = 2026-03-16.
        # two_mondays_ago = 2026-03-02
        summary, mock_repo = self._run_on_date("2026-03-19")
        mock_repo.get_transactions.assert_called_once_with("budget-1", "2026-03-02")

    def test_current_week_is_previous_mon_to_sun(self):
        # today = 2026-03-19 (Thu). prev_monday = 2026-03-09, prev_sunday = 2026-03-15
        summary, _ = self._run_on_date("2026-03-19")
        assert summary.week_start == date(2026, 3, 9)
        assert summary.week_end == date(2026, 3, 15)

    def test_monday_boundary(self):
        # today = 2026-03-16 (Monday). This Monday = 2026-03-16.
        # prev_monday = 2026-03-09, two_mondays_ago = 2026-03-02
        summary, mock_repo = self._run_on_date("2026-03-16")
        mock_repo.get_transactions.assert_called_once_with("budget-1", "2026-03-02")
        assert summary.week_start == date(2026, 3, 9)
        assert summary.week_end == date(2026, 3, 15)


# ---------------------------------------------------------------------------
# generate_summary — transaction splitting & filtering
# ---------------------------------------------------------------------------

class TestGenerateSummaryTransactions:
    """Verify that transactions are split into correct week buckets and expenses filtered."""

    def _run_with_txns(self, transactions, today_str="2026-03-19"):
        service, mock_repo, _ = _make_service(transactions=transactions)
        mock_repo.get_transactions.return_value = transactions
        user = _make_user()

        with patch("application.services.weekly_summary_service.user_today", return_value=date.fromisoformat(today_str)):
            return service.generate_summary(user)

    def test_empty_transactions_returns_no_transactions(self):
        summary = self._run_with_txns([])
        assert not summary.has_transactions
        assert summary.total_spent == 0

    def test_expenses_in_previous_week_counted(self):
        # today=2026-03-19, prev_monday=2026-03-09, prev_sunday=2026-03-15
        txns = [
            _make_txn(-50_000, "Supermercado", "2026-03-10"),
            _make_txn(-30_000, "Transporte", "2026-03-12"),
        ]
        summary = self._run_with_txns(txns)
        assert summary.has_transactions
        assert summary.total_spent == 80_000

    def test_income_transactions_ignored(self):
        # Positive amounts are income, should not be counted
        txns = [
            _make_txn(100_000, "Sueldo", "2026-03-10"),   # income
            _make_txn(-20_000, "Cafe", "2026-03-11"),      # expense
        ]
        summary = self._run_with_txns(txns)
        assert summary.total_spent == 20_000

    def test_transactions_outside_window_not_counted(self):
        # today=2026-03-19, prev window=2026-03-09..2026-03-15
        txns = [
            _make_txn(-100_000, "Antiguo", "2026-03-01"),   # too old (two-week-ago window)
            _make_txn(-50_000, "Futuro", "2026-03-18"),      # current week (incomplete)
            _make_txn(-25_000, "Correcto", "2026-03-10"),    # in prev_week window
        ]
        summary = self._run_with_txns(txns)
        assert summary.total_spent == 25_000

    def test_previous_week_comparison_populated(self):
        # today=2026-03-19
        # two_mondays_ago window: 2026-03-02..2026-03-08
        # prev week window:       2026-03-09..2026-03-15
        txns = [
            _make_txn(-40_000, "Almuerzo", "2026-03-03"),   # two weeks ago
            _make_txn(-60_000, "Cena", "2026-03-10"),       # previous week
        ]
        summary = self._run_with_txns(txns)
        assert summary.total_spent == 60_000
        assert summary.previous_week_total == 40_000

    def test_top_categories_max_three(self):
        txns = [
            _make_txn(-10_000, "Cat A", "2026-03-09"),
            _make_txn(-20_000, "Cat B", "2026-03-10"),
            _make_txn(-30_000, "Cat C", "2026-03-11"),
            _make_txn(-40_000, "Cat D", "2026-03-12"),
        ]
        summary = self._run_with_txns(txns)
        assert len(summary.top_categories) == 3
        assert summary.top_categories[0].category_name == "Cat D"

    def test_percentage_change_computed(self):
        txns = [
            _make_txn(-100_000, "A", "2026-03-03"),  # two weeks ago: 100k
            _make_txn(-150_000, "A", "2026-03-10"),  # prev week:     150k  → +50%
        ]
        summary = self._run_with_txns(txns)
        assert summary.percentage_change == pytest.approx(50.0)

    def test_no_previous_week_percentage_change_is_none(self):
        txns = [_make_txn(-50_000, "A", "2026-03-10")]
        summary = self._run_with_txns(txns)
        assert summary.percentage_change is None


# ---------------------------------------------------------------------------
# should_send_summary
# ---------------------------------------------------------------------------

class TestShouldSendSummary:
    """Unit-test the gating logic without touching YNAB."""

    _MONDAY_8AM = datetime(2026, 3, 16, 8, 5, tzinfo=timezone.utc)  # Monday 08:05 UTC

    def _check(self, user, now_dt=None):
        service, _, _ = _make_service()
        if now_dt is None:
            now_dt = self._MONDAY_8AM
        with patch("application.services.weekly_summary_service.user_now", return_value=now_dt):
            return service.should_send_summary(user)

    def test_returns_true_on_monday_8am_configured(self):
        user = _make_user()
        assert self._check(user) is True

    def test_false_if_not_authorized(self):
        user = _make_user(status=UserStatus.PENDING)
        assert self._check(user) is False

    def test_false_if_not_configured_no_budget(self):
        user = _make_user(budget_id=None)
        assert self._check(user) is False

    def test_false_if_not_configured_no_account(self):
        user = _make_user(account_id=None)
        assert self._check(user) is False

    def test_false_if_no_ynab_token(self):
        user = _make_user(ynab_access_token=None)
        assert self._check(user) is False

    def test_false_if_not_monday(self):
        user = _make_user()
        tuesday = datetime(2026, 3, 17, 8, 5, tzinfo=timezone.utc)
        assert self._check(user, now_dt=tuesday) is False

    def test_false_if_monday_but_wrong_hour(self):
        user = _make_user()
        monday_9am = datetime(2026, 3, 16, 9, 0, tzinfo=timezone.utc)
        assert self._check(user, now_dt=monday_9am) is False

    def test_false_if_monday_but_too_early(self):
        user = _make_user()
        monday_7am = datetime(2026, 3, 16, 7, 59, tzinfo=timezone.utc)
        assert self._check(user, now_dt=monday_7am) is False

    def test_false_if_monday_8_15(self):
        # Minute 15 is outside the 0–14 window
        user = _make_user()
        monday_8_15 = datetime(2026, 3, 16, 8, 15, tzinfo=timezone.utc)
        assert self._check(user, now_dt=monday_8_15) is False

    def test_true_on_minute_boundary_8_00(self):
        user = _make_user()
        monday_8_00 = datetime(2026, 3, 16, 8, 0, tzinfo=timezone.utc)
        assert self._check(user, now_dt=monday_8_00) is True

    def test_true_on_minute_boundary_8_14(self):
        user = _make_user()
        monday_8_14 = datetime(2026, 3, 16, 8, 14, tzinfo=timezone.utc)
        assert self._check(user, now_dt=monday_8_14) is True

    def test_false_if_already_sent_within_6_days(self):
        # Sent 2 days ago — should not resend
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        user = _make_user(last_weekly_summary_sent=two_days_ago)
        assert self._check(user) is False

    def test_true_if_sent_more_than_6_days_ago(self):
        # Sent 7 days ago — OK to resend
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        user = _make_user(last_weekly_summary_sent=seven_days_ago)
        assert self._check(user) is True

    def test_true_if_never_sent(self):
        user = _make_user(last_weekly_summary_sent=None)
        assert self._check(user) is True

    def test_dedup_boundary_exactly_6_days(self):
        # Exactly 6 days ago: elapsed.days == 6 → NOT < 6 → should pass? No — "< 6 days" means
        # 5 days or fewer is blocked. Exactly 6 days → elapsed.days == 6 → NOT < 6 → return True.
        exactly_6_days_ago = datetime.now(timezone.utc) - timedelta(days=6)
        user = _make_user(last_weekly_summary_sent=exactly_6_days_ago)
        assert self._check(user) is True


# ---------------------------------------------------------------------------
# mark_summary_sent
# ---------------------------------------------------------------------------

class TestMarkSummarySent:
    def test_calls_mark_and_saves(self):
        service, _, mock_user_repo = _make_service()
        user = _make_user()
        assert user.last_weekly_summary_sent is None

        service.mark_summary_sent(user)

        assert user.last_weekly_summary_sent is not None
        mock_user_repo.save.assert_called_once_with(user)

    def test_updated_at_also_refreshed(self):
        service, _, _ = _make_service()
        user = _make_user()
        old_updated_at = user.updated_at

        service.mark_summary_sent(user)

        # updated_at should be >= old_updated_at
        assert user.updated_at >= old_updated_at


# ---------------------------------------------------------------------------
# Timezone boundary: user in UTC-3 when server is UTC
# ---------------------------------------------------------------------------

class TestTimezoneBoundary:
    """Verify that generate_summary uses the user's timezone for date computation."""

    def test_bogota_timezone_uses_local_date(self):
        """A user in Bogota (UTC-5) on Monday 00:00 local = Monday 05:00 UTC.
        The date computation should use the user's local date (Sunday), not the server's."""
        # We patch user_today to return the local Sunday date
        service, mock_repo, _ = _make_service(transactions=[])
        mock_repo.get_transactions.return_value = []
        user = _make_user(timezone="America/Bogota")

        local_sunday = date(2026, 3, 15)  # a Sunday
        with patch("application.services.weekly_summary_service.user_today", return_value=local_sunday) as mock_today:
            summary = service.generate_summary(user)
            mock_today.assert_called_once_with("America/Bogota")

        # today=Sunday 2026-03-15 → this_monday=2026-03-09 → prev_monday=2026-03-02
        assert summary.week_start == date(2026, 3, 2)
        assert summary.week_end == date(2026, 3, 8)

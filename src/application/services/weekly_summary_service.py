import logging
from datetime import date, timedelta, timezone, datetime

from domain.models.user import UserConfiguration
from domain.models.weekly_summary import WeeklySummary
from domain.repositories.user_repository import UserRepository
from domain.time_utils import user_now, user_today
from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory

logger = logging.getLogger(__name__)

_SUMMARY_WINDOW_MINUTES = 14  # 08:00 – 08:14 window
_DEDUP_DAYS = 6               # Prevent re-sending within 6 days


def _monday_of_week(d: date) -> date:
    """Return the Monday of the ISO week containing *d*."""
    return d - timedelta(days=d.weekday())


class WeeklySummaryService:
    """Computes and gates the weekly spending summary for a user."""

    def __init__(
        self,
        ynab_factory: YNABRepositoryFactory,
        user_repository: UserRepository,
    ):
        self.ynab_factory = ynab_factory
        self.user_repository = user_repository

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_summary(self, user_config: UserConfiguration) -> WeeklySummary:
        """Fetch YNAB transactions and build a WeeklySummary for the previous week.

        Date ranges (in the user's local timezone):
          - current_week : last Monday → last Sunday  (the week that just ended)
          - previous_week: the Monday before that → the Sunday before that
        """
        if not user_config.budget_id:
            raise ValueError("budget_id is required to generate a weekly summary")

        today = user_today(user_config.timezone)

        # This Monday (start of current, incomplete week)
        this_monday = _monday_of_week(today)

        # Previous week: Mon → Sun
        prev_monday = this_monday - timedelta(weeks=1)
        prev_sunday = prev_monday + timedelta(days=6)

        # Two weeks ago: Mon → Sun
        two_mondays_ago = this_monday - timedelta(weeks=2)
        two_sundays_ago = two_mondays_ago + timedelta(days=6)

        # Fetch all transactions from two_mondays_ago onwards in one API call
        since_date = two_mondays_ago.isoformat()
        ynab_repo = self.ynab_factory.get_repository(user_config)
        all_transactions = ynab_repo.get_transactions(user_config.budget_id, since_date)

        # Split into the two week buckets by transaction date string (YYYY-MM-DD)
        current_week_txns = [
            t for t in all_transactions
            if prev_monday.isoformat() <= t.get("date", "") <= prev_sunday.isoformat()
        ]
        previous_week_txns = [
            t for t in all_transactions
            if two_mondays_ago.isoformat() <= t.get("date", "") <= two_sundays_ago.isoformat()
        ]

        return WeeklySummary.from_transactions(
            current_week_txns=current_week_txns,
            previous_week_txns=previous_week_txns,
            week_start=prev_monday,
            week_end=prev_sunday,
        )

    def should_send_summary(self, user_config: UserConfiguration) -> bool:
        """Return True when all conditions are met to dispatch the weekly summary.

        Conditions (all must be true):
        1. User is authorized.
        2. User has budget_id configured (account_id also checked via is_configured).
        3. User has a YNAB access token.
        4. User's local time is Monday between 08:00 and 08:14 (inclusive).
        5. last_weekly_summary_sent is None or more than 6 days ago (deduplication).
        """
        # 1. Authorization
        if not user_config.is_authorized():
            return False

        # 2. Budget + account configured
        if not user_config.is_configured():
            return False

        # 3. YNAB token present
        if not user_config.has_ynab_token():
            return False

        # 4. User's local time: Monday 08:00–08:14
        now_local = user_now(user_config.timezone)
        if now_local.weekday() != 0:           # 0 = Monday
            return False
        if not (now_local.hour == 8 and 0 <= now_local.minute <= _SUMMARY_WINDOW_MINUTES):
            return False

        # 5. Deduplication: not sent within the last 6 days
        if user_config.last_weekly_summary_sent is not None:
            last_sent = user_config.last_weekly_summary_sent
            # Ensure tz-aware comparison
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            elapsed = datetime.now(timezone.utc) - last_sent
            if elapsed.days < _DEDUP_DAYS:
                return False

        return True

    def mark_summary_sent(self, user_config: UserConfiguration) -> None:
        """Record that the summary was sent and persist via user_repository."""
        user_config.mark_weekly_summary_sent()
        self.user_repository.save(user_config)

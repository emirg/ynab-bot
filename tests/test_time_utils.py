"""Tests for domain.time_utils — central timezone helper."""

from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

from domain.time_utils import user_now, user_today, DEFAULT_TIMEZONE


class TestUserNow:

    def test_user_now_returns_aware_datetime(self):
        result = user_now()
        assert result.tzinfo is not None

    def test_user_now_default_timezone(self):
        result = user_now()
        assert str(result.tzinfo) == DEFAULT_TIMEZONE

    def test_user_now_custom_timezone(self):
        result = user_now("UTC")
        assert str(result.tzinfo) == "UTC"

    def test_user_now_invalid_timezone_falls_back(self):
        result = user_now("Invalid/Zone")
        assert str(result.tzinfo) == DEFAULT_TIMEZONE

    def test_user_now_utc_minus_3_difference(self):
        """Argentina (UTC-3) and UTC differ by exactly 3 hours."""
        utc_now = user_now("UTC")
        arg_now = user_now(DEFAULT_TIMEZONE)
        # Convert both to UTC for comparison
        utc_ts = utc_now.astimezone(ZoneInfo("UTC"))
        arg_ts = arg_now.astimezone(ZoneInfo("UTC"))
        # They should be within a few seconds of each other (same instant)
        diff = abs((utc_ts - arg_ts).total_seconds())
        assert diff < 2  # less than 2 seconds apart
        # But their naive hours should differ by 3 (modulo DST)
        offset_hours = arg_now.utcoffset().total_seconds() / 3600
        assert offset_hours == -3


class TestUserToday:

    def test_user_today_returns_date(self):
        result = user_today()
        assert isinstance(result, date)
        assert not isinstance(result, datetime)

    def test_user_today_default_timezone(self):
        """Should return a date, and be consistent with user_now."""
        result = user_today()
        now_date = user_now().date()
        assert result == now_date

    def test_user_today_custom_timezone(self):
        result = user_today("UTC")
        assert isinstance(result, date)

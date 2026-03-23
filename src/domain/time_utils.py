"""Central timezone helper for user-facing date/time operations.

All user-facing date logic should use these functions instead of
datetime.now() or date.today() to ensure correct timezone handling
when the server runs in UTC.

Internal bookkeeping timestamps (created_at, updated_at, etc.) should
remain in UTC and NOT use these helpers.
"""

import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "America/Bogota"


def user_now(timezone_str: str = DEFAULT_TIMEZONE) -> datetime:
    """Return the current timezone-aware datetime for the given IANA timezone.

    Falls back to DEFAULT_TIMEZONE if *timezone_str* is invalid.
    """
    try:
        tz = ZoneInfo(timezone_str)
    except (KeyError, Exception):
        logger.warning(
            "Zona horaria invalida '%s', usando default '%s'",
            timezone_str,
            DEFAULT_TIMEZONE,
        )
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz=tz)


def user_today(timezone_str: str = DEFAULT_TIMEZONE) -> date:
    """Return today's date in the given IANA timezone."""
    return user_now(timezone_str).date()

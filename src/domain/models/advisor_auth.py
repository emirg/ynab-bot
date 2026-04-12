from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AdvisorLaunchToken:
    telegram_id: int
    token_hash: str
    expires_at: datetime
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class AdvisorSession:
    telegram_id: int
    token_hash: str
    expires_at: datetime
    created_at: datetime = field(default_factory=_utc_now)

    @classmethod
    def with_ttl(cls, telegram_id: int, token_hash: str, ttl_seconds: int) -> "AdvisorSession":
        now = _utc_now()
        return cls(
            telegram_id=telegram_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

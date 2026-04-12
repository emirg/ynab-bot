from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from domain.exceptions import YNABBotException
from domain.models.user import UserConfiguration, UserStatus
from domain.repositories.user_repository import UserRepository
from domain.time_utils import DEFAULT_TIMEZONE
from infrastructure.token_encryption import TokenEncryptor

logger = logging.getLogger(__name__)


class PostgresUserRepository(UserRepository):
    """PostgreSQL implementation of UserRepository."""

    def __init__(self, db_manager, token_encryptor: Optional[TokenEncryptor] = None):
        self._db = db_manager
        self._encryptor = token_encryptor

    def _row_to_user_config(self, row: dict) -> UserConfiguration:
        access_token = row.get("ynab_access_token")
        refresh_token = row.get("ynab_refresh_token")
        if self._encryptor:
            access_token = self._encryptor.decrypt(access_token)
            refresh_token = self._encryptor.decrypt(refresh_token)

        return UserConfiguration(
            telegram_id=row["telegram_id"],
            status=UserStatus(row["status"]) if row.get("status") else UserStatus.PENDING,
            budget_id=row.get("budget_id"),
            default_account_id=row.get("default_account_id"),
            default_account_name=row.get("default_account_name"),
            username=row.get("username"),
            first_name=row.get("first_name"),
            last_name=row.get("last_name"),
            timezone=row.get("timezone") or DEFAULT_TIMEZONE,
            created_at=row.get("created_at") or datetime.now(timezone.utc),
            updated_at=row.get("updated_at") or datetime.now(timezone.utc),
            approved_at=row.get("approved_at"),
            approved_by=row.get("approved_by"),
            ynab_access_token=access_token,
            ynab_refresh_token=refresh_token,
            ynab_token_expires_at=row.get("ynab_token_expires_at"),
            last_weekly_summary_sent=row.get("last_weekly_summary_sent"),
            confirm_before_create=bool(row.get("confirm_before_create")),
        )

    def find_by_telegram_id(self, telegram_id: int) -> Optional[UserConfiguration]:
        try:
            conn = self._db.get_connection()
            row = conn.execute(
                "SELECT * FROM user_configurations WHERE telegram_id = %s",
                (telegram_id,),
            ).fetchone()
            return self._row_to_user_config(row) if row else None
        except Exception as exc:
            logger.error("Database error finding user %s: %s", telegram_id, exc)
            raise YNABBotException(f"Database error: {exc}") from exc

    def save(self, user_config: UserConfiguration) -> UserConfiguration:
        try:
            user_config.updated_at = datetime.now(timezone.utc)

            access_token = user_config.ynab_access_token
            refresh_token = user_config.ynab_refresh_token
            if self._encryptor:
                access_token = self._encryptor.encrypt(access_token)
                refresh_token = self._encryptor.encrypt(refresh_token)

            conn = self._db.get_connection()
            conn.execute(
                """
                INSERT INTO user_configurations
                    (telegram_id, status, budget_id, default_account_id, default_account_name,
                     username, first_name, last_name, timezone, created_at, updated_at, approved_at, approved_by,
                     ynab_access_token, ynab_refresh_token, ynab_token_expires_at,
                     last_weekly_summary_sent, confirm_before_create)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    budget_id = EXCLUDED.budget_id,
                    default_account_id = EXCLUDED.default_account_id,
                    default_account_name = EXCLUDED.default_account_name,
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    timezone = EXCLUDED.timezone,
                    updated_at = EXCLUDED.updated_at,
                    approved_at = EXCLUDED.approved_at,
                    approved_by = EXCLUDED.approved_by,
                    ynab_access_token = EXCLUDED.ynab_access_token,
                    ynab_refresh_token = EXCLUDED.ynab_refresh_token,
                    ynab_token_expires_at = EXCLUDED.ynab_token_expires_at,
                    last_weekly_summary_sent = EXCLUDED.last_weekly_summary_sent,
                    confirm_before_create = EXCLUDED.confirm_before_create
                """,
                (
                    user_config.telegram_id,
                    user_config.status.value,
                    user_config.budget_id,
                    user_config.default_account_id,
                    user_config.default_account_name,
                    user_config.username,
                    user_config.first_name,
                    user_config.last_name,
                    user_config.timezone,
                    user_config.created_at,
                    user_config.updated_at,
                    user_config.approved_at,
                    user_config.approved_by,
                    access_token,
                    refresh_token,
                    user_config.ynab_token_expires_at,
                    user_config.last_weekly_summary_sent,
                    user_config.confirm_before_create,
                ),
            )
            conn.commit()
            return user_config
        except Exception as exc:
            logger.error("Database error saving user configuration: %s", exc)
            raise YNABBotException(f"Failed to save user configuration: {exc}") from exc

    def delete(self, telegram_id: int) -> bool:
        try:
            conn = self._db.get_connection()
            cursor = conn.execute(
                "DELETE FROM user_configurations WHERE telegram_id = %s",
                (telegram_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as exc:
            logger.error("Database error deleting user %s: %s", telegram_id, exc)
            raise YNABBotException(f"Database error: {exc}") from exc

    def find_by_status(self, status: UserStatus) -> List[UserConfiguration]:
        try:
            conn = self._db.get_connection()
            rows = conn.execute(
                "SELECT * FROM user_configurations WHERE status = %s ORDER BY created_at DESC",
                (status.value,),
            ).fetchall()
            return [self._row_to_user_config(row) for row in rows]
        except Exception as exc:
            logger.error("Database error finding users by status %s: %s", status, exc)
            raise YNABBotException(f"Database error: {exc}") from exc

    def find_all(self) -> List[UserConfiguration]:
        try:
            conn = self._db.get_connection()
            rows = conn.execute(
                "SELECT * FROM user_configurations ORDER BY created_at DESC"
            ).fetchall()
            return [self._row_to_user_config(row) for row in rows]
        except Exception as exc:
            logger.error("Database error finding all users: %s", exc)
            raise YNABBotException(f"Database error: {exc}") from exc

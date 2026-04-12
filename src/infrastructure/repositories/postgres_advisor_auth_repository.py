from __future__ import annotations

import logging
from typing import Optional

from domain.exceptions import YNABBotException
from domain.models.advisor_auth import AdvisorLaunchToken, AdvisorSession
from domain.repositories.advisor_auth_repository import AdvisorAuthRepository

logger = logging.getLogger(__name__)


class PostgresAdvisorAuthRepository(AdvisorAuthRepository):
    def __init__(self, db_manager):
        self._db = db_manager

    def create_launch_token(self, token: AdvisorLaunchToken) -> None:
        try:
            conn = self._db.get_connection()
            conn.execute(
                """
                INSERT INTO advisor_launch_tokens (token_hash, telegram_id, created_at, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (token.token_hash, token.telegram_id, token.created_at, token.expires_at),
            )
            conn.commit()
        except Exception as exc:
            logger.error("Database error creating advisor launch token: %s", exc)
            raise YNABBotException(f"Failed to create advisor launch token: {exc}") from exc

    def consume_launch_token(self, token_hash: str) -> Optional[AdvisorLaunchToken]:
        try:
            conn = self._db.get_connection()
            row = conn.execute(
                """
                DELETE FROM advisor_launch_tokens
                WHERE token_hash = %s
                RETURNING token_hash, telegram_id, created_at, expires_at
                """,
                (token_hash,),
            ).fetchone()
            conn.commit()
            if not row:
                return None
            return AdvisorLaunchToken(
                telegram_id=row["telegram_id"],
                token_hash=row["token_hash"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
            )
        except Exception as exc:
            logger.error("Database error consuming advisor launch token: %s", exc)
            raise YNABBotException(f"Failed to consume advisor launch token: {exc}") from exc

    def create_session(self, session: AdvisorSession) -> None:
        try:
            conn = self._db.get_connection()
            conn.execute(
                """
                INSERT INTO advisor_sessions (token_hash, telegram_id, created_at, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (session.token_hash, session.telegram_id, session.created_at, session.expires_at),
            )
            conn.commit()
        except Exception as exc:
            logger.error("Database error creating advisor session: %s", exc)
            raise YNABBotException(f"Failed to create advisor session: {exc}") from exc

    def find_session(self, token_hash: str) -> Optional[AdvisorSession]:
        try:
            conn = self._db.get_connection()
            row = conn.execute(
                """
                SELECT token_hash, telegram_id, created_at, expires_at
                FROM advisor_sessions
                WHERE token_hash = %s
                """,
                (token_hash,),
            ).fetchone()
            if not row:
                return None
            return AdvisorSession(
                telegram_id=row["telegram_id"],
                token_hash=row["token_hash"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
            )
        except Exception as exc:
            logger.error("Database error finding advisor session: %s", exc)
            raise YNABBotException(f"Failed to find advisor session: {exc}") from exc

    def delete_session(self, token_hash: str) -> bool:
        try:
            conn = self._db.get_connection()
            cursor = conn.execute(
                "DELETE FROM advisor_sessions WHERE token_hash = %s",
                (token_hash,),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as exc:
            logger.error("Database error deleting advisor session: %s", exc)
            raise YNABBotException(f"Failed to delete advisor session: {exc}") from exc

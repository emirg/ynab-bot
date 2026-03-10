from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Optional, List

from domain.repositories.user_repository import UserRepository
from domain.models.user import UserConfiguration, UserStatus
from domain.exceptions import YNABBotException
from infrastructure.repositories.database_manager import DatabaseManager
from infrastructure.token_encryption import TokenEncryptor

logger = logging.getLogger(__name__)


class SQLiteUserRepository(UserRepository):
    """SQLite implementation of UserRepository"""

    def __init__(self, db_manager: DatabaseManager, token_encryptor: Optional[TokenEncryptor] = None):
        self._db = db_manager
        self._encryptor = token_encryptor

    def _row_to_user_config(self, row: sqlite3.Row) -> UserConfiguration:
        """Convert a database row to a UserConfiguration domain model"""
        access_token = row['ynab_access_token']
        refresh_token = row['ynab_refresh_token']
        if self._encryptor:
            access_token = self._encryptor.decrypt(access_token)
            refresh_token = self._encryptor.decrypt(refresh_token)

        return UserConfiguration(
            telegram_id=row['telegram_id'],
            status=UserStatus(row['status']) if row['status'] else UserStatus.PENDING,
            budget_id=row['budget_id'],
            default_account_id=row['default_account_id'],
            default_account_name=row['default_account_name'],
            username=row['username'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
            approved_at=datetime.fromisoformat(row['approved_at']) if row['approved_at'] else None,
            approved_by=row['approved_by'],
            ynab_access_token=access_token,
            ynab_refresh_token=refresh_token,
            ynab_token_expires_at=datetime.fromisoformat(row['ynab_token_expires_at']) if row['ynab_token_expires_at'] else None,
        )

    def find_by_telegram_id(self, telegram_id: int) -> Optional[UserConfiguration]:
        """Find user configuration by Telegram user ID"""
        try:
            conn = self._db.get_connection()
            cursor = conn.execute(
                'SELECT * FROM user_configurations WHERE telegram_id = ?',
                (telegram_id,),
            )
            row = cursor.fetchone()
            return self._row_to_user_config(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Database error finding user {telegram_id}: {e}")
            raise YNABBotException(f"Database error: {e}")

    def save(self, user_config: UserConfiguration) -> UserConfiguration:
        """Save user configuration (insert or update)"""
        try:
            user_config.updated_at = datetime.now()

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
                     username, first_name, last_name, created_at, updated_at, approved_at, approved_by,
                     ynab_access_token, ynab_refresh_token, ynab_token_expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    status = excluded.status,
                    budget_id = excluded.budget_id,
                    default_account_id = excluded.default_account_id,
                    default_account_name = excluded.default_account_name,
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    updated_at = excluded.updated_at,
                    approved_at = excluded.approved_at,
                    approved_by = excluded.approved_by,
                    ynab_access_token = excluded.ynab_access_token,
                    ynab_refresh_token = excluded.ynab_refresh_token,
                    ynab_token_expires_at = excluded.ynab_token_expires_at
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
                    user_config.created_at.isoformat(),
                    user_config.updated_at.isoformat(),
                    user_config.approved_at.isoformat() if user_config.approved_at else None,
                    user_config.approved_by,
                    access_token,
                    refresh_token,
                    user_config.ynab_token_expires_at.isoformat() if user_config.ynab_token_expires_at else None,
                ),
            )
            conn.commit()
            logger.info(f"User configuration saved for {user_config.telegram_id}")
            return user_config
        except sqlite3.Error as e:
            logger.error(f"Database error saving user configuration: {e}")
            raise YNABBotException(f"Failed to save user configuration: {e}")

    def delete(self, telegram_id: int) -> bool:
        """Delete user configuration by Telegram user ID"""
        try:
            conn = self._db.get_connection()
            cursor = conn.execute(
                'DELETE FROM user_configurations WHERE telegram_id = ?',
                (telegram_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Database error deleting user {telegram_id}: {e}")
            raise YNABBotException(f"Database error: {e}")

    def find_by_status(self, status: UserStatus) -> List[UserConfiguration]:
        """Find all users with given status"""
        try:
            conn = self._db.get_connection()
            cursor = conn.execute(
                'SELECT * FROM user_configurations WHERE status = ? ORDER BY created_at DESC',
                (status.value,),
            )
            return [self._row_to_user_config(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Database error finding users by status {status}: {e}")
            raise YNABBotException(f"Database error: {e}")

    def find_all(self) -> List[UserConfiguration]:
        """Find all users"""
        try:
            conn = self._db.get_connection()
            cursor = conn.execute(
                'SELECT * FROM user_configurations ORDER BY created_at DESC'
            )
            return [self._row_to_user_config(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Database error finding all users: {e}")
            raise YNABBotException(f"Database error: {e}")

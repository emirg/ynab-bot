from __future__ import annotations

import logging
import os
import sqlite3
from typing import Optional

from domain.exceptions import YNABBotException

logger = logging.getLogger(__name__)

_MIGRATIONS = [
    # Version 1: initial user_configurations table
    (
        1,
        "Create user_configurations table",
        """
        CREATE TABLE IF NOT EXISTS user_configurations (
            telegram_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            budget_id TEXT,
            default_account_id TEXT,
            default_account_name TEXT,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            approved_by INTEGER
        );
        """,
    ),
    # Version 2: learning data tables (per-user)
    (
        2,
        "Create learning data tables",
        """
        CREATE TABLE IF NOT EXISTS payee_category_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            normalized_payee TEXT NOT NULL,
            category_id TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, normalized_payee, category_id),
            FOREIGN KEY (telegram_id) REFERENCES user_configurations(telegram_id)
        );

        CREATE TABLE IF NOT EXISTS user_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            normalized_payee TEXT NOT NULL,
            old_category_id TEXT NOT NULL,
            new_category_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telegram_id) REFERENCES user_configurations(telegram_id)
        );

        CREATE TABLE IF NOT EXISTS recent_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            payee TEXT NOT NULL,
            amount REAL NOT NULL,
            category_id TEXT,
            category_name TEXT,
            confidence REAL DEFAULT 0.0,
            parser_source TEXT DEFAULT 'unknown',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telegram_id) REFERENCES user_configurations(telegram_id)
        );

        CREATE INDEX IF NOT EXISTS idx_pcm_user_payee
            ON payee_category_mappings(telegram_id, normalized_payee);
        CREATE INDEX IF NOT EXISTS idx_recent_user
            ON recent_transactions(telegram_id, id DESC);
        """,
    ),
    # Version 3: OAuth token columns
    (
        3,
        "Add OAuth token columns to user_configurations",
        """
        ALTER TABLE user_configurations ADD COLUMN ynab_access_token TEXT;
        ALTER TABLE user_configurations ADD COLUMN ynab_refresh_token TEXT;
        ALTER TABLE user_configurations ADD COLUMN ynab_token_expires_at TIMESTAMP;
        """,
    ),
    # Version 4: Add category_name to payee_category_mappings
    (
        4,
        "Add category_name to payee_category_mappings",
        """
        ALTER TABLE payee_category_mappings ADD COLUMN category_name TEXT DEFAULT '';
        """,
    ),
    # Version 5: Split configuration tables
    (
        5,
        "Create split configuration tables",
        """
        CREATE TABLE IF NOT EXISTS split_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            category_id TEXT NOT NULL,
            category_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, category_id),
            FOREIGN KEY (telegram_id) REFERENCES user_configurations(telegram_id)
        );

        CREATE TABLE IF NOT EXISTS split_person_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            split_group_id INTEGER NOT NULL,
            alias TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(split_group_id, alias),
            FOREIGN KEY (split_group_id) REFERENCES split_groups(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS split_shared_account (
            telegram_id INTEGER PRIMARY KEY,
            account_id TEXT NOT NULL,
            account_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telegram_id) REFERENCES user_configurations(telegram_id)
        );

        CREATE INDEX IF NOT EXISTS idx_split_groups_user ON split_groups(telegram_id);
        CREATE INDEX IF NOT EXISTS idx_split_aliases_group ON split_person_aliases(split_group_id);
        """,
    ),
    # Version 6: Add ynab_transaction_id to recent_transactions
    (
        6,
        "Add ynab_transaction_id to recent_transactions",
        """
        ALTER TABLE recent_transactions ADD COLUMN ynab_transaction_id TEXT;
        """,
    ),
    # Version 7: Add timezone column to user_configurations
    (
        7,
        "Add timezone column to user_configurations",
        """
        ALTER TABLE user_configurations ADD COLUMN timezone TEXT DEFAULT 'America/Argentina/Buenos_Aires';
        """,
    ),
    # Version 8: Add last_weekly_summary_sent column to user_configurations
    (
        8,
        "Add last_weekly_summary_sent column to user_configurations",
        """
        ALTER TABLE user_configurations ADD COLUMN last_weekly_summary_sent TEXT;
        """,
    ),
    # Version 9: Add confirm_before_create column to user_configurations
    (
        9,
        "Add confirm_before_create column to user_configurations",
        """
        ALTER TABLE user_configurations ADD COLUMN confirm_before_create INTEGER DEFAULT 0;
        """,
    ),
]


class DatabaseManager:
    """Centralized SQLite database connection and migration manager."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_directory()
        self._init_database()

    def _ensure_directory(self) -> None:
        data_dir = os.path.dirname(self.db_path)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Migration system
    # ------------------------------------------------------------------

    def _init_database(self) -> None:
        try:
            conn = self.get_connection()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
            self._run_migrations()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise YNABBotException(f"Database initialization failed: {e}")

    def _get_current_version(self) -> int:
        conn = self.get_connection()
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        return row[0] or 0

    def _run_migrations(self) -> None:
        current_version = self._get_current_version()
        conn = self.get_connection()

        for version, description, sql in _MIGRATIONS:
            if version <= current_version:
                continue
            try:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                    (version, description),
                )
                conn.commit()
                logger.info(f"Applied migration v{version}: {description}")
            except Exception as e:
                logger.error(f"Migration v{version} failed: {e}")
                raise YNABBotException(f"Migration v{version} failed: {e}")

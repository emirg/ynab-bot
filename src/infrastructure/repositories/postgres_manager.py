from __future__ import annotations

import importlib
import logging
from typing import Any, Optional

from domain.exceptions import ConfigurationException, YNABBotException
from infrastructure.repositories.postgres_schema import POSTGRES_MIGRATIONS

logger = logging.getLogger(__name__)


class PostgresDatabaseManager:
    """Connection and migration manager for the future PostgreSQL runtime."""

    def __init__(self, dsn: str):
        if not dsn:
            raise ConfigurationException("PostgreSQL DSN is required")
        self.dsn = dsn
        self._connection: Optional[Any] = None

    def _load_psycopg(self):
        try:
            return importlib.import_module("psycopg")
        except ImportError as exc:
            raise ConfigurationException(
                "psycopg is required for PostgreSQL persistence. Install project dependencies first."
            ) from exc

    def get_connection(self):
        if self._connection is not None and not getattr(self._connection, "closed", False):
            return self._connection

        psycopg = self._load_psycopg()
        try:
            self._connection = psycopg.connect(self.dsn)
            return self._connection
        except Exception as exc:
            logger.error("Failed to connect to PostgreSQL: %s", exc)
            raise YNABBotException(f"PostgreSQL connection failed: {exc}") from exc

    def close(self) -> None:
        if self._connection is None:
            return
        self._connection.close()
        self._connection = None

    def initialize_schema(self) -> None:
        conn = self.get_connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            current_version = self.get_current_version()
            for version, description, sql in POSTGRES_MIGRATIONS:
                if version <= current_version:
                    continue
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, description) VALUES (%s, %s)",
                    (version, description),
                )
                conn.commit()
                logger.info("Applied PostgreSQL migration v%s: %s", version, description)
        except Exception as exc:
            if hasattr(conn, "rollback"):
                conn.rollback()
            logger.error("Failed to initialize PostgreSQL schema: %s", exc)
            raise YNABBotException(f"PostgreSQL schema initialization failed: {exc}") from exc

    def get_current_version(self) -> int:
        conn = self.get_connection()
        cursor = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
        row = cursor.fetchone()
        return row[0] if row else 0

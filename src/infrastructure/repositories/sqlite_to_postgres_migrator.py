from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from domain.exceptions import YNABBotException
from infrastructure.repositories.postgres_manager import PostgresDatabaseManager

logger = logging.getLogger(__name__)

_TABLE_COPY_ORDER = [
    "user_configurations",
    "payee_category_mappings",
    "user_corrections",
    "recent_transactions",
    "split_groups",
    "split_person_aliases",
    "split_shared_account",
]

_SERIAL_ID_TABLES = [
    "payee_category_mappings",
    "user_corrections",
    "recent_transactions",
    "split_groups",
    "split_person_aliases",
]


@dataclass(frozen=True)
class MigrationSummary:
    copied_rows_by_table: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.copied_rows_by_table.values())


class SQLiteToPostgresMigrator:
    """One-time migration helper from the current SQLite schema to PostgreSQL."""

    def __init__(self, sqlite_path: str, postgres_manager: PostgresDatabaseManager):
        self.sqlite_path = sqlite_path
        self.postgres_manager = postgres_manager

    def migrate(self) -> MigrationSummary:
        sqlite_file = Path(self.sqlite_path)
        if not sqlite_file.exists():
            raise YNABBotException(f"SQLite migration source does not exist: {self.sqlite_path}")

        self.postgres_manager.initialize_schema()
        postgres_conn = self.postgres_manager.get_connection()
        copied_rows_by_table: dict[str, int] = {}

        try:
            with sqlite3.connect(self.sqlite_path) as sqlite_conn:
                sqlite_conn.row_factory = sqlite3.Row
                for table_name in _TABLE_COPY_ORDER:
                    copied_rows_by_table[table_name] = self._copy_table(
                        sqlite_conn=sqlite_conn,
                        postgres_conn=postgres_conn,
                        table_name=table_name,
                    )

            self._reset_sequences(postgres_conn)
            postgres_conn.commit()
        except Exception as exc:
            if hasattr(postgres_conn, "rollback"):
                postgres_conn.rollback()
            logger.error("SQLite to PostgreSQL migration failed: %s", exc)
            raise YNABBotException(f"SQLite to PostgreSQL migration failed: {exc}") from exc

        return MigrationSummary(copied_rows_by_table=copied_rows_by_table)

    def _copy_table(self, sqlite_conn: sqlite3.Connection, postgres_conn, table_name: str) -> int:
        rows = sqlite_conn.execute(f"SELECT * FROM {table_name}").fetchall()
        if not rows:
            return 0

        columns = rows[0].keys()
        column_list = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        upsert_sql = self._build_upsert_sql(table_name=table_name, columns=list(columns), placeholders=placeholders)

        for row in rows:
            postgres_conn.execute(upsert_sql, tuple(row[column] for column in columns))

        logger.info("Copied %s rows into PostgreSQL table %s", len(rows), table_name)
        return len(rows)

    @staticmethod
    def _build_upsert_sql(table_name: str, columns: list[str], placeholders: str) -> str:
        column_list = ", ".join(columns)

        if table_name == "user_configurations":
            update_columns = [column for column in columns if column not in {"telegram_id", "created_at"}]
            update_clause = ", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)
            return (
                f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders}) "
                f"ON CONFLICT (telegram_id) DO UPDATE SET {update_clause}"
            )

        if table_name == "split_shared_account":
            update_columns = [column for column in columns if column not in {"telegram_id", "created_at"}]
            update_clause = ", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)
            return (
                f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders}) "
                f"ON CONFLICT (telegram_id) DO UPDATE SET {update_clause}"
            )

        if table_name == "payee_category_mappings":
            update_clause = ", ".join(
                f"{column} = EXCLUDED.{column}"
                for column in columns
                if column not in {"id", "telegram_id", "normalized_payee", "category_id"}
            )
            return (
                f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders}) "
                f"ON CONFLICT (telegram_id, normalized_payee, category_id) DO UPDATE SET {update_clause}"
            )

        if table_name == "split_groups":
            update_clause = ", ".join(
                f"{column} = EXCLUDED.{column}"
                for column in columns
                if column not in {"id", "telegram_id", "category_id"}
            )
            return (
                f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders}) "
                f"ON CONFLICT (telegram_id, category_id) DO UPDATE SET {update_clause}"
            )

        if table_name == "split_person_aliases":
            update_clause = ", ".join(
                f"{column} = EXCLUDED.{column}"
                for column in columns
                if column not in {"id", "split_group_id", "alias"}
            )
            return (
                f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders}) "
                f"ON CONFLICT (split_group_id, alias) DO UPDATE SET {update_clause}"
            )

        if "id" in columns:
            return f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"

        return f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def _reset_sequences(postgres_conn) -> None:
        for table_name in _SERIAL_ID_TABLES:
            postgres_conn.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                    (SELECT MAX(id) IS NOT NULL FROM {table_name})
                )
                """
            )

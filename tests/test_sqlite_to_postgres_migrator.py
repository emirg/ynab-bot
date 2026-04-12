from __future__ import annotations

import sqlite3

import pytest

from infrastructure.repositories.database_manager import DatabaseManager
from infrastructure.repositories.postgres_manager import PostgresDatabaseManager
from infrastructure.repositories.sqlite_to_postgres_migrator import SQLiteToPostgresMigrator


class _FakeCursor:
    def fetchone(self):
        return (None,)


class _FakePostgresConnection:
    def __init__(self):
        self.closed = False
        self.executed: list[tuple[str, tuple | None]] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, sql, params=None):
        statement = " ".join(sql.strip().split())
        self.executed.append((statement, params))
        return _FakeCursor()

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1


@pytest.fixture
def sqlite_db(tmp_path):
    db_path = tmp_path / "migration_source.db"
    manager = DatabaseManager(str(db_path))
    conn = manager.get_connection()

    conn.execute(
        """
        INSERT INTO user_configurations (
            telegram_id, status, budget_id, default_account_id, default_account_name,
            username, first_name, last_name, timezone, created_at, updated_at,
            ynab_access_token, ynab_refresh_token, confirm_before_create
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            123,
            "authorized",
            "budget-1",
            "account-1",
            "Main",
            "tester",
            "Test",
            "User",
            "America/Bogota",
            "2026-04-12T10:00:00",
            "2026-04-12T10:00:00",
            "access",
            "refresh",
            1,
        ),
    )
    conn.execute(
        """
        INSERT INTO payee_category_mappings (
            telegram_id, normalized_payee, category_id, category_name, count, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (123, "carulla", "cat-groceries", "Groceries", 2, "2026-04-12T10:01:00"),
    )
    conn.execute(
        """
        INSERT INTO user_corrections (
            telegram_id, normalized_payee, old_category_id, new_category_id
        ) VALUES (?, ?, ?, ?)
        """,
        (123, "carulla", "cat-old", "cat-groceries"),
    )
    conn.execute(
        """
        INSERT INTO recent_transactions (
            telegram_id, payee, amount, category_id, category_name, confidence, parser_source, ynab_transaction_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (123, "Carulla", 50000, "cat-groceries", "Groceries", 0.8, "llm", "txn-1"),
    )
    conn.execute(
        "INSERT INTO split_groups (telegram_id, category_id, category_name) VALUES (?, ?, ?)",
        (123, "cat-split", "Split"),
    )
    group_id = conn.execute("SELECT id FROM split_groups WHERE telegram_id = ?", (123,)).fetchone()[0]
    conn.execute(
        "INSERT INTO split_person_aliases (split_group_id, alias) VALUES (?, ?)",
        (group_id, "Juan"),
    )
    conn.execute(
        """
        INSERT INTO split_shared_account (
            telegram_id, account_id, account_name, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (123, "shared-1", "Shared", "2026-04-12T10:02:00", "2026-04-12T10:02:00"),
    )
    conn.commit()

    yield str(db_path)
    manager.close()


def test_migrates_all_tables(monkeypatch, sqlite_db):
    fake_connection = _FakePostgresConnection()
    manager = PostgresDatabaseManager("postgresql://example")
    monkeypatch.setattr(manager, "initialize_schema", lambda: None)
    monkeypatch.setattr(manager, "get_connection", lambda: fake_connection)

    summary = SQLiteToPostgresMigrator(sqlite_db, manager).migrate()

    assert summary.copied_rows_by_table["user_configurations"] == 1
    assert summary.copied_rows_by_table["split_person_aliases"] == 1
    assert summary.total_rows == 7
    assert fake_connection.commit_calls == 1
    assert fake_connection.rollback_calls == 0
    assert any("INSERT INTO user_configurations" in sql for sql, _ in fake_connection.executed)
    assert any("SELECT setval" in sql for sql, _ in fake_connection.executed)
    user_config_insert = next(
        params for sql, params in fake_connection.executed if "INSERT INTO user_configurations" in sql
    )
    assert user_config_insert[-1] is True


def test_raises_when_sqlite_source_missing(monkeypatch, tmp_path):
    fake_connection = _FakePostgresConnection()
    manager = PostgresDatabaseManager("postgresql://example")
    monkeypatch.setattr(manager, "initialize_schema", lambda: None)
    monkeypatch.setattr(manager, "get_connection", lambda: fake_connection)

    with pytest.raises(Exception, match="SQLite migration source does not exist"):
        SQLiteToPostgresMigrator(str(tmp_path / "missing.db"), manager).migrate()

import os
import sqlite3
import pytest
from src.infrastructure.repositories.database_manager import DatabaseManager


def test_database_initialization(tmp_path):
    db_file = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_file))

    # Check that schema_version table exists and has the latest version
    conn = db_manager.get_connection()
    cursor = conn.execute("SELECT MAX(version) FROM schema_version")
    version = cursor.fetchone()[0]

    assert version == 9
    db_manager.close()


def test_database_idempotency(tmp_path):
    db_file = tmp_path / "test.db"

    # Initialize first time
    db_manager = DatabaseManager(str(db_file))
    db_manager.close()

    # Initialize second time
    db_manager = DatabaseManager(str(db_file))
    conn = db_manager.get_connection()
    cursor = conn.execute("SELECT MAX(version) FROM schema_version")
    version = cursor.fetchone()[0]

    assert version == 9
    db_manager.close()


def test_split_tables_exist(tmp_path):
    db_file = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_file))
    conn = db_manager.get_connection()
    
    tables = ["split_groups", "split_person_aliases", "split_shared_account"]
    for table in tables:
        cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        assert cursor.fetchone() is not None

    db_manager.close()


def test_ynab_transaction_id_column_exists(tmp_path):
    db_file = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_file))
    conn = db_manager.get_connection()

    cursor = conn.execute("PRAGMA table_info(recent_transactions)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "ynab_transaction_id" in columns
    db_manager.close()


def test_timezone_column_exists(tmp_path):
    db_file = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_file))
    conn = db_manager.get_connection()

    cursor = conn.execute("PRAGMA table_info(user_configurations)")
    columns = {row[1]: row[4] for row in cursor.fetchall()}  # name -> default
    assert "timezone" in columns
    assert columns["timezone"] == "'America/Argentina/Buenos_Aires'"
    db_manager.close()


def test_migration_v8_fresh_db(tmp_path):
    """Migration v8 applies cleanly on a DB bootstrapped to exactly v8."""
    db_file = tmp_path / "test_v8_fresh.db"

    import src.infrastructure.repositories.database_manager as dm_module

    original_migrations = dm_module._MIGRATIONS
    dm_module._MIGRATIONS = [m for m in original_migrations if m[0] <= 8]
    try:
        db_manager = DatabaseManager(str(db_file))
        conn = db_manager.get_connection()

        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        assert cursor.fetchone()[0] == 8

        cursor = conn.execute("PRAGMA table_info(user_configurations)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "last_weekly_summary_sent" in columns

        db_manager.close()
    finally:
        dm_module._MIGRATIONS = original_migrations


def test_migration_v9_fresh_db(tmp_path):
    """Migration v9 applies cleanly on a fresh DB (v1 through v9)."""
    db_file = tmp_path / "test_v9_fresh.db"
    db_manager = DatabaseManager(str(db_file))
    conn = db_manager.get_connection()

    cursor = conn.execute("SELECT MAX(version) FROM schema_version")
    assert cursor.fetchone()[0] == 9

    cursor = conn.execute("PRAGMA table_info(user_configurations)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "confirm_before_create" in columns

    db_manager.close()


def test_migration_v9_on_existing_v8_db(tmp_path):
    """Migration v9 applies cleanly on a DB that was already at v8."""
    db_file = tmp_path / "test_v8_to_v9.db"

    import src.infrastructure.repositories.database_manager as dm_module

    original_migrations = dm_module._MIGRATIONS
    dm_module._MIGRATIONS = [m for m in original_migrations if m[0] <= 8]
    try:
        db_manager = DatabaseManager(str(db_file))
        conn = db_manager.get_connection()
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        assert cursor.fetchone()[0] == 8
        db_manager.close()
    finally:
        dm_module._MIGRATIONS = original_migrations

    # Now open again with full migrations — v9 should be applied
    db_manager = DatabaseManager(str(db_file))
    conn = db_manager.get_connection()

    cursor = conn.execute("SELECT MAX(version) FROM schema_version")
    assert cursor.fetchone()[0] == 9

    cursor = conn.execute("PRAGMA table_info(user_configurations)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "confirm_before_create" in columns

    db_manager.close()


def test_migration_v8_on_existing_v7_db(tmp_path):
    """Migration v8 applies cleanly on a DB that was already at v7."""
    db_file = tmp_path / "test_v7_to_v8.db"

    # Bootstrap the DB up to v7 by temporarily patching _MIGRATIONS
    import src.infrastructure.repositories.database_manager as dm_module

    original_migrations = dm_module._MIGRATIONS
    dm_module._MIGRATIONS = [m for m in original_migrations if m[0] <= 7]
    try:
        db_manager = DatabaseManager(str(db_file))
        conn = db_manager.get_connection()
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        assert cursor.fetchone()[0] == 7
        db_manager.close()
    finally:
        dm_module._MIGRATIONS = original_migrations

    # Now open again with migrations up to v8 — v8 should be applied
    dm_module._MIGRATIONS = [m for m in original_migrations if m[0] <= 8]
    try:
        db_manager = DatabaseManager(str(db_file))
        conn = db_manager.get_connection()

        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        assert cursor.fetchone()[0] == 8

        cursor = conn.execute("PRAGMA table_info(user_configurations)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "last_weekly_summary_sent" in columns

        db_manager.close()
    finally:
        dm_module._MIGRATIONS = original_migrations

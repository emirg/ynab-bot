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
    
    assert version == 7
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

    assert version == 7
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

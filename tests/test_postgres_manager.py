import types

import pytest

from domain.exceptions import ConfigurationException, YNABBotException
from infrastructure.repositories.postgres_manager import PostgresDatabaseManager
from infrastructure.repositories.postgres_schema import POSTGRES_MIGRATIONS


class _FakeCursor:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        return (self._value,)


class _FakeConnection:
    def __init__(self, version: int = 0):
        self.version = version
        self.closed = False
        self.executed = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, sql, params=None):
        statement = " ".join(sql.strip().split())
        self.executed.append((statement, params))
        if "SELECT COALESCE(MAX(version), 0) FROM schema_migrations" in statement:
            return _FakeCursor(self.version)
        if statement.startswith("INSERT INTO schema_migrations"):
            self.version = params[0]
        return _FakeCursor(None)

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.closed = True


class _FakePsycopg:
    def __init__(self, connection):
        self.connection = connection
        self.connect_calls = []

    def connect(self, dsn):
        self.connect_calls.append(dsn)
        return self.connection


def test_requires_dsn():
    with pytest.raises(ConfigurationException):
        PostgresDatabaseManager("")


def test_get_connection_reuses_open_connection(monkeypatch):
    connection = _FakeConnection()
    fake_psycopg = _FakePsycopg(connection)
    manager = PostgresDatabaseManager("postgresql://example")
    monkeypatch.setattr(manager, "_load_psycopg", lambda: fake_psycopg)

    first = manager.get_connection()
    second = manager.get_connection()

    assert first is second
    assert fake_psycopg.connect_calls == ["postgresql://example"]


def test_get_connection_wraps_driver_errors(monkeypatch):
    manager = PostgresDatabaseManager("postgresql://example")
    fake_psycopg = types.SimpleNamespace(
        connect=lambda dsn: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(manager, "_load_psycopg", lambda: fake_psycopg)

    with pytest.raises(YNABBotException, match="PostgreSQL connection failed"):
        manager.get_connection()


def test_initialize_schema_applies_latest_migration(monkeypatch):
    connection = _FakeConnection(version=0)
    manager = PostgresDatabaseManager("postgresql://example")
    monkeypatch.setattr(manager, "get_connection", lambda: connection)

    manager.initialize_schema()

    latest_version = POSTGRES_MIGRATIONS[-1][0]
    assert manager.get_current_version() == latest_version
    assert connection.commit_calls == len(POSTGRES_MIGRATIONS)
    assert any("CREATE TABLE IF NOT EXISTS user_configurations" in stmt for stmt, _ in connection.executed)


def test_initialize_schema_rolls_back_on_migration_error(monkeypatch):
    class _BrokenConnection(_FakeConnection):
        def execute(self, sql, params=None):
            statement = " ".join(sql.strip().split())
            if "CREATE TABLE IF NOT EXISTS user_configurations" in statement:
                raise RuntimeError("broken migration")
            return super().execute(sql, params)

    connection = _BrokenConnection(version=0)
    manager = PostgresDatabaseManager("postgresql://example")
    monkeypatch.setattr(manager, "get_connection", lambda: connection)

    with pytest.raises(YNABBotException, match="PostgreSQL schema initialization failed"):
        manager.initialize_schema()

    assert connection.rollback_calls == 1

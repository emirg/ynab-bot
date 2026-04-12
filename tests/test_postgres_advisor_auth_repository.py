from datetime import datetime, timezone

from domain.models.advisor_auth import AdvisorSession
from infrastructure.repositories.postgres_advisor_auth_repository import PostgresAdvisorAuthRepository


class _FakeCursor:
    def __init__(self, one=None, rowcount=0):
        self._one = one
        self.rowcount = rowcount

    def fetchone(self):
        return self._one


class _FakeConnection:
    def __init__(self, responses):
        self._responses = list(responses)
        self.executed = []
        self.commit_calls = 0

    def execute(self, sql, params=None):
        statement = " ".join(sql.strip().split())
        self.executed.append((statement, params))
        if self._responses:
            return self._responses.pop(0)
        return _FakeCursor()

    def commit(self):
        self.commit_calls += 1


class _FakeManager:
    def __init__(self, connection):
        self._connection = connection

    def get_connection(self):
        return self._connection


def test_create_launch_token_commits():
    conn = _FakeConnection([_FakeCursor()])
    repo = PostgresAdvisorAuthRepository(_FakeManager(conn))

    repo.create_launch_token(
        type("LaunchToken", (), {
            "token_hash": "hash",
            "telegram_id": 1,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc),
        })()
    )

    assert conn.commit_calls == 1
    assert any("INSERT INTO advisor_launch_tokens" in sql for sql, _ in conn.executed)


def test_find_session_returns_session_shape():
    row = {
        "token_hash": "hash",
        "telegram_id": 1,
        "created_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
        "expires_at": datetime(2026, 4, 13, 10, 0, 0, tzinfo=timezone.utc),
    }
    conn = _FakeConnection([_FakeCursor(one=row)])
    repo = PostgresAdvisorAuthRepository(_FakeManager(conn))

    session = repo.find_session("hash")

    assert isinstance(session, AdvisorSession)
    assert session.telegram_id == 1


def test_delete_session_uses_rowcount():
    conn = _FakeConnection([_FakeCursor(rowcount=1)])
    repo = PostgresAdvisorAuthRepository(_FakeManager(conn))

    assert repo.delete_session("hash") is True
    assert conn.commit_calls == 1

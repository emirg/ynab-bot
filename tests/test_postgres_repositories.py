from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from domain.models.expense import Expense
from domain.models.user import UserConfiguration, UserStatus
from infrastructure.repositories.postgres_learning_repository import PostgresLearningRepository
from infrastructure.repositories.postgres_split_config_repository import PostgresSplitConfigRepository
from infrastructure.repositories.postgres_user_repository import PostgresUserRepository


class _FakeCursor:
    def __init__(self, one=None, many=None, rowcount=0):
        self._one = one
        self._many = many or []
        self.rowcount = rowcount

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


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


class _Encryptor:
    def encrypt(self, value):
        return f"enc:{value}" if value is not None else None

    def decrypt(self, value):
        return value.replace("enc:", "") if value is not None else None


def test_postgres_user_repository_round_trips_user_row():
    row = {
        "telegram_id": 1,
        "status": "authorized",
        "budget_id": "budget-1",
        "default_account_id": "acc-1",
        "default_account_name": "Main",
        "username": "tester",
        "first_name": "Test",
        "last_name": "User",
        "timezone": "America/Bogota",
        "created_at": datetime(2026, 4, 12, 10, 0, 0),
        "updated_at": datetime(2026, 4, 12, 10, 1, 0),
        "approved_at": None,
        "approved_by": None,
        "ynab_access_token": "enc:token",
        "ynab_refresh_token": "enc:refresh",
        "ynab_token_expires_at": None,
        "last_weekly_summary_sent": None,
        "confirm_before_create": True,
    }
    conn = _FakeConnection([_FakeCursor(one=row)])
    repo = PostgresUserRepository(_FakeManager(conn), _Encryptor())

    found = repo.find_by_telegram_id(1)

    assert found is not None
    assert found.status == UserStatus.AUTHORIZED
    assert found.ynab_access_token == "token"
    assert found.confirm_before_create is True


def test_postgres_user_repository_save_commits():
    conn = _FakeConnection([_FakeCursor()])
    repo = PostgresUserRepository(_FakeManager(conn), _Encryptor())
    user = UserConfiguration(telegram_id=1, ynab_access_token="token", ynab_refresh_token="refresh")

    repo.save(user)

    assert conn.commit_calls == 1
    assert any("INSERT INTO user_configurations" in sql for sql, _ in conn.executed)


def test_postgres_learning_repository_predict_category():
    rows = [
        {"category_id": "cat-groceries", "count": 3},
        {"category_id": "cat-restaurants", "count": 1},
    ]
    conn = _FakeConnection([_FakeCursor(many=rows)])
    repo = PostgresLearningRepository(_FakeManager(conn))

    result = repo.predict_category(1, "Carulla", [{"id": "cat-groceries"}, {"id": "cat-restaurants"}])

    assert result == ("cat-groceries", 0.75, 3)


def test_postgres_learning_repository_recent_transactions_shape():
    row = {
        "payee": "Carulla",
        "amount": 50000,
        "category_id": "cat-groceries",
        "category_name": "Groceries",
        "confidence": 0.8,
        "parser_source": "llm",
        "created_at": datetime(2026, 4, 12, 10, 0, 0),
        "ynab_transaction_id": "txn-1",
    }
    conn = _FakeConnection([_FakeCursor(many=[row])])
    repo = PostgresLearningRepository(_FakeManager(conn))

    recent = repo.get_recent_transactions(1, 10)

    assert recent == [
        {
            "payee": "Carulla",
            "amount": 50000,
            "category_id": "cat-groceries",
            "category_name": "Groceries",
            "confidence": 0.8,
            "parser_source": "llm",
            "timestamp": datetime(2026, 4, 12, 10, 0, 0),
            "ynab_transaction_id": "txn-1",
        }
    ]


def test_postgres_learning_repository_add_recent_transaction_trims_and_commits():
    conn = _FakeConnection([_FakeCursor(), _FakeCursor()])
    repo = PostgresLearningRepository(_FakeManager(conn))
    expense = Expense(amount=Decimal("25000"), payee="Carulla", memo="Mercado")

    repo.add_recent_transaction(1, expense, ynab_transaction_id="txn-1")

    assert conn.commit_calls == 1
    assert any("INSERT INTO recent_transactions" in sql for sql, _ in conn.executed)
    assert any("DELETE FROM recent_transactions" in sql for sql, _ in conn.executed)


def test_postgres_split_config_repository_add_group_returns_existing_shape():
    conn = _FakeConnection(
        [
            _FakeCursor(),
            _FakeCursor(one={"id": 10, "created_at": datetime(2026, 4, 12, 10, 0, 0), "category_name": "Split"}),
            _FakeCursor(many=[{"alias": "Juan"}]),
        ]
    )
    repo = PostgresSplitConfigRepository(_FakeManager(conn))

    group = repo.add_split_group(1, "cat-split", "Split")

    assert group.id == 10
    assert group.person_aliases == ["Juan"]
    assert conn.commit_calls == 1


def test_postgres_split_config_repository_find_by_alias_is_case_insensitive():
    conn = _FakeConnection(
        [
            _FakeCursor(one={"id": 10, "category_id": "cat-split", "category_name": "Split", "created_at": datetime(2026, 4, 12, 10, 0, 0)}),
            _FakeCursor(many=[{"alias": "Juan"}]),
        ]
    )
    repo = PostgresSplitConfigRepository(_FakeManager(conn))

    group = repo.find_split_group_by_alias(1, "juan")

    assert group is not None
    assert group.category_id == "cat-split"
    assert group.person_aliases == ["Juan"]


def test_postgres_split_config_repository_shared_account_upsert_shape():
    created_at = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
    updated_at = datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc)
    conn = _FakeConnection(
        [
            _FakeCursor(),
            _FakeCursor(one={"created_at": created_at, "updated_at": updated_at}),
        ]
    )
    repo = PostgresSplitConfigRepository(_FakeManager(conn))

    config = repo.set_shared_account(1, "shared-1", "Shared")

    assert config.account_id == "shared-1"
    assert config.created_at == created_at
    assert config.updated_at == updated_at
    assert conn.commit_calls == 1

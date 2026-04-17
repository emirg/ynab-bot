from datetime import datetime
from decimal import Decimal

import pytest

from project_bootstrap import ensure_src_path

ensure_src_path()

from domain.models.expense import Expense
from domain.models.split_config import SharedAccountConfig, SplitGroup
from domain.models.user import (
    UserConfiguration,
    UserStatus,
    YNABAccount,
    YNABBudget,
    YNABCategory,
)


@pytest.fixture
def sample_expense():
    return Expense(
        amount=Decimal("25000"),
        payee="McDonald's",
        memo="Almuerzo McDonald's",
        category_id="550e8400-e29b-41d4-a716-446655440000",
        category_name="Restaurants",
        account_id="660e8400-e29b-41d4-a716-446655440000",
        account_name="Nu Card",
        confidence=0.85,
        parser_source="llm",
        category_explanation="sugerido por IA, confianza 85%",
        date=datetime(2026, 3, 9, 12, 0, 0),
    )


@pytest.fixture
def minimal_expense():
    return Expense(
        amount=Decimal("10000"),
        payee="Carulla",
        memo="Compras super",
    )


@pytest.fixture
def authorized_user():
    return UserConfiguration(
        telegram_id=123456789,
        status=UserStatus.AUTHORIZED,
        budget_id="budget-uuid-1",
        default_account_id="account-uuid-1",
        default_account_name="Nu Card",
        username="testuser",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def pending_user():
    return UserConfiguration(
        telegram_id=987654321,
        status=UserStatus.PENDING,
        username="pendinguser",
        first_name="Pending",
    )


@pytest.fixture
def blocked_user():
    return UserConfiguration(
        telegram_id=111111111,
        status=UserStatus.BLOCKED,
        username="blockeduser",
        first_name="Blocked",
    )


@pytest.fixture
def sample_categories():
    return [
        YNABCategory(
            id="cat-1",
            name="Groceries",
            group_name="Essentials",
            full_name="Essentials -> Groceries",
        ),
        YNABCategory(
            id="cat-2",
            name="Restaurants",
            group_name="Essentials",
            full_name="Essentials -> Restaurants",
        ),
        YNABCategory(
            id="cat-3",
            name="Transport",
            group_name="Essentials",
            full_name="Essentials -> Transport",
        ),
        YNABCategory(
            id="cat-hidden",
            name="Hidden",
            group_name="Internal",
            full_name="Internal -> Hidden",
            hidden=True,
        ),
        YNABCategory(
            id="cat-deleted",
            name="Deleted",
            group_name="Internal",
            full_name="Internal -> Deleted",
            deleted=True,
        ),
    ]


@pytest.fixture
def sample_accounts():
    return [
        YNABAccount(id="acc-1", name="Nu Card", type="creditCard", balance=500000),
        YNABAccount(id="acc-2", name="Bancolombia", type="checking", balance=1000000),
        YNABAccount(id="acc-closed", name="Old", type="checking", closed=True),
        YNABAccount(id="acc-deleted", name="Gone", type="checking", deleted=True),
    ]


@pytest.fixture
def sample_budgets():
    return [
        YNABBudget(id="budget-1", name="My Budget", currency_format={"iso_code": "COP"}),
        YNABBudget(id="budget-2", name="Savings", currency_format={"iso_code": "COP"}),
    ]


@pytest.fixture
def sample_split_groups():
    return [
        SplitGroup(
            id=1,
            telegram_id=123456789,
            category_id="cat-123",
            category_name="Gastos Compartidos",
            person_aliases=["Juan", "Juancho"],
            created_at=datetime(2026, 3, 14, 10, 0, 0),
        ),
        SplitGroup(
            id=2,
            telegram_id=123456789,
            category_id="cat-456",
            category_name="Gastos con Juan",
            person_aliases=["Juan"],
            created_at=datetime(2026, 3, 14, 11, 0, 0),
        ),
    ]


@pytest.fixture
def sample_shared_account():
    return SharedAccountConfig(
        telegram_id=123456789,
        account_id="acc-shared",
        account_name="Nu Savings",
        created_at=datetime(2026, 3, 14, 10, 0, 0),
        updated_at=datetime(2026, 3, 14, 10, 0, 0),
    )

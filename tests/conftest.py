import sys
import os
import json
import tempfile
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

# Add src to path so imports work like in production
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from domain.models.expense import Expense, ExpenseResult
from domain.models.user import UserConfiguration, UserStatus, YNABBudget, YNABAccount, YNABCategory
from domain.models.split_config import SplitGroup, SharedAccountConfig


# ---------------------------------------------------------------------------
# Domain model fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_expense():
    return Expense(
        amount=Decimal('25000'),
        payee="McDonald's",
        memo="Almuerzo McDonald's",
        category_id='550e8400-e29b-41d4-a716-446655440000',
        category_name='Restaurants',
        account_id='660e8400-e29b-41d4-a716-446655440000',
        account_name='Nu Card',
        confidence=0.85,
        parser_source='llm',
        category_explanation='sugerido por IA, confianza 85%',
        date=datetime(2026, 3, 9, 12, 0, 0),
    )


@pytest.fixture
def minimal_expense():
    return Expense(
        amount=Decimal('10000'),
        payee='Carulla',
        memo='Compras super',
    )


@pytest.fixture
def authorized_user():
    user = UserConfiguration(
        telegram_id=123456789,
        status=UserStatus.AUTHORIZED,
        budget_id='budget-uuid-1',
        default_account_id='account-uuid-1',
        default_account_name='Nu Card',
        username='testuser',
        first_name='Test',
        last_name='User',
    )
    return user


@pytest.fixture
def pending_user():
    return UserConfiguration(
        telegram_id=987654321,
        status=UserStatus.PENDING,
        username='pendinguser',
        first_name='Pending',
    )


@pytest.fixture
def blocked_user():
    return UserConfiguration(
        telegram_id=111111111,
        status=UserStatus.BLOCKED,
        username='blockeduser',
        first_name='Blocked',
    )


@pytest.fixture
def sample_categories():
    return [
        YNABCategory(
            id='cat-1', name='Groceries', group_name='Essentials',
            full_name='Essentials -> Groceries',
        ),
        YNABCategory(
            id='cat-2', name='Restaurants', group_name='Essentials',
            full_name='Essentials -> Restaurants',
        ),
        YNABCategory(
            id='cat-3', name='Transport', group_name='Essentials',
            full_name='Essentials -> Transport',
        ),
        YNABCategory(
            id='cat-hidden', name='Hidden', group_name='Internal',
            full_name='Internal -> Hidden', hidden=True,
        ),
        YNABCategory(
            id='cat-deleted', name='Deleted', group_name='Internal',
            full_name='Internal -> Deleted', deleted=True,
        ),
    ]


@pytest.fixture
def sample_accounts():
    return [
        YNABAccount(id='acc-1', name='Nu Card', type='creditCard', balance=500000),
        YNABAccount(id='acc-2', name='Bancolombia', type='checking', balance=1000000),
        YNABAccount(id='acc-closed', name='Old', type='checking', closed=True),
        YNABAccount(id='acc-deleted', name='Gone', type='checking', deleted=True),
    ]


@pytest.fixture
def sample_budgets():
    return [
        YNABBudget(id='budget-1', name='My Budget', currency_format={'iso_code': 'COP'}),
        YNABBudget(id='budget-2', name='Savings', currency_format={'iso_code': 'COP'}),
    ]


# ---------------------------------------------------------------------------
# Temp file fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_json_file(tmp_path):
    """Temporary JSON file for learning repository tests."""
    return str(tmp_path / 'learning_data.json')


@pytest.fixture
def tmp_db_file(tmp_path):
    """Temporary SQLite DB file for user repository tests."""
    return str(tmp_path / 'test_users.db')


# ---------------------------------------------------------------------------
# Mock repository fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user_repository():
    repo = MagicMock()
    repo.find_by_telegram_id.return_value = None
    repo.save.side_effect = lambda entity: entity
    repo.find_by_status.return_value = []
    repo.find_all.return_value = []
    return repo


@pytest.fixture
def mock_ynab_repository(sample_categories, sample_accounts, sample_budgets):
    repo = MagicMock()
    repo.get_categories.return_value = sample_categories
    repo.get_accounts.return_value = sample_accounts
    repo.get_budgets.return_value = sample_budgets
    repo.create_transaction.return_value = 'txn-id-123'
    return repo


@pytest.fixture
def mock_learning_repository():
    repo = MagicMock()
    repo.predict_category.return_value = None
    repo.record_successful_transaction.return_value = None
    repo.add_recent_transaction.return_value = None
    repo.get_learning_statistics.return_value = {
        'total_transactions': 10,
        'learned_associations': 5,
        'accuracy_improvements': 2,
        'learned_payees': 3,
        'total_corrections': 2,
    }
    repo.get_recent_transactions.return_value = []
    repo.get_payee_associations.return_value = []
    repo.delete_payee_associations.return_value = 0
    return repo


@pytest.fixture
def mock_llm_parser():
    parser = MagicMock()
    parser.parse_expense.return_value = {
        'amount': 25000.0,
        'category': 'Restaurants',
        'payee': "McDonald's",
        'account': None,
        'memo': "Almuerzo McDonald's",
        'confidence': 0.85,
    }
    parser.parse_message.return_value = {
        'intent': 'expense',
        'amount': 25000.0,
        'category': 'Restaurants',
        'payee': "McDonald's",
        'account': None,
        'memo': "Almuerzo McDonald's",
        'confidence': 0.85,
    }
    parser.update_categories.return_value = None
    parser.update_accounts.return_value = None
    return parser


@pytest.fixture
def mock_oauth_service():
    service = MagicMock()
    service.generate_auth_url.return_value = "https://app.ynab.com/oauth/authorize?client_id=test"
    service.get_valid_access_token.return_value = "valid-access-token"
    service.disconnect_user.return_value = True
    return service


@pytest.fixture
def mock_ynab_factory(mock_ynab_repository):
    factory = MagicMock()
    factory.get_repository.return_value = mock_ynab_repository
    return factory


# ---------------------------------------------------------------------------
# Split config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_split_groups():
    return [
        SplitGroup(
            id=1,
            telegram_id=123456789,
            category_id='cat-123',
            category_name='Gastos E',
            person_aliases=['Eliana', 'Eli'],
            created_at=datetime(2026, 3, 14, 10, 0, 0)
        ),
        SplitGroup(
            id=2,
            telegram_id=123456789,
            category_id='cat-456',
            category_name='Gastos con Juan',
            person_aliases=['Juan'],
            created_at=datetime(2026, 3, 14, 11, 0, 0)
        )
    ]


@pytest.fixture
def sample_shared_account():
    return SharedAccountConfig(
        telegram_id=123456789,
        account_id='acc-shared',
        account_name='Nu Savings',
        created_at=datetime(2026, 3, 14, 10, 0, 0),
        updated_at=datetime(2026, 3, 14, 10, 0, 0)
    )


@pytest.fixture
def mock_split_config_repository(sample_split_groups, sample_shared_account):
    repo = MagicMock()
    repo.get_split_groups.return_value = sample_split_groups
    repo.get_shared_account.return_value = sample_shared_account
    repo.add_split_group.return_value = sample_split_groups[0]
    repo.remove_split_group.return_value = True
    repo.add_person_alias.return_value = True
    repo.remove_person_alias.return_value = True
    repo.set_shared_account.return_value = sample_shared_account
    repo.remove_shared_account.return_value = True
    repo.find_split_group_by_alias.return_value = sample_split_groups[0]
    return repo

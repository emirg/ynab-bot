from unittest.mock import MagicMock

import pytest


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
    repo.create_transaction.return_value = "txn-id-123"
    repo.get_transaction_by_id.return_value = {
        "id": "txn-id-123",
        "amount": -25_000_000,
        "payee_name": "McDonalds",
        "category_id": "cat-2",
    }
    return repo


@pytest.fixture
def mock_learning_repository():
    repo = MagicMock()
    repo.predict_category.return_value = None
    repo.record_successful_transaction.return_value = None
    repo.add_recent_transaction.return_value = None
    repo.get_payee_category_distribution.return_value = {}
    repo.get_learning_statistics.return_value = {
        "total_transactions": 10,
        "learned_associations": 5,
        "accuracy_improvements": 2,
        "learned_payees": 3,
        "total_corrections": 2,
    }
    repo.get_recent_transactions.return_value = []
    repo.get_payee_associations.return_value = []
    repo.delete_payee_associations.return_value = 0
    return repo


@pytest.fixture
def mock_llm_parser():
    parser = MagicMock()
    parser.parse_expense.return_value = {
        "amount": 25000.0,
        "category": "Restaurants",
        "payee": "McDonald's",
        "account": None,
        "memo": "Almuerzo McDonald's",
        "confidence": 0.85,
    }
    parser.parse_message.return_value = {
        "intent": "expense",
        "amount": 25000.0,
        "category": "Restaurants",
        "payee": "McDonald's",
        "account": None,
        "memo": "Almuerzo McDonald's",
        "confidence": 0.85,
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

import pytest
from unittest.mock import MagicMock, patch
from application.services.split_config_service import SplitConfigService
from domain.models.split_config import SplitGroup, SharedAccountConfig
from domain.models.user import UserConfiguration, YNABCategory, YNABAccount
from domain.exceptions import YNABApiException


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_user_repo():
    return MagicMock()


@pytest.fixture
def mock_ynab_factory():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_user_repo, mock_ynab_factory):
    return SplitConfigService(mock_repo, mock_user_repo, mock_ynab_factory)


def test_add_split_group_success(service, mock_repo, mock_user_repo, mock_ynab_factory):
    telegram_id = 123
    category_id = "cat1"

    user_config = UserConfiguration(telegram_id=telegram_id, budget_id="b1", ynab_access_token="tok")
    mock_user_repo.find_by_telegram_id.return_value = user_config

    mock_ynab_repo = MagicMock()
    mock_ynab_factory.get_repository.return_value = mock_ynab_repo
    mock_ynab_repo.get_categories.return_value = [
        YNABCategory(id=category_id, name="Gastos Compartidos", group_name="Shared", full_name="Shared: Gastos Compartidos", hidden=False)
    ]

    service.add_split_group(telegram_id, category_id)

    mock_repo.add_split_group.assert_called_once_with(telegram_id, category_id, "Gastos Compartidos")


def test_add_split_group_not_found(service, mock_user_repo, mock_ynab_factory):
    telegram_id = 123
    user_config = UserConfiguration(telegram_id=telegram_id, budget_id="b1", ynab_access_token="tok")
    mock_user_repo.find_by_telegram_id.return_value = user_config

    mock_ynab_repo = MagicMock()
    mock_ynab_factory.get_repository.return_value = mock_ynab_repo
    mock_ynab_repo.get_categories.return_value = []

    with pytest.raises(YNABApiException, match="Categoría unknown no encontrada en YNAB"):
        service.add_split_group(telegram_id, "unknown")


def test_set_shared_account_success(service, mock_repo, mock_user_repo, mock_ynab_factory):
    telegram_id = 123
    account_id = "acc1"

    user_config = UserConfiguration(telegram_id=telegram_id, budget_id="b1", ynab_access_token="tok")
    mock_user_repo.find_by_telegram_id.return_value = user_config

    mock_ynab_repo = MagicMock()
    mock_ynab_factory.get_repository.return_value = mock_ynab_repo
    mock_ynab_repo.get_accounts.return_value = [
        YNABAccount(id=account_id, name="Nu Savings", type="checking", closed=False)
    ]

    service.set_shared_account(telegram_id, account_id)

    mock_repo.set_shared_account.assert_called_once_with(telegram_id, account_id, "Nu Savings")


def test_get_split_config_summary(service, mock_repo):
    telegram_id = 123
    mock_repo.get_split_groups.return_value = [MagicMock(spec=SplitGroup)]
    mock_repo.get_shared_account.return_value = MagicMock(spec=SharedAccountConfig)
    
    summary = service.get_split_config_summary(telegram_id)
    
    assert len(summary["groups"]) == 1
    assert summary["shared_account"] is not None
    assert summary["configured"] is True


def test_add_person_alias_empty(service):
    assert service.add_person_alias(123, "cat1", "  ") is False

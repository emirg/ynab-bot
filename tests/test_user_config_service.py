"""Tests for UserConfigService."""
import pytest

from application.services.user_config_service import UserConfigService
from domain.models.user import UserConfiguration, UserStatus, YNABBudget, YNABAccount
from domain.exceptions import YNABApiException


@pytest.fixture
def service(mock_user_repository, mock_ynab_repository):
    return UserConfigService(
        user_repository=mock_user_repository,
        ynab_repository=mock_ynab_repository,
    )


# ---------------------------------------------------------------------------
# get_or_create_user_config
# ---------------------------------------------------------------------------

class TestGetOrCreateUserConfig:

    def test_returns_existing(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.get_or_create_user_config(authorized_user.telegram_id)
        assert result == authorized_user

    def test_creates_new(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.get_or_create_user_config(42)
        assert result.telegram_id == 42
        mock_user_repository.save.assert_called_once()


# ---------------------------------------------------------------------------
# get_available_budgets
# ---------------------------------------------------------------------------

class TestGetAvailableBudgets:

    def test_returns_budgets(self, service, sample_budgets):
        result = service.get_available_budgets()
        assert len(result) == 2

    def test_raises_on_error(self, service, mock_ynab_repository):
        mock_ynab_repository.get_budgets.side_effect = Exception('connection error')
        with pytest.raises(YNABApiException):
            service.get_available_budgets()


# ---------------------------------------------------------------------------
# set_user_budget
# ---------------------------------------------------------------------------

class TestSetUserBudget:

    def test_sets_budget(self, service, mock_user_repository, mock_ynab_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.set_user_budget(42, 'budget-1')
        assert result.budget_id == 'budget-1'

    def test_invalid_budget_raises(self, service, mock_ynab_repository):
        with pytest.raises(YNABApiException):
            service.set_user_budget(42, 'nonexistent-budget')


# ---------------------------------------------------------------------------
# get_user_accounts
# ---------------------------------------------------------------------------

class TestGetUserAccounts:

    def test_returns_accounts(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        accounts, error = service.get_user_accounts(authorized_user.telegram_id)
        assert len(accounts) > 0
        assert error is None

    def test_no_budget_configured(self, service, mock_user_repository):
        user = UserConfiguration(telegram_id=42)
        mock_user_repository.find_by_telegram_id.return_value = user
        accounts, error = service.get_user_accounts(42)
        assert accounts == []
        assert error is not None

    def test_user_not_found(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        accounts, error = service.get_user_accounts(999)
        assert accounts == []
        assert error is not None

    def test_api_error(self, service, mock_user_repository, mock_ynab_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.get_accounts.side_effect = Exception('timeout')
        accounts, error = service.get_user_accounts(authorized_user.telegram_id)
        assert accounts == []
        assert error is not None


# ---------------------------------------------------------------------------
# set_default_account
# ---------------------------------------------------------------------------

class TestSetDefaultAccount:

    def test_sets_account(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.set_default_account(authorized_user.telegram_id, 'acc-1')
        assert result.default_account_id == 'acc-1'
        assert result.default_account_name == 'Nu Card'

    def test_no_budget_raises(self, service, mock_user_repository):
        user = UserConfiguration(telegram_id=42)
        mock_user_repository.find_by_telegram_id.return_value = user
        with pytest.raises(YNABApiException):
            service.set_default_account(42, 'acc-1')

    def test_user_not_found_raises(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        with pytest.raises(YNABApiException):
            service.set_default_account(999, 'acc-1')

    def test_invalid_account_raises(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        with pytest.raises(YNABApiException):
            service.set_default_account(authorized_user.telegram_id, 'nonexistent')


# ---------------------------------------------------------------------------
# get_user_status
# ---------------------------------------------------------------------------

class TestGetUserStatus:

    def test_configured_user(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        status = service.get_user_status(authorized_user.telegram_id)
        assert status['configured'] is True
        assert status['budget_id'] == authorized_user.budget_id
        assert 'completamente' in status['message'].lower()

    def test_unconfigured_user(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        status = service.get_user_status(999)
        assert status['configured'] is False
        assert status['budget_id'] is None

    def test_partially_configured(self, service, mock_user_repository):
        user = UserConfiguration(telegram_id=42, budget_id='b1')
        mock_user_repository.find_by_telegram_id.return_value = user
        status = service.get_user_status(42)
        assert not status['configured']
        assert 'cuenta' in status['message'].lower()

    def test_budget_name_resolved(self, service, mock_user_repository, authorized_user, sample_budgets):
        authorized_user.budget_id = 'budget-1'
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        status = service.get_user_status(authorized_user.telegram_id)
        assert status['budget_name'] == 'My Budget'

    def test_budget_name_api_error(self, service, mock_user_repository, mock_ynab_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.get_budgets.side_effect = Exception('api error')
        status = service.get_user_status(authorized_user.telegram_id)
        assert status['budget_name'] is None  # fails gracefully


# ---------------------------------------------------------------------------
# reset_user_config
# ---------------------------------------------------------------------------

class TestResetUserConfig:

    def test_resets_config(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        assert service.reset_user_config(authorized_user.telegram_id) is True
        assert authorized_user.budget_id is None
        assert authorized_user.default_account_id is None

    def test_user_not_found_returns_true(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        assert service.reset_user_config(999) is True

    def test_error_returns_false(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.side_effect = Exception('db error')
        assert service.reset_user_config(42) is False

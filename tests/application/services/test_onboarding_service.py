import pytest
from unittest.mock import MagicMock

from application.services.onboarding_service import OnboardingService
from domain.models.onboarding import OnboardingStep
from domain.models.user import UserConfiguration


@pytest.fixture
def user_repo():
    return MagicMock()


@pytest.fixture
def onboarding_service(user_repo):
    return OnboardingService(user_repo)


def test_get_onboarding_step_user_not_found(onboarding_service, user_repo):
    user_repo.find_by_telegram_id.return_value = None
    assert onboarding_service.get_onboarding_step(123) == OnboardingStep.NEEDS_YNAB_CONNECTION


def test_get_onboarding_step_needs_ynab_connection(onboarding_service, user_repo):
    # User exists but no YNAB token
    user = UserConfiguration(telegram_id=123, ynab_access_token=None)
    user_repo.find_by_telegram_id.return_value = user
    
    assert onboarding_service.get_onboarding_step(123) == OnboardingStep.NEEDS_YNAB_CONNECTION


def test_get_onboarding_step_needs_budget(onboarding_service, user_repo):
    # User has YNAB token but no budget_id
    user = UserConfiguration(telegram_id=123, ynab_access_token="valid_token", budget_id=None)
    user_repo.find_by_telegram_id.return_value = user
    
    assert onboarding_service.get_onboarding_step(123) == OnboardingStep.NEEDS_BUDGET


def test_get_onboarding_step_needs_account(onboarding_service, user_repo):
    # User has YNAB token and budget_id but no default_account_id
    user = UserConfiguration(
        telegram_id=123, 
        ynab_access_token="valid_token", 
        budget_id="budget-123",
        default_account_id=None
    )
    user_repo.find_by_telegram_id.return_value = user
    
    assert onboarding_service.get_onboarding_step(123) == OnboardingStep.NEEDS_ACCOUNT


def test_get_onboarding_step_complete(onboarding_service, user_repo):
    # User is fully configured
    user = UserConfiguration(
        telegram_id=123, 
        ynab_access_token="valid_token", 
        budget_id="budget-123",
        default_account_id="account-123"
    )
    user_repo.find_by_telegram_id.return_value = user
    
    assert onboarding_service.get_onboarding_step(123) == OnboardingStep.COMPLETE

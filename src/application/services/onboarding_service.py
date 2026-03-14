from typing import Optional

from domain.models.onboarding import OnboardingStep
from domain.repositories.user_repository import UserRepository


class OnboardingService:
    """Service to determine the current onboarding state of a user"""

    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    def get_onboarding_step(self, telegram_user_id: int) -> OnboardingStep:
        """
        Determines the current onboarding step for a given Telegram user ID.
        
        Derives state from existing user configuration:
        1. No YNAB token (or user not found) -> NEEDS_YNAB_CONNECTION
        2. Has token, no budget_id -> NEEDS_BUDGET
        3. Has token + budget_id, no default_account_id -> NEEDS_ACCOUNT
        4. Fully configured -> COMPLETE
        """
        user = self._user_repository.find_by_telegram_id(telegram_user_id)
        
        if not user or not user.has_ynab_token():
            return OnboardingStep.NEEDS_YNAB_CONNECTION
            
        if not user.budget_id:
            return OnboardingStep.NEEDS_BUDGET
            
        if not user.default_account_id:
            return OnboardingStep.NEEDS_ACCOUNT
            
        return OnboardingStep.COMPLETE

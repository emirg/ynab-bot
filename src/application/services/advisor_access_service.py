from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from domain.exceptions import AdvisorAuthenticationException
from domain.models.advisor_auth import AdvisorLaunchToken, AdvisorSession
from domain.models.onboarding import OnboardingStep
from domain.repositories.advisor_auth_repository import AdvisorAuthRepository
from domain.repositories.learning_repository import LearningRepository
from domain.repositories.user_repository import UserRepository
from infrastructure.config.app_config import AppConfig
from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory

_LAUNCH_TOKEN_TTL_SECONDS = 600
_SESSION_TTL_SECONDS = 24 * 60 * 60


class AdvisorAccessService:
    def __init__(
        self,
        config: AppConfig,
        advisor_auth_repository: AdvisorAuthRepository,
        user_repository: UserRepository,
        learning_repository: LearningRepository,
        ynab_factory: YNABRepositoryFactory,
    ):
        self._config = config
        self._advisor_auth_repository = advisor_auth_repository
        self._user_repository = user_repository
        self._learning_repository = learning_repository
        self._ynab_factory = ynab_factory

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def create_launch_url(self, telegram_user_id: int) -> str:
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        launch_token = AdvisorLaunchToken(
            telegram_id=telegram_user_id,
            token_hash=self._hash_token(raw_token),
            created_at=now,
            expires_at=now + timedelta(seconds=_LAUNCH_TOKEN_TTL_SECONDS),
        )
        self._advisor_auth_repository.create_launch_token(launch_token)
        return f"{self._config.resolved_advisor_base_url}/advisor/launch?token={raw_token}"

    def exchange_launch_token(self, raw_token: str) -> str:
        if not raw_token:
            raise AdvisorAuthenticationException("Missing advisor launch token")

        token_hash = self._hash_token(raw_token)
        launch_token = self._advisor_auth_repository.consume_launch_token(token_hash)
        if launch_token is None or launch_token.expires_at <= datetime.now(timezone.utc):
            raise AdvisorAuthenticationException("Advisor launch token is invalid or expired")

        raw_session_token = secrets.token_urlsafe(32)
        session = AdvisorSession.with_ttl(
            telegram_id=launch_token.telegram_id,
            token_hash=self._hash_token(raw_session_token),
            ttl_seconds=_SESSION_TTL_SECONDS,
        )
        self._advisor_auth_repository.create_session(session)
        return raw_session_token

    def get_session_telegram_id(self, raw_session_token: str | None) -> int | None:
        if not raw_session_token:
            return None

        token_hash = self._hash_token(raw_session_token)
        session = self._advisor_auth_repository.find_session(token_hash)
        if session is None:
            return None

        if session.expires_at <= datetime.now(timezone.utc):
            self._advisor_auth_repository.delete_session(token_hash)
            return None

        return session.telegram_id

    def logout(self, raw_session_token: str | None) -> bool:
        if not raw_session_token:
            return False
        return self._advisor_auth_repository.delete_session(self._hash_token(raw_session_token))

    def get_bootstrap_payload(self, telegram_user_id: int) -> dict:
        user = self._user_repository.find_by_telegram_id(telegram_user_id)
        if user is None:
            raise AdvisorAuthenticationException("Advisor session user was not found")

        onboarding_state = self._resolve_onboarding_state(user)
        availability = self._resolve_availability(telegram_user_id, onboarding_state)

        return {
            "status": "ok",
            "advisor_state": availability,
            "onboarding_state": onboarding_state.value,
            "user": {
                "telegram_id": user.telegram_id,
                "display_name": user.get_display_name(),
                "username": user.username,
            },
            "ynab_connected": user.has_ynab_token(),
            "budget_id": user.budget_id,
            "budget_name": self._resolve_budget_name(user),
            "default_account_id": user.default_account_id,
            "default_account_name": user.default_account_name,
        }

    def _resolve_onboarding_state(self, user) -> OnboardingStep:
        if not user.has_ynab_token():
            return OnboardingStep.NEEDS_YNAB_CONNECTION
        if not user.budget_id:
            return OnboardingStep.NEEDS_BUDGET
        if not user.default_account_id:
            return OnboardingStep.NEEDS_ACCOUNT
        return OnboardingStep.COMPLETE

    def _resolve_availability(self, telegram_user_id: int, onboarding_state: OnboardingStep) -> str:
        if onboarding_state == OnboardingStep.NEEDS_YNAB_CONNECTION:
            return "needs_ynab"
        if onboarding_state == OnboardingStep.NEEDS_BUDGET:
            return "needs_budget"
        if onboarding_state == OnboardingStep.NEEDS_ACCOUNT:
            return "needs_account"
        recent = self._learning_repository.get_recent_transactions(telegram_user_id, limit=1)
        return "ready" if recent else "empty"

    def _resolve_budget_name(self, user) -> str | None:
        if not user.budget_id or not user.has_ynab_token():
            return None

        try:
            ynab_repo = self._ynab_factory.get_repository(user)
            budgets = ynab_repo.get_budgets()
            budget = next((item for item in budgets if item.id == user.budget_id), None)
            return budget.name if budget else None
        except Exception:
            return None

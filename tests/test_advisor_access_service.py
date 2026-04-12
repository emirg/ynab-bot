from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from application.services.advisor_access_service import AdvisorAccessService
from domain.models.advisor_auth import AdvisorLaunchToken, AdvisorSession
from domain.models.user import UserConfiguration, UserStatus
from infrastructure.config.app_config import AppConfig


def _config() -> AppConfig:
    return AppConfig(
        telegram_token="tg",
        openai_key="openai",
        admin_ids=[1],
        ynab_client_id="cid",
        ynab_client_secret="secret",
        ynab_redirect_uri="https://bot.example.com/oauth/callback",
        token_encryption_key="k",
        http_api_key="http-key",
    )


@pytest.fixture
def service():
    advisor_repo = MagicMock()
    user_repo = MagicMock()
    learning_repo = MagicMock()
    return AdvisorAccessService(_config(), advisor_repo, user_repo, learning_repo), advisor_repo, user_repo, learning_repo


def test_create_launch_url_persists_hashed_launch_token(service):
    advisor_service, advisor_repo, _, _ = service

    url = advisor_service.create_launch_url(123)

    assert url.startswith("https://bot.example.com/advisor/launch?token=")
    token = advisor_repo.create_launch_token.call_args.args[0]
    assert token.telegram_id == 123
    assert "token=" in url
    assert len(token.token_hash) == 64


def test_exchange_launch_token_creates_session(service):
    advisor_service, advisor_repo, _, _ = service
    launch = AdvisorLaunchToken(
        telegram_id=123,
        token_hash="hash",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    advisor_repo.consume_launch_token.return_value = launch

    session_token = advisor_service.exchange_launch_token("raw-token")

    assert session_token
    persisted_session = advisor_repo.create_session.call_args.args[0]
    assert isinstance(persisted_session, AdvisorSession)
    assert persisted_session.telegram_id == 123


def test_get_session_telegram_id_deletes_expired_session(service):
    advisor_service, advisor_repo, _, _ = service
    advisor_repo.find_session.return_value = AdvisorSession(
        telegram_id=123,
        token_hash="hashed",
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    assert advisor_service.get_session_telegram_id("raw-session") is None
    advisor_repo.delete_session.assert_called_once()


def test_bootstrap_payload_reports_ready_when_recent_activity_exists(service):
    advisor_service, _, user_repo, learning_repo = service
    user_repo.find_by_telegram_id.return_value = UserConfiguration(
        telegram_id=123,
        status=UserStatus.AUTHORIZED,
        budget_id="budget-1",
        default_account_id="acc-1",
        default_account_name="Cuenta principal",
        first_name="Test",
        ynab_access_token="token",
    )
    learning_repo.get_recent_transactions.return_value = [{"payee": "Carulla"}]

    payload = advisor_service.get_bootstrap_payload(123)

    assert payload["advisor_state"] == "ready"
    assert payload["user"]["display_name"] == "Test"


def test_bootstrap_payload_reports_needs_budget_when_missing(service):
    advisor_service, _, user_repo, _ = service
    user_repo.find_by_telegram_id.return_value = UserConfiguration(
        telegram_id=123,
        status=UserStatus.AUTHORIZED,
        ynab_access_token="token",
    )

    payload = advisor_service.get_bootstrap_payload(123)

    assert payload["advisor_state"] == "needs_budget"
    assert payload["onboarding_state"] == "needs_budget"

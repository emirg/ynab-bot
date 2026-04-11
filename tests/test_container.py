"""Tests for DIContainer — service registration and convenience methods."""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from infrastructure.config.app_config import AppConfig
from infrastructure.container import DIContainer
from application.services.weekly_summary_service import WeeklySummaryService


@pytest.fixture
def container(tmp_path):
    """Build a real DIContainer backed by a temp database."""
    db_path = str(tmp_path / "test_container.db")
    config = AppConfig(
        telegram_token="tg-token",
        openai_key="openai-key",
        admin_ids=[111],
        ynab_client_id="cid",
        ynab_client_secret="cs",
        ynab_redirect_uri="http://localhost/cb",
        # A valid 32-byte url-safe base64 Fernet key (required by TokenEncryptor)
        token_encryption_key="aTULl7SBg8iYq9Kof_vgaC8GdG25-ryXic46AotyOQs=",
        http_api_key="http-key",
        database_path=db_path,
    )
    return DIContainer(config)


class TestWeeklySummaryServiceRegistration:

    def test_get_weekly_summary_service_returns_instance(self, container):
        service = container.get_weekly_summary_service()
        assert isinstance(service, WeeklySummaryService)

    def test_get_weekly_summary_service_is_transient(self, container):
        """Each call returns a new instance (transient, not singleton)."""
        svc1 = container.get_weekly_summary_service()
        svc2 = container.get_weekly_summary_service()
        assert svc1 is not svc2

    def test_weekly_summary_service_has_correct_dependencies(self, container):
        """Service receives ynab_factory and user_repository via DI."""
        from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory
        from infrastructure.repositories.sqlite_user_repository import SQLiteUserRepository

        service = container.get_weekly_summary_service()
        assert isinstance(service.ynab_factory, YNABRepositoryFactory)
        assert isinstance(service.user_repository, SQLiteUserRepository)

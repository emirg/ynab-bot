"""Tests for DIContainer — service registration and convenience methods."""

import pytest

from infrastructure.config.app_config import AppConfig
from infrastructure.container import DIContainer
from application.services.weekly_summary_service import WeeklySummaryService
from domain.repositories.user_repository import UserRepository


@pytest.fixture
def container(tmp_path, monkeypatch):
    """Build a DIContainer against the PostgreSQL runtime path."""
    from infrastructure.repositories.postgres_manager import PostgresDatabaseManager

    monkeypatch.setattr(PostgresDatabaseManager, "initialize_schema", lambda self: None)
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
        postgres_dsn="postgresql://ynab:ynab@localhost:5432/ynab_bot",
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
        from infrastructure.repositories.postgres_user_repository import PostgresUserRepository

        service = container.get_weekly_summary_service()
        assert isinstance(service.ynab_factory, YNABRepositoryFactory)
        assert isinstance(service.user_repository, PostgresUserRepository)

    def test_user_repository_interface_is_registered(self, container):
        repo = container.get(UserRepository)
        assert repo is container.get_user_repository()

    def test_registers_postgres_user_repository(self, tmp_path, monkeypatch):
        from infrastructure.repositories.postgres_manager import PostgresDatabaseManager
        from infrastructure.repositories.postgres_user_repository import PostgresUserRepository

        monkeypatch.setattr(PostgresDatabaseManager, "initialize_schema", lambda self: None)

        config = AppConfig(
            telegram_token="tg-token",
            openai_key="openai-key",
            admin_ids=[111],
            ynab_client_id="cid",
            ynab_client_secret="cs",
            ynab_redirect_uri="http://localhost/cb",
            token_encryption_key="aTULl7SBg8iYq9Kof_vgaC8GdG25-ryXic46AotyOQs=",
            http_api_key="http-key",
            postgres_dsn="postgresql://ynab:ynab@localhost:5432/ynab_bot",
        )

        container = DIContainer(config)
        repo = container.get_user_repository()

        assert isinstance(repo, PostgresUserRepository)

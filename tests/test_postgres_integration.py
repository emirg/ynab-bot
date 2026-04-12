from __future__ import annotations

import os

import pytest

from infrastructure.repositories.postgres_manager import PostgresDatabaseManager


pytestmark = pytest.mark.integration


def test_postgres_schema_initializes_when_dsn_is_provided():
    dsn = os.getenv("POSTGRES_INTEGRATION_DSN")
    if not dsn:
        pytest.skip("POSTGRES_INTEGRATION_DSN is not set")

    manager = PostgresDatabaseManager(dsn)
    manager.initialize_schema()

    assert manager.get_current_version() >= 1
    manager.close()

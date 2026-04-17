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

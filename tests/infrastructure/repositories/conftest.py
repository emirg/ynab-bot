import pytest


@pytest.fixture
def tmp_json_file(tmp_path):
    return str(tmp_path / "learning_data.json")


@pytest.fixture
def tmp_db_file(tmp_path):
    return str(tmp_path / "test_users.db")

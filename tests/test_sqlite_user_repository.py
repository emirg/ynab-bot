"""Tests for SQLiteUserRepository."""
import pytest
from datetime import datetime

from infrastructure.repositories.sqlite_user_repository import SQLiteUserRepository
from domain.models.user import UserConfiguration, UserStatus


@pytest.fixture
def repo(tmp_db_file):
    r = SQLiteUserRepository(tmp_db_file)
    yield r
    r.close()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:

    def test_creates_database(self, tmp_db_file):
        repo = SQLiteUserRepository(tmp_db_file)
        import os
        assert os.path.exists(tmp_db_file)
        repo.close()

    def test_creates_directory(self, tmp_path):
        db_path = str(tmp_path / 'subdir' / 'users.db')
        repo = SQLiteUserRepository(db_path)
        import os
        assert os.path.exists(db_path)
        repo.close()

    def test_idempotent_init(self, tmp_db_file):
        repo1 = SQLiteUserRepository(tmp_db_file)
        repo2 = SQLiteUserRepository(tmp_db_file)  # should not raise
        repo1.close()
        repo2.close()


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

class TestSaveAndFind:

    def test_save_and_find_by_telegram_id(self, repo, authorized_user):
        repo.save(authorized_user)
        found = repo.find_by_telegram_id(authorized_user.telegram_id)
        assert found is not None
        assert found.telegram_id == authorized_user.telegram_id
        assert found.status == UserStatus.AUTHORIZED
        assert found.budget_id == authorized_user.budget_id

    def test_find_nonexistent_returns_none(self, repo):
        assert repo.find_by_telegram_id(999999) is None

    def test_find_by_id_string(self, repo, authorized_user):
        repo.save(authorized_user)
        found = repo.find_by_id(str(authorized_user.telegram_id))
        assert found is not None

    def test_find_by_id_invalid_string(self, repo):
        assert repo.find_by_id('not-a-number') is None

    def test_save_updates_existing(self, repo, authorized_user):
        repo.save(authorized_user)
        authorized_user.budget_id = 'new-budget'
        repo.save(authorized_user)
        found = repo.find_by_telegram_id(authorized_user.telegram_id)
        assert found.budget_id == 'new-budget'

    def test_save_preserves_all_fields(self, repo):
        user = UserConfiguration(
            telegram_id=42,
            status=UserStatus.AUTHORIZED,
            budget_id='b1',
            default_account_id='a1',
            default_account_name='Nu Card',
            username='testuser',
            first_name='Test',
            last_name='User',
            approved_at=datetime(2026, 1, 1),
            approved_by=100,
        )
        repo.save(user)
        found = repo.find_by_telegram_id(42)
        assert found.username == 'testuser'
        assert found.default_account_name == 'Nu Card'
        assert found.approved_by == 100
        assert found.approved_at is not None


class TestDelete:

    def test_delete_existing(self, repo, authorized_user):
        repo.save(authorized_user)
        assert repo.delete(str(authorized_user.telegram_id))
        assert repo.find_by_telegram_id(authorized_user.telegram_id) is None

    def test_delete_nonexistent(self, repo):
        assert not repo.delete('999999')


# ---------------------------------------------------------------------------
# Query methods
# ---------------------------------------------------------------------------

class TestFindByStatus:

    def test_find_by_status(self, repo, authorized_user, pending_user, blocked_user):
        repo.save(authorized_user)
        repo.save(pending_user)
        repo.save(blocked_user)

        authorized = repo.find_by_status(UserStatus.AUTHORIZED)
        pending = repo.find_by_status(UserStatus.PENDING)
        blocked = repo.find_by_status(UserStatus.BLOCKED)

        assert len(authorized) == 1
        assert len(pending) == 1
        assert len(blocked) == 1
        assert authorized[0].telegram_id == authorized_user.telegram_id

    def test_find_by_status_empty(self, repo):
        assert repo.find_by_status(UserStatus.BLOCKED) == []


class TestFindAll:

    def test_find_all(self, repo, authorized_user, pending_user):
        repo.save(authorized_user)
        repo.save(pending_user)
        all_users = repo.find_all()
        assert len(all_users) == 2

    def test_find_all_empty(self, repo):
        assert repo.find_all() == []


class TestSaveByTelegramId:

    def test_calls_through(self, repo, authorized_user):
        result = repo.save_by_telegram_id(authorized_user)
        assert result.telegram_id == authorized_user.telegram_id
        found = repo.find_by_telegram_id(authorized_user.telegram_id)
        assert found is not None

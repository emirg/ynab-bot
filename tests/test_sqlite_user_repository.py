"""Tests for SQLiteUserRepository."""
import pytest
from datetime import datetime

from infrastructure.repositories.database_manager import DatabaseManager
from infrastructure.repositories.sqlite_user_repository import SQLiteUserRepository
from domain.models.user import UserConfiguration, UserStatus
from domain.time_utils import DEFAULT_TIMEZONE
from domain.exceptions import YNABBotException


@pytest.fixture
def db_manager(tmp_db_file):
    mgr = DatabaseManager(tmp_db_file)
    yield mgr
    mgr.close()


@pytest.fixture
def repo(db_manager):
    return SQLiteUserRepository(db_manager)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:

    def test_creates_database(self, tmp_db_file):
        mgr = DatabaseManager(tmp_db_file)
        import os
        assert os.path.exists(tmp_db_file)
        mgr.close()

    def test_creates_directory(self, tmp_path):
        db_path = str(tmp_path / 'subdir' / 'users.db')
        mgr = DatabaseManager(db_path)
        import os
        assert os.path.exists(db_path)
        mgr.close()

    def test_idempotent_init(self, tmp_db_file):
        mgr1 = DatabaseManager(tmp_db_file)
        mgr2 = DatabaseManager(tmp_db_file)  # should not raise
        mgr1.close()
        mgr2.close()


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

    def test_upsert_preserves_created_at(self, repo, authorized_user):
        repo.save(authorized_user)
        original = repo.find_by_telegram_id(authorized_user.telegram_id)
        original_created = original.created_at

        authorized_user.budget_id = 'changed'
        repo.save(authorized_user)
        updated = repo.find_by_telegram_id(authorized_user.telegram_id)
        assert updated.created_at == original_created
        assert updated.budget_id == 'changed'


class TestDelete:

    def test_delete_existing(self, repo, authorized_user):
        repo.save(authorized_user)
        assert repo.delete(authorized_user.telegram_id)
        assert repo.find_by_telegram_id(authorized_user.telegram_id) is None

    def test_delete_nonexistent(self, repo):
        assert not repo.delete(999999)


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


# ---------------------------------------------------------------------------
# Timezone persistence
# ---------------------------------------------------------------------------

class TestTimezonePersistence:

    def test_save_and_load_timezone(self, repo):
        user = UserConfiguration(telegram_id=42, timezone="America/Bogota")
        repo.save(user)
        found = repo.find_by_telegram_id(42)
        assert found.timezone == "America/Bogota"

    def test_default_timezone_on_load(self, repo):
        user = UserConfiguration(telegram_id=43)
        repo.save(user)
        found = repo.find_by_telegram_id(43)
        assert found.timezone == DEFAULT_TIMEZONE

    def test_update_timezone_persists(self, repo):
        user = UserConfiguration(telegram_id=44)
        repo.save(user)
        user.update_timezone("Europe/Madrid")
        repo.save(user)
        found = repo.find_by_telegram_id(44)
        assert found.timezone == "Europe/Madrid"

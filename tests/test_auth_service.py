"""Tests for domain AuthorizationService."""
import pytest
from unittest.mock import MagicMock

from domain.services.auth_service import AuthorizationService
from domain.models.user import UserConfiguration, UserStatus


@pytest.fixture
def auth_service(mock_user_repository):
    return AuthorizationService(
        user_repository=mock_user_repository,
        admin_ids=[100, 200],
    )


class TestIsAdmin:

    def test_admin_id(self, auth_service):
        assert auth_service.is_admin(100)
        assert auth_service.is_admin(200)

    def test_non_admin_id(self, auth_service):
        assert not auth_service.is_admin(999)


class TestRegisterUser:

    def test_new_user_is_pending(self, auth_service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        telegram_user = MagicMock(id=999, username='new', first_name='New', last_name='User')

        result = auth_service.register_user(telegram_user)
        assert result.status == UserStatus.PENDING
        mock_user_repository.save.assert_called_once()

    def test_new_admin_is_auto_authorized(self, auth_service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        telegram_user = MagicMock(id=100, username='admin', first_name='Admin', last_name='User')

        result = auth_service.register_user(telegram_user)
        assert result.status == UserStatus.AUTHORIZED
        assert result.approved_by == 100

    def test_existing_user_updates_profile(self, auth_service, mock_user_repository, pending_user):
        mock_user_repository.find_by_telegram_id.return_value = pending_user
        telegram_user = MagicMock(id=pending_user.telegram_id, username='updated', first_name='Updated', last_name='Name')

        result = auth_service.register_user(telegram_user)
        assert result.username == 'updated'
        mock_user_repository.save.assert_called_once()


class TestAuthorizeUser:

    def test_authorize_pending_user(self, auth_service, mock_user_repository, pending_user):
        mock_user_repository.find_by_telegram_id.return_value = pending_user
        assert auth_service.authorize_user(pending_user.telegram_id, admin_id=100)
        assert pending_user.is_authorized()
        mock_user_repository.save.assert_called_once()

    def test_authorize_by_non_admin_fails(self, auth_service, mock_user_repository, pending_user):
        mock_user_repository.find_by_telegram_id.return_value = pending_user
        assert not auth_service.authorize_user(pending_user.telegram_id, admin_id=999)

    def test_authorize_nonexistent_user_fails(self, auth_service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        assert not auth_service.authorize_user(999, admin_id=100)


class TestBlockUser:

    def test_block_user(self, auth_service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        assert auth_service.block_user(authorized_user.telegram_id, admin_id=100)
        assert authorized_user.is_blocked()

    def test_block_by_non_admin_fails(self, auth_service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        assert not auth_service.block_user(authorized_user.telegram_id, admin_id=999)

    def test_block_nonexistent_user_fails(self, auth_service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        assert not auth_service.block_user(999, admin_id=100)


class TestGetUserStatus:

    def test_authorized(self, auth_service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        assert auth_service.get_user_status(authorized_user.telegram_id) == UserStatus.AUTHORIZED

    def test_nonexistent(self, auth_service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        assert auth_service.get_user_status(999) is None


class TestIsAuthorized:

    def test_authorized_user(self, auth_service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        assert auth_service.is_authorized(authorized_user.telegram_id)

    def test_pending_user(self, auth_service, mock_user_repository, pending_user):
        mock_user_repository.find_by_telegram_id.return_value = pending_user
        assert not auth_service.is_authorized(pending_user.telegram_id)

    def test_nonexistent_user(self, auth_service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        assert not auth_service.is_authorized(999)


class TestUserLists:

    def test_get_pending_users(self, auth_service, mock_user_repository, pending_user):
        mock_user_repository.find_by_status.return_value = [pending_user]
        result = auth_service.get_pending_users()
        assert len(result) == 1
        mock_user_repository.find_by_status.assert_called_with(UserStatus.PENDING)

    def test_get_all_users(self, auth_service, mock_user_repository, authorized_user, pending_user):
        mock_user_repository.find_all.return_value = [authorized_user, pending_user]
        assert len(auth_service.get_all_users()) == 2

    def test_get_authorized_users(self, auth_service, mock_user_repository):
        auth_service.get_authorized_users()
        mock_user_repository.find_by_status.assert_called_with(UserStatus.AUTHORIZED)

    def test_get_blocked_users(self, auth_service, mock_user_repository):
        auth_service.get_blocked_users()
        mock_user_repository.find_by_status.assert_called_with(UserStatus.BLOCKED)

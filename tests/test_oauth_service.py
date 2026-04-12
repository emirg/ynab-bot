"""Tests for YNABOAuthService."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from application.services.oauth_service import YNABOAuthService
from domain.models.user import UserConfiguration, UserStatus
from domain.exceptions import OAuthException, TokenExpiredException, YNABApiException
from infrastructure.config.app_config import AppConfig
from infrastructure.http_client import ResilientHTTPClient


@pytest.fixture
def config():
    return AppConfig(
        telegram_token='tg',
        openai_key='ok',
        admin_ids=[1],
        ynab_client_id='test-client-id',
        ynab_client_secret='test-secret',
        ynab_redirect_uri='https://example.com/oauth/callback',
        token_encryption_key='k',
        http_api_key='http-key',
    )


@pytest.fixture
def mock_http_client():
    return MagicMock(spec=ResilientHTTPClient)


@pytest.fixture
def service(config, mock_user_repository, mock_http_client):
    return YNABOAuthService(
        config=config,
        user_repository=mock_user_repository,
        http_client=mock_http_client,
    )


@pytest.fixture
def user_with_token():
    return UserConfiguration(
        telegram_id=123,
        status=UserStatus.AUTHORIZED,
        ynab_access_token='access-tok',
        ynab_refresh_token='refresh-tok',
        ynab_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def user_with_expired_token():
    return UserConfiguration(
        telegram_id=123,
        status=UserStatus.AUTHORIZED,
        ynab_access_token='old-access',
        ynab_refresh_token='refresh-tok',
        ynab_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )


def _mock_token_response(mock_http_client, access_token='new-access', refresh_token='new-refresh', expires_in=7200):
    """Helper to configure the mock HTTP client to return a successful token response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': expires_in,
    }
    mock_resp.raise_for_status.return_value = None
    mock_http_client.post.return_value = mock_resp
    return mock_resp


class TestGenerateAuthUrl:
    def test_contains_client_id(self, service):
        url = service.generate_auth_url(123)
        assert 'client_id=test-client-id' in url

    def test_contains_redirect_uri(self, service):
        url = service.generate_auth_url(123)
        assert 'redirect_uri=' in url

    def test_contains_state(self, service):
        url = service.generate_auth_url(123)
        assert 'state=123.' in url

    def test_response_type_code(self, service):
        url = service.generate_auth_url(123)
        assert 'response_type=code' in url


class TestStateSigningVerification:
    def test_sign_and_verify_roundtrip(self, service):
        state = service._sign_state(456)
        result = service._verify_state(state)
        assert result == 456

    def test_invalid_state_format(self, service):
        with pytest.raises(OAuthException):
            service._verify_state('invalid')

    def test_tampered_signature(self, service):
        state = service._sign_state(123)
        tampered = state[:-4] + 'xxxx'
        with pytest.raises(OAuthException):
            service._verify_state(tampered)

    def test_tampered_user_id(self, service):
        state = service._sign_state(123)
        sig = state.split('.', 1)[1]
        tampered = f"999.{sig}"
        with pytest.raises(OAuthException):
            service._verify_state(tampered)


class TestExchangeCodeForTokens:
    def test_success(self, service, mock_http_client, mock_user_repository):
        user = UserConfiguration(telegram_id=123, status=UserStatus.AUTHORIZED)
        mock_user_repository.find_by_telegram_id.return_value = user
        _mock_token_response(mock_http_client)

        state = service._sign_state(123)
        result = service.exchange_code_for_tokens('auth-code', state)

        assert result.ynab_access_token == 'new-access'
        assert result.ynab_refresh_token == 'new-refresh'
        mock_user_repository.save.assert_called_once()
        mock_http_client.post.assert_called_once_with(
            '/oauth/token',
            data={
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'redirect_uri': 'https://example.com/oauth/callback',
                'grant_type': 'authorization_code',
                'code': 'auth-code',
            },
        )

    def test_user_not_found(self, service, mock_http_client, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        _mock_token_response(mock_http_client, access_token='a', refresh_token='r', expires_in=3600)

        state = service._sign_state(123)
        with pytest.raises(OAuthException, match="no encontrado"):
            service.exchange_code_for_tokens('code', state)

    def test_all_retries_fail_raises_oauth_exception(self, service, mock_http_client, mock_user_repository):
        """When the HTTP client exhausts retries and raises YNABApiException, OAuthException is raised."""
        mock_http_client.post.side_effect = YNABApiException(
            "HTTP 500 after 2 retries", status_code=500, response_body="error"
        )

        state = service._sign_state(123)
        with pytest.raises(OAuthException, match="Error en la solicitud OAuth"):
            service.exchange_code_for_tokens('auth-code', state)

    def test_transient_failure_then_success(self, service, mock_http_client, mock_user_repository):
        """Simulates the HTTP client handling a transient failure internally and returning success."""
        user = UserConfiguration(telegram_id=123, status=UserStatus.AUTHORIZED)
        mock_user_repository.find_by_telegram_id.return_value = user

        # The ResilientHTTPClient handles retries internally — when it succeeds, it returns a response.
        # Here we simulate that behavior: the client's post() returns successfully after internal retries.
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'access_token': 'retried-access',
            'refresh_token': 'retried-refresh',
            'expires_in': 7200,
        }
        mock_resp.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_resp

        state = service._sign_state(123)
        result = service.exchange_code_for_tokens('auth-code', state)

        assert result.ynab_access_token == 'retried-access'
        mock_http_client.post.assert_called_once()


class TestRefreshTokenIfNeeded:
    def test_not_expired_returns_unchanged(self, service, user_with_token):
        result = service.refresh_token_if_needed(user_with_token)
        assert result.ynab_access_token == 'access-tok'

    def test_no_token_raises(self, service):
        user = UserConfiguration(telegram_id=123)
        with pytest.raises(OAuthException):
            service.refresh_token_if_needed(user)

    def test_expired_no_refresh_token_raises(self, service):
        user = UserConfiguration(
            telegram_id=123,
            ynab_access_token='tok',
            ynab_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        with pytest.raises(TokenExpiredException):
            service.refresh_token_if_needed(user)

    def test_expired_refreshes(self, service, mock_http_client, mock_user_repository, user_with_expired_token):
        mock_user_repository.find_by_telegram_id.return_value = user_with_expired_token
        _mock_token_response(mock_http_client, access_token='refreshed-access', refresh_token='refreshed-refresh')

        result = service.refresh_token_if_needed(user_with_expired_token)
        assert result.ynab_access_token == 'refreshed-access'
        mock_user_repository.save.assert_called_once()

    def test_refresh_all_retries_fail_raises_oauth_exception(
        self, service, mock_http_client, user_with_expired_token
    ):
        """YNABApiException from exhausted retries becomes OAuthException."""
        mock_http_client.post.side_effect = YNABApiException(
            "Network error after 2 retries", status_code=None, response_body=None
        )
        with pytest.raises(OAuthException, match="Error en la solicitud OAuth"):
            service.refresh_token_if_needed(user_with_expired_token)


class TestGetValidAccessToken:
    def test_returns_token(self, service, user_with_token):
        token = service.get_valid_access_token(user_with_token)
        assert token == 'access-tok'


class TestDisconnectUser:
    def test_success(self, service, mock_user_repository, user_with_token):
        mock_user_repository.find_by_telegram_id.return_value = user_with_token
        result = service.disconnect_user(123)
        assert result is True
        assert user_with_token.ynab_access_token is None
        assert user_with_token.budget_id is None
        mock_user_repository.save.assert_called_once()

    def test_user_not_found(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.disconnect_user(999)
        assert result is False


class TestDefaultHttpClientCreation:
    def test_default_client_created_when_not_injected(self, config, mock_user_repository):
        """When no http_client is passed, a default ResilientHTTPClient is created."""
        svc = YNABOAuthService(config=config, user_repository=mock_user_repository)
        assert isinstance(svc._http_client, ResilientHTTPClient)

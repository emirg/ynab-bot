import hashlib
import hmac
import logging
from typing import Optional
from urllib.parse import urlencode

from domain.exceptions import OAuthException, TokenExpiredException, YNABApiException
from domain.models.user import UserConfiguration
from domain.repositories.user_repository import UserRepository
from infrastructure.config.app_config import AppConfig
from infrastructure.http_client import ResilientHTTPClient

logger = logging.getLogger(__name__)

_AUTHORIZE_URL = "https://app.ynab.com/oauth/authorize"
_TOKEN_URL = "https://app.ynab.com/oauth/token"
_OAUTH_BASE_URL = "https://app.ynab.com"
_TOKEN_PATH = "/oauth/token"


class YNABOAuthService:
    def __init__(
        self,
        config: AppConfig,
        user_repository: UserRepository,
        http_client: Optional[ResilientHTTPClient] = None,
    ):
        self.config = config
        self.user_repository = user_repository
        self._http_client = http_client or ResilientHTTPClient(
            base_url=_OAUTH_BASE_URL,
            max_retries=2,
            timeout=30,
        )

    def generate_auth_url(self, telegram_user_id: int) -> str:
        state = self._sign_state(telegram_user_id)
        params = {
            "client_id": self.config.ynab_client_id,
            "redirect_uri": self.config.ynab_redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(self, code: str, state: str) -> UserConfiguration:
        telegram_user_id = self._verify_state(state)

        data = {
            "client_id": self.config.ynab_client_id,
            "client_secret": self.config.ynab_client_secret,
            "redirect_uri": self.config.ynab_redirect_uri,
            "grant_type": "authorization_code",
            "code": code,
        }
        token_data = self._request_token(data)

        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user_config:
            raise OAuthException(f"Usuario {telegram_user_id} no encontrado")

        user_config.update_ynab_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in_seconds=token_data["expires_in"],
        )
        self.user_repository.save(user_config)
        logger.info(f"OAuth tokens stored for user {telegram_user_id}")
        return user_config

    def refresh_token_if_needed(self, user_config: UserConfiguration) -> UserConfiguration:
        if not user_config.has_ynab_token():
            raise OAuthException("Usuario no tiene token YNAB")

        if not user_config.is_token_expired():
            return user_config

        if not user_config.ynab_refresh_token:
            raise TokenExpiredException()

        data = {
            "client_id": self.config.ynab_client_id,
            "client_secret": self.config.ynab_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": user_config.ynab_refresh_token,
        }
        token_data = self._request_token(data)

        user_config.update_ynab_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in_seconds=token_data["expires_in"],
        )
        self.user_repository.save(user_config)
        logger.info(f"OAuth token refreshed for user {user_config.telegram_id}")
        return user_config

    def get_valid_access_token(self, user_config: UserConfiguration) -> str:
        user_config = self.refresh_token_if_needed(user_config)
        return user_config.ynab_access_token

    def disconnect_user(self, telegram_user_id: int) -> bool:
        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user_config:
            return False

        user_config.clear_ynab_tokens()
        user_config.budget_id = None
        user_config.default_account_id = None
        user_config.default_account_name = None
        self.user_repository.save(user_config)
        logger.info(f"OAuth disconnected for user {telegram_user_id}")
        return True

    def _request_token(self, data: dict) -> dict:
        try:
            resp = self._http_client.post(_TOKEN_PATH, data=data)
            resp.raise_for_status()
            return resp.json()
        except YNABApiException as e:
            logger.error(f"OAuth token request failed after retries: {e}")
            raise OAuthException(f"Error en la solicitud OAuth: {e}")

    def _sign_state(self, telegram_user_id: int) -> str:
        sig = hmac.new(
            self.config.ynab_client_secret.encode(),
            str(telegram_user_id).encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{telegram_user_id}.{sig}"

    def _verify_state(self, state: str) -> int:
        try:
            user_id_str, sig = state.rsplit(".", 1)
            telegram_user_id = int(user_id_str)
        except (ValueError, AttributeError):
            raise OAuthException("State OAuth inválido")

        expected_sig = hmac.new(
            self.config.ynab_client_secret.encode(),
            user_id_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            raise OAuthException("Firma de state OAuth inválida")

        return telegram_user_id

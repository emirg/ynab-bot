import os
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlsplit
from dotenv import load_dotenv

from domain.exceptions import ConfigurationException

# Compute once: infrastructure/config/ -> infrastructure/ -> src/ -> project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


@dataclass
class AppConfig:
    """Application configuration from environment variables"""
    telegram_token: Optional[str]
    openai_key: Optional[str]
    admin_ids: List[int]
    ynab_client_id: Optional[str]
    ynab_client_secret: Optional[str]
    ynab_redirect_uri: Optional[str]
    token_encryption_key: str
    http_api_key: str
    advisor_base_url: Optional[str] = None
    persistence_backend: str = 'postgres'
    postgres_dsn: Optional[str] = None
    app_mode: str = 'full'
    external_mode: str = 'live'
    dev_api_key: str = 'dev-api-key'
    enable_dev_routes: bool = False
    default_budget_id: Optional[str] = None
    database_path: str = 'data/users.db'
    log_level: str = 'INFO'

    @classmethod
    def from_env(cls, env_path: str = 'config/.env') -> 'AppConfig':
        """Load configuration from environment file"""
        # Get absolute path relative to project root
        if not os.path.isabs(env_path):
            env_path = os.path.join(_PROJECT_ROOT, env_path)

        load_dotenv(env_path)

        app_mode = os.getenv('APP_MODE', 'full').strip().lower()
        cls._validate_app_mode(app_mode)
        external_mode = os.getenv('EXTERNAL_MODE', cls._default_external_mode(app_mode)).strip().lower()
        cls._validate_external_mode(external_mode)
        persistence_backend = os.getenv('PERSISTENCE_BACKEND', 'postgres').strip().lower()
        cls._validate_persistence_backend(persistence_backend)

        return cls(
            telegram_token=cls._optional_env('TELEGRAM_BOT_TOKEN'),
            openai_key=cls._optional_env('OPENAI_API_KEY'),
            admin_ids=cls._parse_admin_ids(
                os.getenv('ADMIN_IDS', ''),
                allow_default=app_mode in {'http-dev', 'test'},
            ),
            ynab_client_id=cls._optional_env('YNAB_CLIENT_ID'),
            ynab_client_secret=cls._optional_env('YNAB_CLIENT_SECRET'),
            ynab_redirect_uri=cls._optional_env('YNAB_REDIRECT_URI'),
            token_encryption_key=cls._require_env('TOKEN_ENCRYPTION_KEY'),
            http_api_key=cls._resolve_http_api_key(app_mode),
            advisor_base_url=cls._optional_env('ADVISOR_BASE_URL'),
            persistence_backend=persistence_backend,
            postgres_dsn=cls._optional_env('POSTGRES_DSN'),
            app_mode=app_mode,
            external_mode=external_mode,
            dev_api_key=cls._resolve_dev_api_key(app_mode),
            enable_dev_routes=cls._parse_bool_env('ENABLE_DEV_ROUTES', default=False),
            default_budget_id=os.getenv('YNAB_BUDGET_ID'),
            database_path=os.getenv('DATABASE_PATH', 'data/users.db'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
        )._validate_runtime_requirements()

    @staticmethod
    def _require_env(key: str) -> str:
        """Get required environment variable or raise exception"""
        value = os.getenv(key)
        if not value:
            raise ConfigurationException(f"Required environment variable {key} is not set")
        return value

    @staticmethod
    def _optional_env(key: str) -> Optional[str]:
        """Get optional environment variable, normalizing blanks to None."""
        value = os.getenv(key)
        if value is None:
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _validate_app_mode(app_mode: str) -> None:
        allowed = {'full', 'http-dev', 'http-live', 'test'}
        if app_mode not in allowed:
            raise ConfigurationException(
                f"Invalid APP_MODE '{app_mode}'. Expected one of: {', '.join(sorted(allowed))}"
            )

    @staticmethod
    def _validate_external_mode(external_mode: str) -> None:
        allowed = {'live', 'stub'}
        if external_mode not in allowed:
            raise ConfigurationException(
                f"Invalid EXTERNAL_MODE '{external_mode}'. Expected one of: {', '.join(sorted(allowed))}"
            )

    @staticmethod
    def _validate_persistence_backend(persistence_backend: str) -> None:
        allowed = {'postgres'}
        if persistence_backend not in allowed:
            raise ConfigurationException(
                f"Invalid PERSISTENCE_BACKEND '{persistence_backend}'. Expected one of: {', '.join(sorted(allowed))}"
            )

    @staticmethod
    def _default_external_mode(app_mode: str) -> str:
        return 'stub' if app_mode in {'http-dev', 'test'} else 'live'

    @staticmethod
    def _resolve_http_api_key(app_mode: str) -> str:
        value = os.getenv('HTTP_API_KEY')
        if value:
            return value
        if app_mode in {'http-dev', 'test'}:
            return 'dev-http-key'
        raise ConfigurationException("Required environment variable HTTP_API_KEY is not set")

    @staticmethod
    def _resolve_dev_api_key(app_mode: str) -> str:
        value = os.getenv('DEV_API_KEY')
        if value:
            return value
        if app_mode == 'http-dev':
            raise ConfigurationException("Required environment variable DEV_API_KEY is not set")
        return 'dev-api-key'

    @staticmethod
    def _parse_bool_env(key: str, default: bool = False) -> bool:
        value = os.getenv(key)
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'off'}:
            return False
        raise ConfigurationException(
            f"Invalid boolean value for {key}: {value}. Use true/false."
        )

    @staticmethod
    def _parse_admin_ids(admin_ids_str: str, allow_default: bool = False) -> List[int]:
        """Parse comma-separated admin IDs from environment variable"""
        if not admin_ids_str.strip():
            if allow_default:
                return [1]
            raise ConfigurationException(
                "ADMIN_IDS environment variable is required. "
                "Set it to a comma-separated list of Telegram user IDs (e.g., '123456789,987654321')"
            )
        
        try:
            return [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
        except ValueError as e:
            raise ConfigurationException(
                f"Invalid ADMIN_IDS format: {admin_ids_str}. "
                f"Must be comma-separated integers (e.g., '123456789,987654321')"
            ) from e
    
    def get_absolute_path(self, relative_path: str) -> str:
        """Convert relative path to absolute path from project root"""
        if os.path.isabs(relative_path):
            return relative_path
        return os.path.join(_PROJECT_ROOT, relative_path)
    
    @property
    def database_absolute_path(self) -> str:
        """Get absolute path for database"""
        return self.get_absolute_path(self.database_path)

    @property
    def uses_postgres(self) -> bool:
        return self.persistence_backend == 'postgres'

    @property
    def resolved_advisor_base_url(self) -> str:
        if self.advisor_base_url:
            return self.advisor_base_url.rstrip('/')
        if self.ynab_redirect_uri:
            parsed = urlsplit(self.ynab_redirect_uri)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return 'http://localhost:8080'

    @property
    def telegram_enabled(self) -> bool:
        return self.app_mode == 'full'

    @property
    def dev_routes_enabled(self) -> bool:
        return self.app_mode == 'http-dev' and self.enable_dev_routes

    @property
    def use_live_integrations(self) -> bool:
        return self.external_mode == 'live'

    def _validate_runtime_requirements(self) -> 'AppConfig':
        if self.app_mode == 'http-dev' and (
            os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID')
        ):
            raise ConfigurationException("APP_MODE=http-dev is not allowed on Railway environments")

        if self.telegram_enabled and not self.telegram_token:
            raise ConfigurationException("Required environment variable TELEGRAM_BOT_TOKEN is not set")

        if self.use_live_integrations:
            for key, value in (
                ('OPENAI_API_KEY', self.openai_key),
                ('YNAB_CLIENT_ID', self.ynab_client_id),
                ('YNAB_CLIENT_SECRET', self.ynab_client_secret),
                ('YNAB_REDIRECT_URI', self.ynab_redirect_uri),
            ):
                if not value:
                    raise ConfigurationException(f"Required environment variable {key} is not set")

        if self.enable_dev_routes and self.app_mode != 'http-dev':
            raise ConfigurationException("ENABLE_DEV_ROUTES=true requires APP_MODE=http-dev")

        if self.uses_postgres and not self.postgres_dsn:
            raise ConfigurationException("PERSISTENCE_BACKEND=postgres requires POSTGRES_DSN")

        return self

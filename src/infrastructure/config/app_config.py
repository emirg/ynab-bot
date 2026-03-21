import os
from dataclasses import dataclass
from typing import Optional, List
from dotenv import load_dotenv

from domain.exceptions import ConfigurationException

# Compute once: infrastructure/config/ -> infrastructure/ -> src/ -> project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


@dataclass
class AppConfig:
    """Application configuration from environment variables"""
    telegram_token: str
    openai_key: str
    admin_ids: List[int]
    ynab_client_id: str
    ynab_client_secret: str
    ynab_redirect_uri: str
    token_encryption_key: str
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

        return cls(
            telegram_token=cls._require_env('TELEGRAM_BOT_TOKEN'),
            openai_key=cls._require_env('OPENAI_API_KEY'),
            admin_ids=cls._parse_admin_ids(os.getenv('ADMIN_IDS', '')),
            ynab_client_id=cls._require_env('YNAB_CLIENT_ID'),
            ynab_client_secret=cls._require_env('YNAB_CLIENT_SECRET'),
            ynab_redirect_uri=cls._require_env('YNAB_REDIRECT_URI'),
            token_encryption_key=cls._require_env('TOKEN_ENCRYPTION_KEY'),
            default_budget_id=os.getenv('YNAB_BUDGET_ID'),
            database_path=os.getenv('DATABASE_PATH', 'data/users.db'),
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )
    
    @staticmethod
    def _require_env(key: str) -> str:
        """Get required environment variable or raise exception"""
        value = os.getenv(key)
        if not value:
            raise ConfigurationException(f"Required environment variable {key} is not set")
        return value
    
    @staticmethod
    def _parse_admin_ids(admin_ids_str: str) -> List[int]:
        """Parse comma-separated admin IDs from environment variable"""
        if not admin_ids_str.strip():
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
    

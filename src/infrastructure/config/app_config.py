import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

from domain.exceptions import ConfigurationException


@dataclass
class AppConfig:
    """Application configuration from environment variables"""
    telegram_token: str
    ynab_token: str
    openai_key: str
    default_budget_id: Optional[str] = None
    database_path: str = 'data/users.db'
    learning_data_path: str = 'data/category_learning_data.json'
    log_level: str = 'INFO'
    
    @classmethod
    def from_env(cls, env_path: str = 'config/.env') -> 'AppConfig':
        """Load configuration from environment file"""
        # Get absolute path relative to project root
        if not os.path.isabs(env_path):
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            env_path = os.path.join(project_root, env_path)
        
        load_dotenv(env_path)
        
        return cls(
            telegram_token=cls._require_env('TELEGRAM_BOT_TOKEN'),
            ynab_token=cls._require_env('YNAB_ACCESS_TOKEN'),
            openai_key=cls._require_env('OPENAI_API_KEY'),
            default_budget_id=os.getenv('YNAB_BUDGET_ID'),
            database_path=os.getenv('DATABASE_PATH', 'data/users.db'),
            learning_data_path=os.getenv('LEARNING_DATA_PATH', 'data/category_learning_data.json'),
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )
    
    @staticmethod
    def _require_env(key: str) -> str:
        """Get required environment variable or raise exception"""
        value = os.getenv(key)
        if not value:
            raise ConfigurationException(f"Required environment variable {key} is not set")
        return value
    
    def get_absolute_path(self, relative_path: str) -> str:
        """Convert relative path to absolute path from project root"""
        if os.path.isabs(relative_path):
            return relative_path
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return os.path.join(project_root, relative_path)
    
    @property
    def database_absolute_path(self) -> str:
        """Get absolute path for database"""
        return self.get_absolute_path(self.database_path)
    
    @property
    def learning_data_absolute_path(self) -> str:
        """Get absolute path for learning data"""
        return self.get_absolute_path(self.learning_data_path)
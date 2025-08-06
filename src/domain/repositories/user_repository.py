from abc import abstractmethod
from typing import Optional
from domain.repositories.base import BaseRepository
from domain.models.user import UserConfiguration


class UserRepository(BaseRepository[UserConfiguration]):
    """Repository interface for user configuration"""
    
    @abstractmethod
    def find_by_telegram_id(self, telegram_id: int) -> Optional[UserConfiguration]:
        """Find user configuration by Telegram user ID"""
        pass
    
    @abstractmethod
    def save_by_telegram_id(self, user_config: UserConfiguration) -> UserConfiguration:
        """Save user configuration using telegram_id as key"""
        pass
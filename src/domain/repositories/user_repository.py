from abc import abstractmethod
from typing import Optional, List
from domain.repositories.base import BaseRepository
from domain.models.user import UserConfiguration, UserStatus


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
    
    @abstractmethod
    def find_by_status(self, status: UserStatus) -> List[UserConfiguration]:
        """Find all users with given status"""
        pass
    
    @abstractmethod
    def find_all(self) -> List[UserConfiguration]:
        """Find all users"""
        pass
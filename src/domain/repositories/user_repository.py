from abc import ABC, abstractmethod
from typing import Optional, List

from domain.models.user import UserConfiguration, UserStatus


class UserRepository(ABC):
    """Repository interface for user configuration"""

    @abstractmethod
    def save(self, user_config: UserConfiguration) -> UserConfiguration:
        """Save user configuration (insert or update)"""
        pass

    @abstractmethod
    def find_by_telegram_id(self, telegram_id: int) -> Optional[UserConfiguration]:
        """Find user configuration by Telegram user ID"""
        pass

    @abstractmethod
    def delete(self, telegram_id: int) -> bool:
        """Delete user configuration by Telegram user ID"""
        pass

    @abstractmethod
    def find_by_status(self, status: UserStatus) -> List[UserConfiguration]:
        """Find all users with given status"""
        pass

    @abstractmethod
    def find_all(self) -> List[UserConfiguration]:
        """Find all users"""
        pass

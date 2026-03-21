from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models.split_config import SplitGroup, SharedAccountConfig


class SplitConfigRepository(ABC):
    @abstractmethod
    def add_split_group(self, telegram_id: int, category_id: str, category_name: str) -> SplitGroup:
        """Adds a split group, or returns existing if category_id already exists for user"""
        pass

    @abstractmethod
    def remove_split_group(self, telegram_id: int, category_id: str) -> bool:
        """Removes a split group and all its aliases"""
        pass

    @abstractmethod
    def get_split_groups(self, telegram_id: int) -> List[SplitGroup]:
        """Gets all split groups for a user, including aliases"""
        pass

    @abstractmethod
    def find_split_group_by_alias(self, telegram_id: int, alias: str) -> Optional[SplitGroup]:
        """Find a group where alias matches (case-insensitive)"""
        pass

    @abstractmethod
    def add_person_alias(self, telegram_id: int, category_id: str, alias: str) -> bool:
        """Adds an alias to a split group"""
        pass

    @abstractmethod
    def remove_person_alias(self, telegram_id: int, category_id: str, alias: str) -> bool:
        """Removes an alias from a split group"""
        pass

    @abstractmethod
    def set_shared_account(self, telegram_id: int, account_id: str, account_name: str) -> SharedAccountConfig:
        """Sets the shared transactions account for a user (upsert)"""
        pass

    @abstractmethod
    def get_shared_account(self, telegram_id: int) -> Optional[SharedAccountConfig]:
        """Gets the shared account config for a user"""
        pass

    @abstractmethod
    def remove_shared_account(self, telegram_id: int) -> bool:
        """Removes the shared account config for a user"""
        pass

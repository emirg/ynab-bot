from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Base repository interface"""
    
    @abstractmethod
    def save(self, entity: T) -> T:
        """Save entity and return saved entity"""
        pass
    
    @abstractmethod
    def find_by_id(self, id: str) -> Optional[T]:
        """Find entity by ID"""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """Delete entity by ID"""
        pass
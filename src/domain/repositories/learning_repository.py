from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from domain.models.expense import Expense


class LearningRepository(ABC):
    """Repository interface for adaptive learning data"""
    
    @abstractmethod
    def record_successful_transaction(self, expense: Expense) -> None:
        """Record a successful transaction for learning"""
        pass
    
    @abstractmethod
    def predict_category(self, payee: str, categories: List[Dict]) -> Optional[Tuple[str, float]]:
        """Predict category for a payee, return (category_id, confidence)"""
        pass
    
    @abstractmethod
    def record_user_correction(self, payee: str, old_category_id: str, new_category_id: str) -> None:
        """Record a user correction for learning improvement"""
        pass
    
    @abstractmethod
    def get_learning_statistics(self) -> Dict:
        """Get learning system statistics"""
        pass
    
    @abstractmethod
    def add_recent_transaction(self, expense: Expense) -> None:
        """Add transaction to recent transactions for correction purposes"""
        pass
    
    @abstractmethod
    def get_recent_transactions(self, limit: int = 10) -> List[Dict]:
        """Get recent transactions for correction purposes"""
        pass
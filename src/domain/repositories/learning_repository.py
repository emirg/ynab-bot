from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from domain.models.expense import Expense


class LearningRepository(ABC):
    """Repository interface for adaptive learning data (per-user)"""

    @abstractmethod
    def record_successful_transaction(self, telegram_id: int, expense: Expense) -> None:
        """Record a successful transaction for learning"""
        pass

    @abstractmethod
    def predict_category(self, telegram_id: int, payee: str, categories: List[Dict]) -> Optional[Tuple[str, float, int]]:
        """Predict category for a payee, return (category_id, confidence, count)"""
        pass

    @abstractmethod
    def record_user_correction(self, telegram_id: int, payee: str, old_category_id: str, new_category_id: str, new_category_name: str = "") -> None:
        """Record a user correction for learning improvement"""
        pass

    @abstractmethod
    def get_learning_statistics(self, telegram_id: int) -> Dict:
        """Get learning system statistics for a user"""
        pass

    @abstractmethod
    def add_recent_transaction(self, telegram_id: int, expense: Expense, ynab_transaction_id: str = None) -> None:
        """Add transaction to recent transactions for correction purposes"""
        pass

    @abstractmethod
    def get_recent_transactions(self, telegram_id: int, limit: int = 10) -> List[Dict]:
        """Get recent transactions for correction purposes"""
        pass

    @abstractmethod
    def get_payee_associations(self, telegram_id: int) -> List[Dict]:
        """Get all payee-category associations for a user, ordered by count DESC"""
        pass

    @abstractmethod
    def delete_payee_associations(self, telegram_id: int, normalized_payee: str) -> int:
        """Delete all associations for a given payee for a user. Returns row count deleted."""
        pass

    @abstractmethod
    def decrement_learning(self, telegram_id: int, payee: str, category_id: str) -> None:
        """Decrement the learning count for a payee-category mapping. Deletes row if count reaches 0."""
        pass

    @abstractmethod
    def delete_recent_transaction(self, telegram_id: int, ynab_transaction_id: str) -> bool:
        """Delete a recent transaction by ynab_transaction_id for a specific user. Returns True if deleted."""
        pass

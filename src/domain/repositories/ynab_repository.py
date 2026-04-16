from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models.expense import Expense
from domain.models.user import YNABBudget, YNABAccount, YNABCategory, YNABPayee


class YNABRepository(ABC):
    """Repository interface for YNAB operations"""
    
    @abstractmethod
    def get_budgets(self) -> List[YNABBudget]:
        """Get all available budgets"""
        pass
    
    @abstractmethod
    def get_accounts(self, budget_id: str) -> List[YNABAccount]:
        """Get all accounts for a budget"""
        pass
    
    @abstractmethod
    def get_categories(self, budget_id: str) -> List[YNABCategory]:
        """Get all categories for a budget"""
        pass
    
    @abstractmethod
    def get_payees(self, budget_id: str) -> List[YNABPayee]:
        """Get all payees for a budget"""
        pass

    @abstractmethod
    def create_transaction(self, expense: Expense, budget_id: str, account_id: str) -> Optional[str]:
        """Create transaction and return transaction ID if successful"""
        pass

    @abstractmethod
    def update_transaction_category(self, budget_id: str, transaction_id: str, category_id: str) -> bool:
        """Update the category of an existing transaction. Returns True on success."""
        pass

    @abstractmethod
    def get_transactions(self, budget_id: str, since_date: str) -> List[dict]:
        """Get transactions since a given date (YYYY-MM-DD). Returns raw dicts with at least
        amount, category_name, date, deleted, and payee_name fields."""
        pass

    @abstractmethod
    def get_transaction_by_id(self, budget_id: str, transaction_id: str) -> Optional[dict]:
        """Get a single transaction by ID. Returns the raw YNAB transaction dict or None."""
        pass

    @abstractmethod
    def delete_transaction(self, budget_id: str, transaction_id: str) -> bool:
        """Delete a transaction. Returns True if deletion succeeded."""
        pass

    @abstractmethod
    def update_transaction(self, budget_id: str, transaction_id: str, fields: dict) -> bool:
        """Update fields of an existing transaction. The fields dict may contain any combination of:
        amount (int, milliunits), payee_name (str), payee_id (str), category_id (str), account_id (str).
        Returns True on success."""
        pass

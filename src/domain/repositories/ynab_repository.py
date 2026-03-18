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
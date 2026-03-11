from dataclasses import dataclass
from typing import Optional

from domain.models.expense import ExpenseResult


@dataclass
class BudgetQueryResult:
    """Result of a budget query operation"""
    success: bool
    query_type: str  # "category_balance" | "account_balance" | "budget_summary"
    data: Optional[dict] = None
    error_message: Optional[str] = None

    @classmethod
    def success_result(cls, query_type: str, data: dict) -> 'BudgetQueryResult':
        return cls(success=True, query_type=query_type, data=data)

    @classmethod
    def error_result(cls, query_type: str, error_message: str) -> 'BudgetQueryResult':
        return cls(success=False, query_type=query_type, error_message=error_message)


@dataclass
class MessageResult:
    """Result of processing a user message (expense or query)"""
    intent: str  # "expense" | "query"
    expense_result: Optional[ExpenseResult] = None
    query_result: Optional[BudgetQueryResult] = None

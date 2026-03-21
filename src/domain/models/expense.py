import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from domain.time_utils import user_now


_UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

logger = logging.getLogger(__name__)


@dataclass
class Expense:
    """Domain model for an expense transaction"""
    amount: Decimal
    payee: str
    memo: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    confidence: float = 0.0
    parser_source: str = 'unknown'
    category_explanation: Optional[str] = None
    date: Optional[datetime] = None
    is_split: bool = False
    split_person: Optional[str] = None
    split_proportion: Decimal = field(default_factory=lambda: Decimal('0.5'))
    split_category_id: Optional[str] = None
    split_category_name: Optional[str] = None
    payer: str = 'user'
    payee_id: Optional[str] = None

    def to_ynab_format(self, budget_id: str, default_account_id: str) -> dict:
        """Convert to YNAB API transaction format"""
        # YNAB uses miliunits (multiply by 1000) and negative for expenses
        amount_milliunits = int(self.amount * -1000)

        effective_date = self.date or user_now()
        transaction_data = {
            "account_id": self.account_id or default_account_id,
            "payee_name": self.payee,
            "amount": amount_milliunits,
            "memo": self.memo,
            "date": effective_date.strftime("%Y-%m-%d"),
            "cleared": "uncleared"
        }

        # Use payee_id when available (matched against existing YNAB payees)
        if self.payee_id and _UUID_PATTERN.match(self.payee_id):
            transaction_data["payee_id"] = self.payee_id

        # Other-paid split: 0-sum transaction with two subtransactions
        if self.payer == 'other' and self.is_split and self.split_category_id and _UUID_PATTERN.match(self.split_category_id):
            transaction_data["amount"] = 0
            user_share_milliunits = int(self.amount * self.split_proportion * -1000)
            subtransactions = [
                {"amount": user_share_milliunits},
                {"amount": -user_share_milliunits, "category_id": self.split_category_id},
            ]
            if self.category_id and _UUID_PATTERN.match(self.category_id):
                subtransactions[0]["category_id"] = self.category_id
            transaction_data["subtransactions"] = subtransactions
        # User-paid split transaction: create subtransactions instead of top-level category
        elif self.is_split and self.split_category_id and _UUID_PATTERN.match(self.split_category_id):
            user_share = int(self.amount * self.split_proportion * -1000)
            split_share = amount_milliunits - user_share
            subtransactions = [
                {"amount": user_share},
                {"amount": split_share, "category_id": self.split_category_id},
            ]
            if self.category_id and _UUID_PATTERN.match(self.category_id):
                subtransactions[0]["category_id"] = self.category_id
            transaction_data["subtransactions"] = subtransactions
        else:
            # Only add category_id if available and valid UUID format
            if self.category_id and self.category_id.strip():
                if _UUID_PATTERN.match(self.category_id):
                    transaction_data["category_id"] = self.category_id
                else:
                    logger.warning(f"Invalid category UUID format: {self.category_id}, omitting from transaction")

        return {"transaction": transaction_data}
    
    def is_valid(self) -> bool:
        """Validate expense data"""
        return (
            self.amount > 0 and
            bool(self.payee.strip()) and
            self.confidence >= 0.0
        )


@dataclass
class ExpenseResult:
    """Result of expense processing operation"""
    success: bool
    expense: Optional[Expense] = None
    error_message: Optional[str] = None
    transaction_id: Optional[str] = None
    
    @classmethod
    def success_result(cls, expense: Expense, transaction_id: str = None) -> 'ExpenseResult':
        return cls(success=True, expense=expense, transaction_id=transaction_id)
    
    @classmethod
    def error_result(cls, error_message: str) -> 'ExpenseResult':
        return cls(success=False, error_message=error_message)
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from domain.time_utils import user_now

if TYPE_CHECKING:
    from domain.models.user import UserConfiguration


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
    split_fixed_amount: Optional[Decimal] = None
    split_user_share_amount: Optional[Decimal] = None
    split_other_share_amount: Optional[Decimal] = None
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

        has_valid_split_category = bool(
            self.split_category_id and _UUID_PATTERN.match(self.split_category_id)
        )
        has_normalized_shares = (
            self.split_user_share_amount is not None
            and self.split_other_share_amount is not None
        )

        if self.is_split and has_valid_split_category and has_normalized_shares:
            user_share_milliunits = int(self.split_user_share_amount * -1000)
            other_share_milliunits = int(self.split_other_share_amount * -1000)

            if self.payer == 'other':
                transaction_data["amount"] = 0
                subtransactions = [
                    {"amount": user_share_milliunits},
                    {"amount": -user_share_milliunits, "category_id": self.split_category_id},
                ]
                if self.category_id and _UUID_PATTERN.match(self.category_id):
                    subtransactions[0]["category_id"] = self.category_id
                transaction_data["subtransactions"] = subtransactions
                return {"transaction": transaction_data}

            if self.split_user_share_amount == 0:
                transaction_data["category_id"] = self.split_category_id
                return {"transaction": transaction_data}

            if self.split_other_share_amount == 0:
                if self.category_id and _UUID_PATTERN.match(self.category_id):
                    transaction_data["category_id"] = self.category_id
                return {"transaction": transaction_data}

            subtransactions = [
                {"amount": user_share_milliunits},
                {"amount": other_share_milliunits, "category_id": self.split_category_id},
            ]
            if self.category_id and _UUID_PATTERN.match(self.category_id):
                subtransactions[0]["category_id"] = self.category_id
            transaction_data["subtransactions"] = subtransactions
            return {"transaction": transaction_data}

        # Other-paid split: 0-sum transaction with two subtransactions
        if self.payer == 'other' and self.is_split and has_valid_split_category:
            transaction_data["amount"] = 0
            if self.split_fixed_amount is not None:
                others_share_mu = int(self.split_fixed_amount * -1000)  # other person's share in milliunits
                user_share_milliunits = int(self.amount * -1000) - others_share_mu
            else:
                user_share_milliunits = int(self.amount * self.split_proportion * -1000)
            subtransactions = [
                {"amount": user_share_milliunits},
                {"amount": -user_share_milliunits, "category_id": self.split_category_id},
            ]
            if self.category_id and _UUID_PATTERN.match(self.category_id):
                subtransactions[0]["category_id"] = self.category_id
            transaction_data["subtransactions"] = subtransactions
        # User-paid split transaction: create subtransactions instead of top-level category
        elif self.is_split and has_valid_split_category:
            if self.split_fixed_amount is not None:
                split_share = int(self.split_fixed_amount * -1000)
                user_share = amount_milliunits - split_share
            else:
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


@dataclass
class PreparedExpense:
    """Prepared expense data used by preview and two-phase commit flows."""

    expense: Expense
    budget_id: str
    account_id: str
    user_config: 'UserConfiguration'
    expense_result: Optional[ExpenseResult]
    intent: str

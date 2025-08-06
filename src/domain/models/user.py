from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UserConfiguration:
    """Domain model for user configuration"""
    telegram_id: int
    budget_id: Optional[str] = None
    default_account_id: Optional[str] = None
    default_account_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def is_configured(self) -> bool:
        """Check if user has minimum required configuration"""
        return bool(self.budget_id and self.default_account_id)
    
    def update_budget(self, budget_id: str):
        """Update budget configuration"""
        self.budget_id = budget_id
        self.updated_at = datetime.now()
    
    def update_default_account(self, account_id: str, account_name: str = None):
        """Update default account configuration"""
        self.default_account_id = account_id
        self.default_account_name = account_name
        self.updated_at = datetime.now()


@dataclass
class YNABBudget:
    """Domain model for YNAB budget"""
    id: str
    name: str
    currency_format: dict
    
    @classmethod
    def from_api_response(cls, api_data: dict) -> 'YNABBudget':
        return cls(
            id=api_data['id'],
            name=api_data['name'],
            currency_format=api_data.get('currency_format', {})
        )


@dataclass
class YNABAccount:
    """Domain model for YNAB account"""
    id: str
    name: str
    type: str
    balance: int = 0
    cleared_balance: int = 0
    uncleared_balance: int = 0
    closed: bool = False
    deleted: bool = False
    
    @classmethod
    def from_api_response(cls, api_data: dict) -> 'YNABAccount':
        return cls(
            id=api_data['id'],
            name=api_data['name'],
            type=api_data['type'],
            balance=api_data.get('balance', 0),
            cleared_balance=api_data.get('cleared_balance', 0),
            uncleared_balance=api_data.get('uncleared_balance', 0),
            closed=api_data.get('closed', False),
            deleted=api_data.get('deleted', False)
        )


@dataclass
class YNABCategory:
    """Domain model for YNAB category"""
    id: str
    name: str
    group_name: str
    full_name: str
    budgeted: int = 0
    activity: int = 0
    balance: int = 0
    deleted: bool = False
    hidden: bool = False
    
    @classmethod
    def from_api_response(cls, api_data: dict, group_name: str) -> 'YNABCategory':
        full_name = f"{group_name} → {api_data['name']}"
        return cls(
            id=api_data['id'],
            name=api_data['name'],
            group_name=group_name,
            full_name=full_name,
            budgeted=api_data.get('budgeted', 0),
            activity=api_data.get('activity', 0),
            balance=api_data.get('balance', 0),
            deleted=api_data.get('deleted', False),
            hidden=api_data.get('hidden', False)
        )
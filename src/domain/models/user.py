from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from enum import Enum

from domain.time_utils import DEFAULT_TIMEZONE

_TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)


class UserStatus(Enum):
    """User authorization status"""
    PENDING = "pending"      # Waiting for admin approval
    AUTHORIZED = "authorized"  # Can use the bot
    BLOCKED = "blocked"      # Blocked by admin


@dataclass
class UserConfiguration:
    """Domain model for user configuration with authentication"""
    telegram_id: int
    status: UserStatus = UserStatus.PENDING
    budget_id: Optional[str] = None
    default_account_id: Optional[str] = None
    default_account_name: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: str = DEFAULT_TIMEZONE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    ynab_access_token: Optional[str] = None
    ynab_refresh_token: Optional[str] = None
    ynab_token_expires_at: Optional[datetime] = None
    last_weekly_summary_sent: Optional[datetime] = None
    confirm_before_create: bool = False

    def is_configured(self) -> bool:
        """Check if user has minimum required configuration"""
        return bool(self.budget_id and self.default_account_id)
    
    def is_authorized(self) -> bool:
        """Check if user is authorized to use the bot"""
        return self.status == UserStatus.AUTHORIZED
    
    def is_pending(self) -> bool:
        """Check if user is pending approval"""
        return self.status == UserStatus.PENDING
    
    def is_blocked(self) -> bool:
        """Check if user is blocked"""
        return self.status == UserStatus.BLOCKED
    
    def authorize(self, approved_by: int):
        """Authorize the user"""
        self.status = UserStatus.AUTHORIZED
        self.approved_at = datetime.now()
        self.approved_by = approved_by
        self.updated_at = datetime.now()
    
    def block(self):
        """Block the user"""
        self.status = UserStatus.BLOCKED
        self.updated_at = datetime.now()
    
    def get_display_name(self) -> str:
        """Get user's display name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.telegram_id}"
    
    def update_budget(self, budget_id: str):
        """Update budget configuration"""
        self.budget_id = budget_id
        self.updated_at = datetime.now()
    
    def update_default_account(self, account_id: str, account_name: str = None):
        """Update default account configuration"""
        self.default_account_id = account_id
        self.default_account_name = account_name
        self.updated_at = datetime.now()
    
    def update_profile(self, username: str = None, first_name: str = None, last_name: str = None):
        """Update user profile information"""
        if username is not None:
            self.username = username
        if first_name is not None:
            self.first_name = first_name
        if last_name is not None:
            self.last_name = last_name
        self.updated_at = datetime.now()

    def update_timezone(self, timezone: str):
        """Update user timezone (IANA timezone string)"""
        self.timezone = timezone
        self.updated_at = datetime.now()

    def has_ynab_token(self) -> bool:
        return self.ynab_access_token is not None

    def is_token_expired(self) -> bool:
        if self.ynab_token_expires_at is None:
            return True
        return datetime.now() >= self.ynab_token_expires_at - _TOKEN_EXPIRY_BUFFER

    def update_ynab_tokens(self, access_token: str, refresh_token: str, expires_in_seconds: int):
        self.ynab_access_token = access_token
        self.ynab_refresh_token = refresh_token
        self.ynab_token_expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
        self.updated_at = datetime.now()

    def clear_ynab_tokens(self):
        self.ynab_access_token = None
        self.ynab_refresh_token = None
        self.ynab_token_expires_at = None
        self.updated_at = datetime.now()

    def mark_weekly_summary_sent(self):
        """Record that the weekly summary was sent now (UTC)."""
        self.last_weekly_summary_sent = datetime.now(timezone.utc)
        self.updated_at = datetime.now()

    def toggle_confirmation(self, enabled: bool):
        """Enable or disable the confirmation-before-create flow."""
        self.confirm_before_create = enabled
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
class YNABPayee:
    """Domain model for YNAB payee"""
    id: str
    name: str
    deleted: bool = False

    @classmethod
    def from_api_response(cls, api_data: dict) -> 'YNABPayee':
        return cls(
            id=api_data['id'],
            name=api_data['name'],
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
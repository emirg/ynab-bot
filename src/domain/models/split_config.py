from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class SplitGroup:
    """Domain model for a Splitwise category group configuration"""
    telegram_id: int
    category_id: str
    category_name: str
    id: Optional[int] = None
    person_aliases: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def add_alias(self, alias: str) -> None:
        """Adds an alias if not already present (case-insensitive dedup)"""
        alias_clean = alias.strip()
        if not alias_clean:
            return
            
        if not any(a.lower() == alias_clean.lower() for a in self.person_aliases):
            self.person_aliases.append(alias_clean)

    def remove_alias(self, alias: str) -> bool:
        """Removes an alias, returns True if found (case-insensitive)"""
        alias_lower = alias.lower().strip()
        for i, a in enumerate(self.person_aliases):
            if a.lower() == alias_lower:
                self.person_aliases.pop(i)
                return True
        return False

    def matches_alias(self, text: str) -> bool:
        """Case-insensitive check if text matches any alias"""
        text_lower = text.lower().strip()
        return any(a.lower() == text_lower for a in self.person_aliases)


@dataclass
class SharedAccountConfig:
    """Domain model for a user's shared transactions YNAB account"""
    telegram_id: int
    account_id: str
    account_name: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

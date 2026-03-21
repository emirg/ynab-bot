from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import List, Optional

from domain.models.split_config import SplitGroup, SharedAccountConfig
from domain.repositories.split_config_repository import SplitConfigRepository
from infrastructure.repositories.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class SQLiteSplitConfigRepository(SplitConfigRepository):
    """SQLite implementation of SplitConfigRepository."""

    def __init__(self, db_manager: DatabaseManager):
        self._db = db_manager

    def add_split_group(self, telegram_id: int, category_id: str, category_name: str) -> SplitGroup:
        conn = self._db.get_connection()
        
        # INSERT OR IGNORE and then fetch to handle existing groups
        conn.execute(
            """
            INSERT OR IGNORE INTO split_groups (telegram_id, category_id, category_name)
            VALUES (?, ?, ?)
            """,
            (telegram_id, category_id, category_name),
        )
        conn.commit()

        # Fetch the group (whether it was just created or already existed)
        cursor = conn.execute(
            "SELECT id, created_at FROM split_groups WHERE telegram_id = ? AND category_id = ?",
            (telegram_id, category_id),
        )
        row = cursor.fetchone()
        
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        # Fetch aliases
        cursor = conn.execute(
            "SELECT alias FROM split_person_aliases WHERE split_group_id = ?",
            (row["id"],),
        )
        aliases = [r["alias"] for r in cursor.fetchall()]

        return SplitGroup(
            id=row["id"],
            telegram_id=telegram_id,
            category_id=category_id,
            category_name=category_name,
            person_aliases=aliases,
            created_at=created_at,
        )

    def remove_split_group(self, telegram_id: int, category_id: str) -> bool:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM split_groups WHERE telegram_id = ? AND category_id = ?",
            (telegram_id, category_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_split_groups(self, telegram_id: int) -> List[SplitGroup]:
        conn = self._db.get_connection()
        cursor = conn.execute(
            """
            SELECT id, category_id, category_name, created_at
            FROM split_groups
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        groups = []
        for row in cursor.fetchall():
            created_at = row["created_at"]
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            
            # Fetch aliases for each group
            alias_cursor = conn.execute(
                "SELECT alias FROM split_person_aliases WHERE split_group_id = ?",
                (row["id"],),
            )
            aliases = [r["alias"] for r in alias_cursor.fetchall()]
            
            groups.append(
                SplitGroup(
                    id=row["id"],
                    telegram_id=telegram_id,
                    category_id=row["category_id"],
                    category_name=row["category_name"],
                    person_aliases=aliases,
                    created_at=created_at,
                )
            )
        return groups

    def find_split_group_by_alias(self, telegram_id: int, alias: str) -> Optional[SplitGroup]:
        conn = self._db.get_connection()
        cursor = conn.execute(
            """
            SELECT g.id, g.category_id, g.category_name, g.created_at
            FROM split_person_aliases a
            JOIN split_groups g ON a.split_group_id = g.id
            WHERE g.telegram_id = ? AND LOWER(a.alias) = LOWER(?)
            """,
            (telegram_id, alias.strip()),
        )
        row = cursor.fetchone()
        if not row:
            return None

        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        # Fetch all aliases for this group
        alias_cursor = conn.execute(
            "SELECT alias FROM split_person_aliases WHERE split_group_id = ?",
            (row["id"],),
        )
        aliases = [r["alias"] for r in alias_cursor.fetchall()]

        return SplitGroup(
            id=row["id"],
            telegram_id=telegram_id,
            category_id=row["category_id"],
            category_name=row["category_name"],
            person_aliases=aliases,
            created_at=created_at,
        )

    def add_person_alias(self, telegram_id: int, category_id: str, alias: str) -> bool:
        alias_clean = alias.strip()
        if not alias_clean:
            return False

        conn = self._db.get_connection()
        
        # Find group id
        cursor = conn.execute(
            "SELECT id FROM split_groups WHERE telegram_id = ? AND category_id = ?",
            (telegram_id, category_id),
        )
        row = cursor.fetchone()
        if not row:
            return False
        
        group_id = row["id"]
        
        try:
            conn.execute(
                "INSERT INTO split_person_aliases (split_group_id, alias) VALUES (?, ?)",
                (group_id, alias_clean),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Alias already exists for this group
            return False

    def remove_person_alias(self, telegram_id: int, category_id: str, alias: str) -> bool:
        conn = self._db.get_connection()
        
        # Find group id
        cursor = conn.execute(
            "SELECT id FROM split_groups WHERE telegram_id = ? AND category_id = ?",
            (telegram_id, category_id),
        )
        row = cursor.fetchone()
        if not row:
            return False
        
        group_id = row["id"]
        
        cursor = conn.execute(
            "DELETE FROM split_person_aliases WHERE split_group_id = ? AND alias = ?",
            (group_id, alias),
        )
        conn.commit()
        return cursor.rowcount > 0

    def set_shared_account(self, telegram_id: int, account_id: str, account_name: str) -> SharedAccountConfig:
        conn = self._db.get_connection()
        now = datetime.now().isoformat()
        
        conn.execute(
            """
            INSERT INTO split_shared_account (telegram_id, account_id, account_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                account_id = excluded.account_id,
                account_name = excluded.account_name,
                updated_at = excluded.updated_at
            """,
            (telegram_id, account_id, account_name, now, now),
        )
        conn.commit()
        
        # Fetch to get correct dates if it was an insert
        cursor = conn.execute(
            "SELECT created_at, updated_at FROM split_shared_account WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = cursor.fetchone()
        
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        updated_at = row["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return SharedAccountConfig(
            telegram_id=telegram_id,
            account_id=account_id,
            account_name=account_name,
            created_at=created_at,
            updated_at=updated_at,
        )

    def get_shared_account(self, telegram_id: int) -> Optional[SharedAccountConfig]:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "SELECT account_id, account_name, created_at, updated_at FROM split_shared_account WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        updated_at = row["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return SharedAccountConfig(
            telegram_id=telegram_id,
            account_id=row["account_id"],
            account_name=row["account_name"],
            created_at=created_at,
            updated_at=updated_at,
        )

    def remove_shared_account(self, telegram_id: int) -> bool:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM split_shared_account WHERE telegram_id = ?",
            (telegram_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

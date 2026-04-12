from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from domain.models.split_config import SharedAccountConfig, SplitGroup
from domain.repositories.split_config_repository import SplitConfigRepository


class PostgresSplitConfigRepository(SplitConfigRepository):
    """PostgreSQL implementation of SplitConfigRepository."""

    def __init__(self, db_manager):
        self._db = db_manager

    def add_split_group(self, telegram_id: int, category_id: str, category_name: str) -> SplitGroup:
        conn = self._db.get_connection()
        conn.execute(
            """
            INSERT INTO split_groups (telegram_id, category_id, category_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (telegram_id, category_id) DO NOTHING
            """,
            (telegram_id, category_id, category_name),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, created_at, category_name FROM split_groups WHERE telegram_id = %s AND category_id = %s",
            (telegram_id, category_id),
        ).fetchone()
        aliases = self._get_aliases(conn, row["id"])
        return SplitGroup(
            id=row["id"],
            telegram_id=telegram_id,
            category_id=category_id,
            category_name=row["category_name"],
            person_aliases=aliases,
            created_at=row["created_at"] if isinstance(row["created_at"], datetime) else datetime.fromisoformat(row["created_at"]),
        )

    def remove_split_group(self, telegram_id: int, category_id: str) -> bool:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM split_groups WHERE telegram_id = %s AND category_id = %s",
            (telegram_id, category_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_split_groups(self, telegram_id: int) -> List[SplitGroup]:
        conn = self._db.get_connection()
        rows = conn.execute(
            """
            SELECT id, category_id, category_name, created_at
            FROM split_groups
            WHERE telegram_id = %s
            """,
            (telegram_id,),
        ).fetchall()
        return [
            SplitGroup(
                id=row["id"],
                telegram_id=telegram_id,
                category_id=row["category_id"],
                category_name=row["category_name"],
                person_aliases=self._get_aliases(conn, row["id"]),
                created_at=row["created_at"] if isinstance(row["created_at"], datetime) else datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def find_split_group_by_alias(self, telegram_id: int, alias: str) -> Optional[SplitGroup]:
        conn = self._db.get_connection()
        row = conn.execute(
            """
            SELECT g.id, g.category_id, g.category_name, g.created_at
            FROM split_person_aliases a
            JOIN split_groups g ON a.split_group_id = g.id
            WHERE g.telegram_id = %s AND LOWER(a.alias) = LOWER(%s)
            """,
            (telegram_id, alias.strip()),
        ).fetchone()
        if not row:
            return None
        return SplitGroup(
            id=row["id"],
            telegram_id=telegram_id,
            category_id=row["category_id"],
            category_name=row["category_name"],
            person_aliases=self._get_aliases(conn, row["id"]),
            created_at=row["created_at"] if isinstance(row["created_at"], datetime) else datetime.fromisoformat(row["created_at"]),
        )

    def add_person_alias(self, telegram_id: int, category_id: str, alias: str) -> bool:
        alias_clean = alias.strip()
        if not alias_clean:
            return False
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT id FROM split_groups WHERE telegram_id = %s AND category_id = %s",
            (telegram_id, category_id),
        ).fetchone()
        if not row:
            return False
        cursor = conn.execute(
            """
            INSERT INTO split_person_aliases (split_group_id, alias)
            VALUES (%s, %s)
            ON CONFLICT (split_group_id, alias) DO NOTHING
            """,
            (row["id"], alias_clean),
        )
        conn.commit()
        return cursor.rowcount > 0

    def remove_person_alias(self, telegram_id: int, category_id: str, alias: str) -> bool:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT id FROM split_groups WHERE telegram_id = %s AND category_id = %s",
            (telegram_id, category_id),
        ).fetchone()
        if not row:
            return False
        cursor = conn.execute(
            "DELETE FROM split_person_aliases WHERE split_group_id = %s AND alias = %s",
            (row["id"], alias),
        )
        conn.commit()
        return cursor.rowcount > 0

    def set_shared_account(self, telegram_id: int, account_id: str, account_name: str) -> SharedAccountConfig:
        conn = self._db.get_connection()
        now = datetime.now()
        conn.execute(
            """
            INSERT INTO split_shared_account (telegram_id, account_id, account_name, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (telegram_id) DO UPDATE SET
                account_id = EXCLUDED.account_id,
                account_name = EXCLUDED.account_name,
                updated_at = EXCLUDED.updated_at
            """,
            (telegram_id, account_id, account_name, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT created_at, updated_at FROM split_shared_account WHERE telegram_id = %s",
            (telegram_id,),
        ).fetchone()
        created_at = row["created_at"] if isinstance(row["created_at"], datetime) else datetime.fromisoformat(row["created_at"])
        updated_at = row["updated_at"] if isinstance(row["updated_at"], datetime) else datetime.fromisoformat(row["updated_at"])
        return SharedAccountConfig(
            telegram_id=telegram_id,
            account_id=account_id,
            account_name=account_name,
            created_at=created_at,
            updated_at=updated_at,
        )

    def get_shared_account(self, telegram_id: int) -> Optional[SharedAccountConfig]:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT account_id, account_name, created_at, updated_at FROM split_shared_account WHERE telegram_id = %s",
            (telegram_id,),
        ).fetchone()
        if not row:
            return None
        created_at = row["created_at"] if isinstance(row["created_at"], datetime) else datetime.fromisoformat(row["created_at"])
        updated_at = row["updated_at"] if isinstance(row["updated_at"], datetime) else datetime.fromisoformat(row["updated_at"])
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
            "DELETE FROM split_shared_account WHERE telegram_id = %s",
            (telegram_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _get_aliases(conn, split_group_id: int) -> List[str]:
        rows = conn.execute(
            "SELECT alias FROM split_person_aliases WHERE split_group_id = %s",
            (split_group_id,),
        ).fetchall()
        return [row["alias"] for row in rows]

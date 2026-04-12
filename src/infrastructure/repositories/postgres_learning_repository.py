from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from domain.models.expense import Expense
from domain.repositories.learning_repository import LearningRepository
from domain.services.payee_normalizer import normalize_payee

logger = logging.getLogger(__name__)

_MAX_RECENT_TRANSACTIONS = 20


class PostgresLearningRepository(LearningRepository):
    """PostgreSQL implementation of LearningRepository with per-user scoping."""

    def __init__(self, db_manager):
        self._db = db_manager

    def record_successful_transaction(self, telegram_id: int, expense: Expense) -> None:
        if not expense.payee or not expense.category_id:
            return

        normalized = normalize_payee(expense.payee)
        conn = self._db.get_connection()
        conn.execute(
            """
            INSERT INTO payee_category_mappings
                (telegram_id, normalized_payee, category_id, category_name, count, last_updated)
            VALUES (%s, %s, %s, %s, 1, %s)
            ON CONFLICT (telegram_id, normalized_payee, category_id) DO UPDATE SET
                count = payee_category_mappings.count + 1,
                last_updated = EXCLUDED.last_updated,
                category_name = EXCLUDED.category_name
            """,
            (telegram_id, normalized, expense.category_id, expense.category_name or "", datetime.now()),
        )
        conn.commit()

    def get_payee_associations(self, telegram_id: int) -> List[Dict]:
        conn = self._db.get_connection()
        rows = conn.execute(
            """
            SELECT normalized_payee, category_id, category_name, count
            FROM payee_category_mappings
            WHERE telegram_id = %s
            ORDER BY count DESC
            """,
            (telegram_id,),
        ).fetchall()
        return [
            {
                "normalized_payee": row["normalized_payee"],
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "count": row["count"],
            }
            for row in rows
        ]

    def delete_payee_associations(self, telegram_id: int, normalized_payee: str) -> int:
        normalized = normalize_payee(normalized_payee)
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM payee_category_mappings WHERE telegram_id = %s AND normalized_payee = %s",
            (telegram_id, normalized),
        )
        conn.commit()
        return cursor.rowcount

    def predict_category(self, telegram_id: int, payee: str, categories: List[Dict]) -> Optional[Tuple[str, float, int]]:
        if not payee:
            return None

        normalized = normalize_payee(payee)
        conn = self._db.get_connection()
        rows = conn.execute(
            """
            SELECT category_id, count
            FROM payee_category_mappings
            WHERE telegram_id = %s AND normalized_payee = %s
            """,
            (telegram_id, normalized),
        ).fetchall()
        if not rows:
            return None

        total = sum(row["count"] for row in rows)
        best = max(rows, key=lambda row: row["count"])
        category_ids = {cat.get("id") for cat in categories if cat.get("id")}
        if best["category_id"] not in category_ids:
            return None
        return best["category_id"], best["count"] / total, best["count"]

    def record_user_correction(
        self,
        telegram_id: int,
        payee: str,
        old_category_id: str,
        new_category_id: str,
        new_category_name: str = "",
    ) -> None:
        normalized = normalize_payee(payee)
        conn = self._db.get_connection()
        conn.execute(
            """
            INSERT INTO user_corrections
                (telegram_id, normalized_payee, old_category_id, new_category_id)
            VALUES (%s, %s, %s, %s)
            """,
            (telegram_id, normalized, old_category_id, new_category_id),
        )
        conn.execute(
            """
            UPDATE payee_category_mappings
            SET count = count - 1, last_updated = %s
            WHERE telegram_id = %s AND normalized_payee = %s AND category_id = %s AND count > 0
            """,
            (datetime.now(), telegram_id, normalized, old_category_id),
        )
        conn.execute(
            """
            DELETE FROM payee_category_mappings
            WHERE telegram_id = %s AND normalized_payee = %s AND category_id = %s AND count <= 0
            """,
            (telegram_id, normalized, old_category_id),
        )
        conn.execute(
            """
            INSERT INTO payee_category_mappings
                (telegram_id, normalized_payee, category_id, category_name, count, last_updated)
            VALUES (%s, %s, %s, %s, 1, %s)
            ON CONFLICT (telegram_id, normalized_payee, category_id) DO UPDATE SET
                count = payee_category_mappings.count + 1,
                last_updated = EXCLUDED.last_updated,
                category_name = EXCLUDED.category_name
            """,
            (telegram_id, normalized, new_category_id, new_category_name, datetime.now()),
        )
        conn.commit()

    def get_learning_statistics(self, telegram_id: int) -> Dict:
        conn = self._db.get_connection()
        total_txn = conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM payee_category_mappings WHERE telegram_id = %s",
            (telegram_id,),
        ).fetchone()["total"]
        learned_payees = conn.execute(
            "SELECT COUNT(DISTINCT normalized_payee) AS total FROM payee_category_mappings WHERE telegram_id = %s",
            (telegram_id,),
        ).fetchone()["total"]
        total_corrections = conn.execute(
            "SELECT COUNT(*) AS total FROM user_corrections WHERE telegram_id = %s",
            (telegram_id,),
        ).fetchone()["total"]
        return {
            "total_transactions": total_txn,
            "learned_associations": learned_payees,
            "accuracy_improvements": total_corrections,
            "learned_payees": learned_payees,
            "total_corrections": total_corrections,
        }

    def add_recent_transaction(self, telegram_id: int, expense: Expense, ynab_transaction_id: str = None) -> None:
        conn = self._db.get_connection()
        conn.execute(
            """
            INSERT INTO recent_transactions
                (telegram_id, payee, amount, category_id, category_name, confidence, parser_source, ynab_transaction_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                telegram_id,
                expense.payee,
                float(expense.amount),
                expense.category_id,
                expense.category_name,
                expense.confidence,
                expense.parser_source,
                ynab_transaction_id,
            ),
        )
        conn.execute(
            """
            DELETE FROM recent_transactions
            WHERE telegram_id = %s AND id NOT IN (
                SELECT id
                FROM recent_transactions
                WHERE telegram_id = %s
                ORDER BY id DESC
                LIMIT %s
            )
            """,
            (telegram_id, telegram_id, _MAX_RECENT_TRANSACTIONS),
        )
        conn.commit()

    def decrement_learning(self, telegram_id: int, payee: str, category_id: str) -> None:
        normalized = normalize_payee(payee)
        conn = self._db.get_connection()
        conn.execute(
            """
            UPDATE payee_category_mappings
            SET count = count - 1, last_updated = %s
            WHERE telegram_id = %s AND normalized_payee = %s AND category_id = %s AND count > 0
            """,
            (datetime.now(), telegram_id, normalized, category_id),
        )
        conn.execute(
            """
            DELETE FROM payee_category_mappings
            WHERE telegram_id = %s AND normalized_payee = %s AND category_id = %s AND count <= 0
            """,
            (telegram_id, normalized, category_id),
        )
        conn.commit()

    def get_recent_transactions(self, telegram_id: int, limit: int = 10) -> List[Dict]:
        conn = self._db.get_connection()
        rows = conn.execute(
            """
            SELECT payee, amount, category_id, category_name, confidence, parser_source, created_at, ynab_transaction_id
            FROM recent_transactions
            WHERE telegram_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (telegram_id, limit),
        ).fetchall()
        return [
            {
                "payee": row["payee"],
                "amount": row["amount"],
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "confidence": row["confidence"],
                "parser_source": row["parser_source"],
                "timestamp": row["created_at"],
                "ynab_transaction_id": row["ynab_transaction_id"],
            }
            for row in rows
        ]

    def delete_recent_transaction(self, telegram_id: int, ynab_transaction_id: str) -> bool:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM recent_transactions WHERE telegram_id = %s AND ynab_transaction_id = %s",
            (telegram_id, ynab_transaction_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def update_recent_transaction(
        self,
        telegram_id: int,
        ynab_transaction_id: str,
        *,
        payee: str | None = None,
        amount: float | None = None,
        category_id: str | None = None,
        category_name: str | None = None,
    ) -> bool:
        conn = self._db.get_connection()
        cursor = conn.execute(
            """
            UPDATE recent_transactions
            SET
                payee = COALESCE(%s, payee),
                amount = COALESCE(%s, amount),
                category_id = COALESCE(%s, category_id),
                category_name = COALESCE(%s, category_name)
            WHERE telegram_id = %s AND ynab_transaction_id = %s
            """,
            (payee, amount, category_id, category_name, telegram_id, ynab_transaction_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_payee_category_distribution(self, telegram_id: int) -> Dict[str, List[Dict]]:
        conn = self._db.get_connection()
        rows = conn.execute(
            """
            SELECT normalized_payee, category_name, count
            FROM payee_category_mappings
            WHERE telegram_id = %s
            ORDER BY normalized_payee, count DESC
            """,
            (telegram_id,),
        ).fetchall()

        grouped: Dict[str, List[Dict]] = {}
        for row in rows:
            grouped.setdefault(row["normalized_payee"], []).append(
                {"category_name": row["category_name"], "count": row["count"]}
            )

        result: Dict[str, List[Dict]] = {}
        for payee, entries in grouped.items():
            total = sum(entry["count"] for entry in entries)
            if total < 2:
                continue
            result[payee] = [
                {
                    "category_name": entry["category_name"],
                    "count": entry["count"],
                    "percentage": entry["count"] / total,
                }
                for entry in entries
            ]
        return result

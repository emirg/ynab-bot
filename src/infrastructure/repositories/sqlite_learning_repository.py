from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from domain.repositories.learning_repository import LearningRepository
from domain.models.expense import Expense
from domain.services.payee_normalizer import normalize_payee
from infrastructure.repositories.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

_MAX_RECENT_TRANSACTIONS = 20


class SQLiteLearningRepository(LearningRepository):
    """SQLite implementation of LearningRepository with per-user scoping."""

    def __init__(self, db_manager: DatabaseManager):
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
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(telegram_id, normalized_payee, category_id) DO UPDATE SET
                count = count + 1,
                last_updated = excluded.last_updated,
                category_name = excluded.category_name
            """,
            (
                telegram_id,
                normalized,
                expense.category_id,
                expense.category_name or "",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        logger.info(f"Learned: {normalized} -> {expense.category_name} (user {telegram_id})")

    def get_payee_associations(self, telegram_id: int) -> List[Dict]:
        """Get all payee-category associations for a user, ordered by count DESC"""
        conn = self._db.get_connection()
        cursor = conn.execute(
            """
            SELECT normalized_payee, category_id, category_name, count
            FROM payee_category_mappings
            WHERE telegram_id = ?
            ORDER BY count DESC
            """,
            (telegram_id,),
        )
        return [
            {
                "normalized_payee": row["normalized_payee"],
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "count": row["count"],
            }
            for row in cursor.fetchall()
        ]

    def delete_payee_associations(self, telegram_id: int, normalized_payee: str) -> int:
        """Delete all associations for a given payee for a user. Returns row count deleted."""
        # Ensure we use normalized version for matching
        normalized = normalize_payee(normalized_payee)
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM payee_category_mappings WHERE telegram_id = ? AND normalized_payee = ?",
            (telegram_id, normalized),
        )
        conn.commit()
        return cursor.rowcount

    def predict_category(
        self, telegram_id: int, payee: str, categories: List[Dict]
    ) -> Optional[Tuple[str, float, int]]:
        if not payee:
            return None

        normalized = normalize_payee(payee)
        conn = self._db.get_connection()

        cursor = conn.execute(
            """
            SELECT category_id, count
            FROM payee_category_mappings
            WHERE telegram_id = ? AND normalized_payee = ?
            """,
            (telegram_id, normalized),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        # Find most frequent category and compute confidence
        total = sum(row['count'] for row in rows)
        best = max(rows, key=lambda r: r['count'])
        best_category_id = best['category_id']
        confidence = best['count'] / total

        # Verify category still exists in YNAB
        category_ids = {cat.get('id') for cat in categories if cat.get('id')}
        if best_category_id not in category_ids:
            logger.warning(f"Learned category {best_category_id} no longer exists in YNAB")
            return None

        logger.info(f"Predicted for '{payee}': {best_category_id} (confidence: {confidence:.2f})")
        return best_category_id, confidence, best['count']

    def record_user_correction(
        self, telegram_id: int, payee: str, old_category_id: str, new_category_id: str
    ) -> None:
        normalized = normalize_payee(payee)
        conn = self._db.get_connection()

        # Log the correction
        conn.execute(
            """
            INSERT INTO user_corrections
                (telegram_id, normalized_payee, old_category_id, new_category_id)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_id, normalized, old_category_id, new_category_id),
        )

        # Reduce old category count (delete row if count reaches 0)
        conn.execute(
            """
            UPDATE payee_category_mappings
            SET count = count - 1, last_updated = ?
            WHERE telegram_id = ? AND normalized_payee = ? AND category_id = ? AND count > 0
            """,
            (datetime.now().isoformat(), telegram_id, normalized, old_category_id),
        )
        conn.execute(
            """
            DELETE FROM payee_category_mappings
            WHERE telegram_id = ? AND normalized_payee = ? AND category_id = ? AND count <= 0
            """,
            (telegram_id, normalized, old_category_id),
        )

        # Increase new category count
        conn.execute(
            """
            INSERT INTO payee_category_mappings
                (telegram_id, normalized_payee, category_id, count, last_updated)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(telegram_id, normalized_payee, category_id) DO UPDATE SET
                count = count + 1,
                last_updated = excluded.last_updated
            """,
            (telegram_id, normalized, new_category_id, datetime.now().isoformat()),
        )
        conn.commit()
        logger.info(f"Correction: {normalized} {old_category_id} -> {new_category_id} (user {telegram_id})")

    def get_learning_statistics(self, telegram_id: int) -> Dict:
        conn = self._db.get_connection()

        total_txn = conn.execute(
            "SELECT COALESCE(SUM(count), 0) FROM payee_category_mappings WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()[0]

        learned_payees = conn.execute(
            "SELECT COUNT(DISTINCT normalized_payee) FROM payee_category_mappings WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()[0]

        total_corrections = conn.execute(
            "SELECT COUNT(*) FROM user_corrections WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()[0]

        return {
            "total_transactions": total_txn,
            "learned_associations": learned_payees,
            "accuracy_improvements": total_corrections,
            "learned_payees": learned_payees,
            "total_corrections": total_corrections,
        }

    def add_recent_transaction(self, telegram_id: int, expense: Expense) -> None:
        conn = self._db.get_connection()
        conn.execute(
            """
            INSERT INTO recent_transactions
                (telegram_id, payee, amount, category_id, category_name, confidence, parser_source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                expense.payee,
                float(expense.amount),
                expense.category_id,
                expense.category_name,
                expense.confidence,
                expense.parser_source,
            ),
        )

        # Trim to keep only the most recent entries per user
        conn.execute(
            """
            DELETE FROM recent_transactions
            WHERE telegram_id = ? AND id NOT IN (
                SELECT id FROM recent_transactions
                WHERE telegram_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (telegram_id, telegram_id, _MAX_RECENT_TRANSACTIONS),
        )
        conn.commit()

    def get_recent_transactions(self, telegram_id: int, limit: int = 10) -> List[Dict]:
        conn = self._db.get_connection()
        cursor = conn.execute(
            """
            SELECT payee, amount, category_id, category_name, confidence, parser_source, created_at
            FROM recent_transactions
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (telegram_id, limit),
        )
        return [
            {
                "payee": row['payee'],
                "amount": row['amount'],
                "category_id": row['category_id'],
                "category_name": row['category_name'],
                "confidence": row['confidence'],
                "parser_source": row['parser_source'],
                "timestamp": row['created_at'],
            }
            for row in cursor.fetchall()
        ]

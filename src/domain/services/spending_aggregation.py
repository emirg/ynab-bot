from __future__ import annotations

from typing import Dict, List


def extract_expense_entries(transactions: List[dict]) -> List[dict]:
    """Return negative expense entries, expanding split subtransactions when needed.

    YNAB split transactions keep the real category amounts in ``subtransactions``.
    For category breakdowns we should count those subcategories instead of the
    parent ``Split (Multiple Categories)`` bucket, but only when the parent
    transaction is itself a real expense (negative amount). Zero-sum bookkeeping
    transactions are ignored.
    """
    entries: List[dict] = []
    for txn in transactions:
        amount = txn.get("amount", 0)
        if amount >= 0:
            continue

        negative_subtransactions = [
            sub for sub in (txn.get("subtransactions") or [])
            if sub.get("amount", 0) < 0
        ]
        if negative_subtransactions:
            for sub in negative_subtransactions:
                entries.append(
                    {
                        "amount": sub["amount"],
                        "category_name": sub.get("category_name") or "Sin categoría",
                        "date": txn.get("date", ""),
                    }
                )
            continue

        entries.append(
            {
                "amount": amount,
                "category_name": txn.get("category_name") or "Sin categoría",
                "date": txn.get("date", ""),
            }
        )
    return entries


def aggregate_category_spending(expense_entries: List[dict]) -> Dict[str, int]:
    category_totals: Dict[str, int] = {}
    for entry in expense_entries:
        name = entry.get("category_name") or "Sin categoría"
        category_totals[name] = category_totals.get(name, 0) + abs(entry["amount"])
    return category_totals

from __future__ import annotations

from typing import Any, Dict, List


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


def summarize_spending(expense_entries: List[dict]) -> tuple[int, Dict[str, int]]:
    total_spent = sum(abs(entry["amount"]) for entry in expense_entries)
    return total_spent, aggregate_category_spending(expense_entries)


def summarize_transaction_spending(transactions: List[dict]) -> tuple[int, Dict[str, int]]:
    return summarize_spending(extract_expense_entries(transactions))


def normalize_budget_category_snapshots(categories: List[Any]) -> List[dict]:
    snapshots: List[dict] = []
    for category in categories:
        name = _read_category_field(category, "name", "")
        budgeted = _read_category_field(category, "budgeted", 0)
        activity = _read_category_field(category, "activity", 0)
        balance = _read_category_field(category, "balance", 0)
        hidden = bool(_read_category_field(category, "hidden", False))
        deleted = bool(_read_category_field(category, "deleted", False))

        if deleted or hidden:
            continue
        if budgeted <= 0 and activity == 0:
            continue

        snapshots.append(
            {
                "name": name,
                "budgeted": budgeted,
                "activity": activity,
                "balance": balance,
            }
        )
    return snapshots


def aggregate_category_spending(expense_entries: List[dict]) -> Dict[str, int]:
    category_totals: Dict[str, int] = {}
    for entry in expense_entries:
        name = entry.get("category_name") or "Sin categoría"
        category_totals[name] = category_totals.get(name, 0) + abs(entry["amount"])
    return category_totals


def _read_category_field(category: Any, field_name: str, default: Any) -> Any:
    if isinstance(category, dict):
        return category.get(field_name, default)
    return getattr(category, field_name, default)

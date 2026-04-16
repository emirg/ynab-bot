from __future__ import annotations

from typing import Any, Dict, List


def extract_expense_entries(transactions: List[dict]) -> List[dict]:
    """Return negative expense entries, expanding split subtransactions when needed.

    YNAB split transactions keep the real category amounts in ``subtransactions``.
    For category breakdowns we should count those subcategories instead of the
    parent ``Split (Multiple Categories)`` bucket. This includes zero-sum shared
    transactions where the parent amount is ``0`` but a negative subtransaction
    still represents the user's expense. Positive balancing legs are ignored.
    Transfer rows and other bookkeeping-only transactions are excluded.
    """
    entries: List[dict] = []
    for txn in transactions:
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

        if _is_bookkeeping_transaction(txn):
            continue

        amount = txn.get("amount", 0)
        if amount >= 0:
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


def summarize_transaction_net_spending(transactions: List[dict]) -> tuple[int, Dict[str, int]]:
    """Return Reflect-like net spending plus visible negative-net category totals.

    Total spending is derived from net category activity for the period:
    outflows increase spending and category inflows reduce it. Visible category
    totals only include categories whose net activity is still negative.
    """
    net_activity_by_key: Dict[str, int] = {}
    category_name_by_key: Dict[str, str] = {}

    for txn in transactions:
        if _is_bookkeeping_transaction(txn):
            continue

        subtransactions = txn.get("subtransactions") or []
        if subtransactions:
            for sub in subtransactions:
                amount = sub.get("amount", 0)
                if amount == 0:
                    continue
                if amount > 0 and not _should_count_positive_category_inflow(sub):
                    continue
                key = _category_key(sub)
                net_activity_by_key[key] = net_activity_by_key.get(key, 0) + amount
                category_name_by_key[key] = _category_name(sub)
            continue

        amount = txn.get("amount", 0)
        if amount == 0:
            continue
        if amount > 0 and not _should_count_positive_category_inflow(txn):
            continue

        key = _category_key(txn)
        net_activity_by_key[key] = net_activity_by_key.get(key, 0) + amount
        category_name_by_key[key] = _category_name(txn)

    net_total = sum(net_activity_by_key.values())
    total_spent = max(0, -net_total)

    visible_category_totals: Dict[str, int] = {}
    for key, net_amount in net_activity_by_key.items():
        if net_amount >= 0:
            continue
        name = category_name_by_key[key]
        visible_category_totals[name] = visible_category_totals.get(name, 0) + abs(net_amount)

    return total_spent, visible_category_totals


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


def _is_bookkeeping_transaction(transaction: dict) -> bool:
    return bool(
        transaction.get("transfer_account_id")
        or transaction.get("transfer_transaction_id")
    )


def _category_name(transaction: dict) -> str:
    return transaction.get("category_name") or "Sin categoría"


def _category_key(transaction: dict) -> str:
    category_id = transaction.get("category_id")
    if category_id:
        return f"id:{category_id}"
    return f"name:{_category_name(transaction)}"


def _should_count_positive_category_inflow(transaction: dict) -> bool:
    category_id = transaction.get("category_id")
    if not category_id:
        return False
    category_name = _category_name(transaction)
    return not category_name.startswith("Inflow:")


def _read_category_field(category: Any, field_name: str, default: Any) -> Any:
    if isinstance(category, dict):
        return category.get(field_name, default)
    return getattr(category, field_name, default)

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass
class CategorySpending:
    """Spending amount for a single category (milliunits, always positive)."""
    category_name: str
    amount: int  # milliunits, positive


@dataclass
class WeeklySummary:
    """Aggregated weekly spending summary derived from YNAB transactions."""
    total_spent: int                          # milliunits, always positive
    category_breakdown: List[CategorySpending]  # sorted desc by amount
    top_categories: List[CategorySpending]    # first 3 from category_breakdown
    previous_week_total: int                  # milliunits, always positive
    percentage_change: Optional[float]        # None if previous week had no spending
    has_transactions: bool
    week_start: date
    week_end: date

    @classmethod
    def from_transactions(
        cls,
        current_week_txns: List[dict],
        previous_week_txns: List[dict],
        week_start: date,
        week_end: date,
    ) -> "WeeklySummary":
        """
        Build a WeeklySummary from raw YNAB transaction dicts.

        Each transaction dict must contain at minimum:
          - amount: int (milliunits, negative for expenses)
          - category_name: str

        Only expense transactions (amount < 0) are counted.
        """
        current_expenses = [t for t in current_week_txns if t.get("amount", 0) < 0]
        previous_expenses = [t for t in previous_week_txns if t.get("amount", 0) < 0]

        # Total spent — absolute value of the sum of negative amounts
        total_spent = abs(sum(t["amount"] for t in current_expenses))
        previous_week_total = abs(sum(t["amount"] for t in previous_expenses))

        # Aggregate by category
        category_totals: Dict[str, int] = {}
        for txn in current_expenses:
            name = txn.get("category_name") or "Sin categoría"
            category_totals[name] = category_totals.get(name, 0) + abs(txn["amount"])

        category_breakdown = sorted(
            [CategorySpending(category_name=name, amount=amount)
             for name, amount in category_totals.items()],
            key=lambda c: c.amount,
            reverse=True,
        )

        top_categories = category_breakdown[:3]

        if previous_week_total > 0:
            percentage_change = ((total_spent - previous_week_total) / previous_week_total) * 100
        else:
            percentage_change = None

        return cls(
            total_spent=total_spent,
            category_breakdown=category_breakdown,
            top_categories=top_categories,
            previous_week_total=previous_week_total,
            percentage_change=percentage_change,
            has_transactions=len(current_expenses) > 0,
            week_start=week_start,
            week_end=week_end,
        )

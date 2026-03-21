from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

from domain.models.weekly_summary import CategorySpending


@dataclass
class CategoryBudgetComparison:
    """Budget vs. actual spending for a single category (milliunits)."""
    category_name: str
    budgeted: int   # milliunits, positive
    spent: int      # milliunits, positive (abs of activity)
    remaining: int  # milliunits, can be negative if overspent


@dataclass
class OnDemandSummary:
    """Aggregated spending summary for an on-demand period (day, week, or month)."""
    period_type: str                                        # "dia" | "semana" | "mes"
    period_label: str                                       # human-readable label in Spanish
    total_spent: int                                        # milliunits, positive
    category_breakdown: List[CategorySpending]              # sorted desc by amount
    budget_comparison: Optional[List[CategoryBudgetComparison]]  # only for "mes"
    has_transactions: bool
    period_start: date
    period_end: date

    @classmethod
    def from_transactions(
        cls,
        transactions: List[dict],
        period_type: str,
        period_label: str,
        period_start: date,
        period_end: date,
        budget_data: Optional[List[dict]] = None,
    ) -> "OnDemandSummary":
        """
        Build an OnDemandSummary from raw YNAB transaction dicts.

        Each transaction dict must contain at minimum:
          - amount: int (milliunits, negative for expenses)
          - category_name: str

        budget_data (optional) is a list of dicts with keys:
          - name: str
          - budgeted: int (milliunits, positive)
          - activity: int (milliunits, negative for spending)

        Only expense transactions (amount < 0) are counted.
        """
        expenses = [t for t in transactions if t.get("amount", 0) < 0]

        total_spent = abs(sum(t["amount"] for t in expenses))

        # Aggregate spending by category
        category_totals: Dict[str, int] = {}
        for txn in expenses:
            name = txn.get("category_name") or "Sin categoría"
            category_totals[name] = category_totals.get(name, 0) + abs(txn["amount"])

        category_breakdown = sorted(
            [CategorySpending(category_name=name, amount=amount)
             for name, amount in category_totals.items()],
            key=lambda c: c.amount,
            reverse=True,
        )

        # Build budget comparison if budget_data is provided
        budget_comparison: Optional[List[CategoryBudgetComparison]] = None
        if budget_data is not None:
            comparisons = []
            for entry in budget_data:
                budgeted = entry.get("budgeted", 0)
                activity = entry.get("activity", 0)
                spent = abs(activity)
                remaining = budgeted - spent
                comparisons.append(CategoryBudgetComparison(
                    category_name=entry["name"],
                    budgeted=budgeted,
                    spent=spent,
                    remaining=remaining,
                ))
            budget_comparison = comparisons

        return cls(
            period_type=period_type,
            period_label=period_label,
            total_spent=total_spent,
            category_breakdown=category_breakdown,
            budget_comparison=budget_comparison,
            has_transactions=len(expenses) > 0,
            period_start=period_start,
            period_end=period_end,
        )

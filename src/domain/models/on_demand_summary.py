from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from domain.models.weekly_summary import CategorySpending
from domain.services.spending_aggregation import (
    summarize_transaction_spending,
)


@dataclass
class CategoryBudgetComparison:
    """YNAB category budget snapshot for a single category (milliunits)."""
    category_name: str
    budgeted: int   # milliunits assigned this month, positive
    spent: int      # milliunits spent this month, positive (abs of activity)
    remaining: int  # YNAB available balance, can be negative if overspent


@dataclass
class MonthlySummaryInsight:
    """Derived insight bundle used to keep monthly formatting concise and useful."""
    overspent_categories: List[CategoryBudgetComparison] = field(default_factory=list)
    top_categories: List[CategorySpending] = field(default_factory=list)
    healthy_categories_count: int = 0
    status: str = "sin_datos"
    status_summary: Optional[str] = None
    recommended_action: Optional[str] = None


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
    monthly_insight: Optional[MonthlySummaryInsight] = None

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
          - balance: int (milliunits, YNAB available amount)

        Only expense transactions (amount < 0) are counted.
        """
        total_spent, category_breakdown = cls._build_spending_from_transactions(transactions)

        # Build budget comparison if budget_data is provided
        budget_comparison: Optional[List[CategoryBudgetComparison]] = None
        if budget_data is not None:
            comparisons = []
            for entry in budget_data:
                budgeted = entry.get("budgeted", 0)
                activity = entry.get("activity", 0)
                spent = abs(activity)
                remaining = entry["balance"]
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
            monthly_insight=MonthlySummaryInsight(
                top_categories=category_breakdown[:3],
            ) if period_type == "mes" else None,
            has_transactions=total_spent > 0,
            period_start=period_start,
            period_end=period_end,
        )

    @staticmethod
    def _build_spending_from_transactions(
        transactions: List[dict],
    ) -> tuple[int, List[CategorySpending]]:
        total_spent, category_totals = summarize_transaction_spending(transactions)
        category_breakdown = sorted(
            [
                CategorySpending(category_name=name, amount=amount)
                for name, amount in category_totals.items()
            ],
            key=lambda c: c.amount,
            reverse=True,
        )
        return total_spent, category_breakdown

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

from domain.models.weekly_summary import CategorySpending

_SPANISH_WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


@dataclass
class AdvisorTrendPoint:
    date: date
    label: str
    amount: int

    def to_payload(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "label": self.label,
            "amount": self.amount,
        }


@dataclass
class AdvisorBudgetStatus:
    category_name: str
    budgeted: int
    spent: int
    remaining: int
    status: str

    def to_payload(self) -> dict:
        return {
            "category_name": self.category_name,
            "budgeted": self.budgeted,
            "spent": self.spent,
            "remaining": self.remaining,
            "status": self.status,
        }


@dataclass
class AdvisorSummary:
    period_label: str
    total_spent: int
    transaction_count: int
    average_daily_spent: int
    top_category_name: Optional[str]
    top_category_amount: int
    active_days: int

    def to_payload(self) -> dict:
        return {
            "period_label": self.period_label,
            "total_spent": self.total_spent,
            "transaction_count": self.transaction_count,
            "average_daily_spent": self.average_daily_spent,
            "top_category_name": self.top_category_name,
            "top_category_amount": self.top_category_amount,
            "active_days": self.active_days,
        }


@dataclass
class AdvisorDashboard:
    period_type: str
    period_label: str
    period_start: date
    period_end: date
    summary: AdvisorSummary
    trend: List[AdvisorTrendPoint]
    top_categories: List[CategorySpending]
    budget_status: Optional[List[AdvisorBudgetStatus]]
    has_transactions: bool

    @classmethod
    def from_ynab_data(
        cls,
        *,
        period_type: str,
        period_label: str,
        period_start: date,
        period_end: date,
        transactions: List[dict],
        budget_data: Optional[List[dict]] = None,
    ) -> "AdvisorDashboard":
        expenses = [txn for txn in transactions if txn.get("amount", 0) < 0]

        total_spent = abs(sum(txn["amount"] for txn in expenses))
        transaction_count = len(expenses)
        active_days = (period_end - period_start).days + 1
        average_daily_spent = total_spent // active_days if active_days > 0 else 0

        category_totals: Dict[str, int] = {}
        for txn in expenses:
            category_name = txn.get("category_name") or "Sin categoría"
            category_totals[category_name] = category_totals.get(category_name, 0) + abs(txn["amount"])

        top_categories = sorted(
            [
                CategorySpending(category_name=name, amount=amount)
                for name, amount in category_totals.items()
            ],
            key=lambda item: item.amount,
            reverse=True,
        )[:5]

        top_category_name = top_categories[0].category_name if top_categories else None
        top_category_amount = top_categories[0].amount if top_categories else 0

        trend = cls._build_trend(
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            expenses=expenses,
        )

        budget_status = None
        if budget_data is not None:
            budget_status = cls._build_budget_status(budget_data)

        return cls(
            period_type=period_type,
            period_label=period_label,
            period_start=period_start,
            period_end=period_end,
            summary=AdvisorSummary(
                period_label=period_label,
                total_spent=total_spent,
                transaction_count=transaction_count,
                average_daily_spent=average_daily_spent,
                top_category_name=top_category_name,
                top_category_amount=top_category_amount,
                active_days=active_days,
            ),
            trend=trend,
            top_categories=top_categories,
            budget_status=budget_status,
            has_transactions=transaction_count > 0,
        )

    @staticmethod
    def _build_trend(
        *,
        period_type: str,
        period_start: date,
        period_end: date,
        expenses: List[dict],
    ) -> List[AdvisorTrendPoint]:
        amounts_by_date: Dict[str, int] = {}
        for txn in expenses:
            txn_date = txn.get("date")
            if not txn_date:
                continue
            amounts_by_date[txn_date] = amounts_by_date.get(txn_date, 0) + abs(txn["amount"])

        current = period_start
        points: List[AdvisorTrendPoint] = []
        while current <= period_end:
            label = AdvisorDashboard._build_trend_label(period_type, current, period_start)
            points.append(
                AdvisorTrendPoint(
                    date=current,
                    label=label,
                    amount=amounts_by_date.get(current.isoformat(), 0),
                )
            )
            current += timedelta(days=1)
        return points

    @staticmethod
    def _build_trend_label(period_type: str, point_date: date, period_start: date) -> str:
        if period_type == "dia":
            return "Hoy"
        if period_type == "semana":
            return _SPANISH_WEEKDAYS[point_date.weekday()]
        if point_date == period_start:
            return f"{point_date.day:02d}"
        return str(point_date.day)

    @staticmethod
    def _build_budget_status(budget_data: List[dict]) -> List[AdvisorBudgetStatus]:
        statuses = []
        for entry in budget_data:
            budgeted = entry.get("budgeted", 0)
            spent = abs(entry.get("activity", 0))
            remaining = budgeted - spent
            statuses.append(
                AdvisorBudgetStatus(
                    category_name=entry["name"],
                    budgeted=budgeted,
                    spent=spent,
                    remaining=remaining,
                    status="overspent" if remaining < 0 else "within_budget",
                )
            )

        statuses.sort(key=lambda item: item.spent, reverse=True)
        return statuses[:5]

    def to_payload(self) -> dict:
        return {
            "period_type": self.period_type,
            "period_label": self.period_label,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "has_transactions": self.has_transactions,
            "summary": self.summary.to_payload(),
            "trend": [point.to_payload() for point in self.trend],
            "top_categories": [
                {
                    "category_name": item.category_name,
                    "amount": item.amount,
                }
                for item in self.top_categories
            ],
            "budget_status": None if self.budget_status is None else [
                item.to_payload() for item in self.budget_status
            ],
        }

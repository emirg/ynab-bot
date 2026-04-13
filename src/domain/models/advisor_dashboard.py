from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from domain.models.weekly_summary import CategorySpending


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
class AdvisorInsight:
    code: str
    title: str
    message: str
    severity: str
    evidence: dict

    def to_payload(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "evidence": self.evidence,
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
    insights: List[AdvisorInsight]
    has_transactions: bool

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
            "insights": [item.to_payload() for item in self.insights],
        }

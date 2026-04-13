from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange
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

        insights = cls._build_insights(
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            total_spent=total_spent,
            transaction_count=transaction_count,
            top_categories=top_categories,
            budget_data=budget_data,
            budget_status=budget_status,
        )

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
            insights=insights,
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

    @classmethod
    def _build_insights(
        cls,
        *,
        period_type: str,
        period_start: date,
        period_end: date,
        total_spent: int,
        transaction_count: int,
        top_categories: List[CategorySpending],
        budget_data: Optional[List[dict]],
        budget_status: Optional[List[AdvisorBudgetStatus]],
    ) -> List[AdvisorInsight]:
        if transaction_count == 0:
            return []

        insights: List[AdvisorInsight] = []

        if top_categories and total_spent > 0:
            top_category = top_categories[0]
            concentration_ratio = Decimal(top_category.amount) / Decimal(total_spent)
            if concentration_ratio >= Decimal("0.60"):
                insights.append(
                    AdvisorInsight(
                        code="spending_concentration",
                        title="Tu gasto esta muy concentrado",
                        message=(
                            f"{top_category.category_name} concentra una parte alta de tus gastos en este periodo. "
                            "Vale la pena revisar si es un pico puntual o un habito que se esta repitiendo."
                        ),
                        severity="warning",
                        evidence={
                            "category_name": top_category.category_name,
                            "category_amount": top_category.amount,
                            "share_percent": cls._as_percent(concentration_ratio),
                            "total_spent": total_spent,
                        },
                    )
                )

        if period_type == "mes" and budget_data is not None:
            total_budgeted = sum(max(entry.get("budgeted", 0), 0) for entry in budget_data)
            days_in_month = monthrange(period_end.year, period_end.month)[1]
            elapsed_days = max((period_end - period_start).days + 1, 1)
            projected_spent = (total_spent * days_in_month) // elapsed_days

            if total_budgeted > 0 and elapsed_days >= 3 and projected_spent > total_budgeted:
                insights.append(
                    AdvisorInsight(
                        code="monthly_pace_warning",
                        title="Vas por encima del ritmo del mes",
                        message=(
                            "Si mantienes el ritmo actual, tu gasto proyectado al cierre del mes quedaria por encima "
                            "de lo presupuestado."
                        ),
                        severity="warning",
                        evidence={
                            "projected_spent": projected_spent,
                            "total_budgeted": total_budgeted,
                            "elapsed_days": elapsed_days,
                            "days_in_month": days_in_month,
                        },
                    )
                )

            overspent_items = [
                item for item in (budget_status or [])
                if item.status == "overspent"
            ]
            if overspent_items:
                item = overspent_items[0]
                insights.append(
                    AdvisorInsight(
                        code="overspent_category",
                        title="Ya hay una categoria en sobregasto",
                        message=(
                            f"{item.category_name} ya supero lo presupuestado este mes. "
                            "Conviene ajustar el ritmo o mover presupuesto antes de cerrar el periodo."
                        ),
                        severity="warning",
                        evidence={
                            "category_name": item.category_name,
                            "budgeted": item.budgeted,
                            "spent": item.spent,
                            "remaining": item.remaining,
                        },
                    )
                )
            else:
                near_limit_items = [
                    item for item in (budget_status or [])
                    if item.budgeted > 0 and item.spent * 100 >= item.budgeted * 90
                ]
                if near_limit_items:
                    item = near_limit_items[0]
                    insights.append(
                        AdvisorInsight(
                            code="near_budget_limit",
                            title="Una categoria esta cerca del limite",
                            message=(
                                f"{item.category_name} ya consumio casi todo su presupuesto mensual. "
                                "Si sigues al mismo ritmo, es una categoria con riesgo de sobregasto."
                            ),
                            severity="info",
                            evidence={
                                "category_name": item.category_name,
                                "budgeted": item.budgeted,
                                "spent": item.spent,
                                "usage_percent": cls._as_percent(Decimal(item.spent) / Decimal(item.budgeted)),
                            },
                        )
                    )

            inactive_items = [
                entry for entry in budget_data
                if entry.get("budgeted", 0) > 0 and entry.get("activity", 0) == 0
            ]
            if inactive_items:
                entry = max(inactive_items, key=lambda item: item.get("budgeted", 0))
                insights.append(
                    AdvisorInsight(
                        code="inactive_budget",
                        title="Tienes presupuesto quieto este mes",
                        message=(
                            f"{entry['name']} tiene dinero asignado pero todavia no registra actividad. "
                            "Puede ser una oportunidad para reasignar ese monto si ya no lo necesitas ahi."
                        ),
                        severity="info",
                        evidence={
                            "category_name": entry["name"],
                            "budgeted": entry.get("budgeted", 0),
                        },
                    )
                )

        if not insights:
            insights.append(
                AdvisorInsight(
                    code="all_clear",
                    title="No veo alertas fuertes por ahora",
                    message=(
                        "Tu periodo actual no muestra senales evidentes de desorden en las reglas que revisa el advisor. "
                        "Sigue monitoreando el ritmo y las categorias principales."
                    ),
                    severity="positive",
                    evidence={
                        "transaction_count": transaction_count,
                        "total_spent": total_spent,
                    },
                )
            )

        return insights

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

    @staticmethod
    def _as_percent(value: Decimal) -> int:
        return int((value * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

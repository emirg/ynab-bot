from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from domain.models.advisor_dashboard import AdvisorBudgetStatus, AdvisorInsight
from domain.models.weekly_summary import CategorySpending


class AdvisorInsightsService:
    def build_insights(
        self,
        *,
        period_type: str,
        period_start: date,
        period_end: date,
        total_spent: int,
        transaction_count: int,
        top_categories: list[CategorySpending],
        budget_data: Optional[list[dict]],
        budget_status: Optional[list[AdvisorBudgetStatus]],
    ) -> list[AdvisorInsight]:
        if transaction_count == 0:
            return []

        insights: list[AdvisorInsight] = []

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
                            "share_percent": self._as_percent(concentration_ratio),
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
                                "usage_percent": self._as_percent(
                                    Decimal(item.spent) / Decimal(item.budgeted)
                                ),
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

    @staticmethod
    def _as_percent(value: Decimal) -> int:
        return int((value * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

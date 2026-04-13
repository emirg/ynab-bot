"""Tests for OnDemandSummaryFormatter."""

import pytest
from datetime import date
from typing import List, Optional

from domain.models.on_demand_summary import (
    CategoryBudgetComparison,
    MonthlySummaryInsight,
    OnDemandSummary,
)
from domain.models.weekly_summary import CategorySpending
from presentation.telegram.formatters import OnDemandSummaryFormatter


def make_summary(
    period_type: str = "mes",
    period_label: str = "Mes de marzo 2026",
    total_spent: int = 500_000,
    category_breakdown: Optional[List[CategorySpending]] = None,
    budget_comparison: Optional[List[CategoryBudgetComparison]] = None,
    has_transactions: bool = True,
    period_start: date = date(2026, 3, 1),
    period_end: date = date(2026, 3, 19),
) -> OnDemandSummary:
    if category_breakdown is None:
        category_breakdown = [
            CategorySpending(category_name="Comida", amount=300_000),
            CategorySpending(category_name="Transporte", amount=200_000),
        ]
    monthly_insight = None
    if period_type == "mes" and has_transactions:
        overspent = [comp for comp in (budget_comparison or []) if comp.remaining < 0][:3]
        at_risk = [
            comp for comp in (budget_comparison or [])
            if comp.remaining >= 0
            and (comp.spent + max(comp.remaining, 0)) > 0
            and (comp.spent / (comp.spent + max(comp.remaining, 0))) >= 0.9
        ][:3]
        status_summary = "Tu mes va dentro del presupuesto por ahora."
        recommended_action = "Mantén el ritmo actual y revisa solo las categorías más activas."
        status = "estable"
        if overspent:
            status = "alerta"
            status_summary = f"Vas pasado en {len(overspent)} categoría{'s' if len(overspent) != 1 else ''}."
            recommended_action = "Revisa esas categorías antes de seguir gastando este mes."
        elif at_risk:
            status = "riesgo"
            status_summary = f"Tienes {len(at_risk)} categoría{'s' if len(at_risk) != 1 else ''} al límite."
            recommended_action = "Si puedes, frena gasto variable en esas categorías por unos días."
        monthly_insight = MonthlySummaryInsight(
            overspent_categories=overspent,
            at_risk_categories=at_risk,
            top_categories=category_breakdown[:3],
            healthy_categories_count=max(0, len(budget_comparison or []) - len(overspent) - len(at_risk)),
            status=status,
            status_summary=status_summary,
            recommended_action=recommended_action,
        )
    return OnDemandSummary(
        period_type=period_type,
        period_label=period_label,
        total_spent=total_spent,
        category_breakdown=category_breakdown,
        budget_comparison=budget_comparison,
        has_transactions=has_transactions,
        period_start=period_start,
        period_end=period_end,
        monthly_insight=monthly_insight,
    )


class TestNoTransactionsMessage:
    def test_no_transactions_returns_friendly_message(self):
        summary = make_summary(has_transactions=False, total_spent=0, category_breakdown=[])
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert result == "No hubo gastos en Mes de marzo 2026."

    def test_no_transactions_includes_period_label(self):
        summary = make_summary(
            period_type="dia",
            period_label="Hoy (19/03)",
            has_transactions=False,
            total_spent=0,
            category_breakdown=[],
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "Hoy (19/03)" in result
        assert result == "No hubo gastos en Hoy (19/03)."


class TestDaySummaryFormatting:
    def test_day_summary_has_header(self):
        summary = make_summary(
            period_type="dia",
            period_label="Hoy (19/03)",
            total_spent=150_000,
            category_breakdown=[CategorySpending(category_name="Almuerzo", amount=150_000)],
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "📊 *Resumen — Hoy (19/03)*" in result

    def test_day_summary_has_total(self):
        summary = make_summary(
            period_type="dia",
            period_label="Hoy (19/03)",
            total_spent=150_000,
            category_breakdown=[CategorySpending(category_name="Almuerzo", amount=150_000)],
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "💰 *Total gastado:* $150" in result

    def test_day_summary_has_category_breakdown(self):
        summary = make_summary(
            period_type="dia",
            period_label="Hoy (19/03)",
            total_spent=150_000,
            category_breakdown=[CategorySpending(category_name="Almuerzo", amount=150_000)],
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "📋 *Desglose por categoría:*" in result
        assert "1. Almuerzo — $150" in result

    def test_day_summary_has_footer_suggesting_mes(self):
        summary = make_summary(
            period_type="dia",
            period_label="Hoy (19/03)",
            total_spent=150_000,
            category_breakdown=[CategorySpending(category_name="Almuerzo", amount=150_000)],
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "/resumen mes" in result
        assert "💡" in result

    def test_day_summary_no_budget_comparison_section(self):
        summary = make_summary(
            period_type="dia",
            period_label="Hoy (19/03)",
            total_spent=150_000,
            category_breakdown=[CategorySpending(category_name="Almuerzo", amount=150_000)],
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "Presupuesto vs. Gasto" not in result


class TestWeekSummaryFormatting:
    def test_week_summary_has_header(self):
        summary = make_summary(
            period_type="semana",
            period_label="Semana (lun 17/03 - mié 19/03)",
            total_spent=300_000,
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "📊 *Resumen — Semana (lun 17/03 - mié 19/03)*" in result

    def test_week_summary_has_footer_suggesting_mes(self):
        summary = make_summary(
            period_type="semana",
            period_label="Semana (lun 17/03 - mié 19/03)",
            total_spent=300_000,
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "/resumen mes" in result

    def test_week_summary_no_budget_comparison_section(self):
        summary = make_summary(
            period_type="semana",
            period_label="Semana (lun 17/03 - mié 19/03)",
            total_spent=300_000,
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "Presupuesto vs. Gasto" not in result


class TestMonthSummaryWithBudgetComparison:
    def test_month_summary_has_header(self):
        summary = make_summary()
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "📊 *Resumen — Mes de marzo 2026*" in result

    def test_month_summary_no_footer_for_mes(self):
        summary = make_summary()
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "/resumen mes" not in result

    def test_month_summary_has_status_section(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Comida",
                budgeted=400_000,
                spent=300_000,
                remaining=100_000,
            )
        ]
        summary = make_summary(budget_comparison=budget_comparison)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "🧭 *Estado del mes:*" in result

    def test_month_summary_shows_next_step(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Comida",
                budgeted=400_000,
                spent=300_000,
                remaining=100_000,
            )
        ]
        summary = make_summary(budget_comparison=budget_comparison)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "💡 *Siguiente paso:*" in result

    def test_healthy_month_can_highlight_top_category(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Transporte",
                budgeted=200_000,
                spent=150_000,
                remaining=50_000,
            )
        ]
        summary = make_summary(budget_comparison=budget_comparison)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "✅ Tu categoría más activa va en" in result

    def test_month_summary_avoids_full_budget_dump(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Ropa",
                budgeted=100_000,
                spent=100_000,
                remaining=0,
            )
        ]
        summary = make_summary(budget_comparison=budget_comparison)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "Presupuesto vs. Gasto" not in result


class TestOverspentCategoryHighlighting:
    def test_overspent_category_has_red_emoji(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Restaurantes",
                budgeted=100_000,
                spent=150_000,
                remaining=-50_000,
            )
        ]
        summary = make_summary(budget_comparison=budget_comparison)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "🔴 *Restaurantes* va pasado" in result

    def test_overspent_shows_negative_remaining(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Restaurantes",
                budgeted=100_000,
                spent=150_000,
                remaining=-50_000,
            )
        ]
        summary = make_summary(budget_comparison=budget_comparison)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "$50" in result

    def test_mixed_overspent_and_at_risk(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Comida",
                budgeted=400_000,
                spent=380_000,
                remaining=20_000,
            ),
            CategoryBudgetComparison(
                category_name="Restaurantes",
                budgeted=100_000,
                spent=150_000,
                remaining=-50_000,
            ),
        ]
        summary = make_summary(budget_comparison=budget_comparison)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "🟠 *Comida* ya consumió 95% del disponible" in result
        assert "🔴 *Restaurantes* va pasado" in result

    def test_carryover_budget_is_not_flagged_as_overspent_or_risk(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Energy",
                budgeted=150_000_000,
                spent=172_390_000,
                remaining=29_831_830,
            )
        ]
        summary = make_summary(
            total_spent=172_390_000,
            category_breakdown=[CategorySpending(category_name="Energy", amount=172_390_000)],
            budget_comparison=budget_comparison,
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "va pasado" not in result
        assert "al límite" not in result
        assert "✅ Tu categoría más activa va en *Energy*" in result


class TestMonthSummaryWithoutBudgetData:
    def test_month_summary_without_budget_comparison_has_no_budget_section(self):
        summary = make_summary(budget_comparison=None)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "Presupuesto vs. Gasto" not in result

    def test_month_summary_without_budget_still_shows_actionable_signal(self):
        summary = make_summary(budget_comparison=None)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "🧭 *Estado del mes:*" in result
        assert "Comida" in result


class TestCategoryBreakdownOrdering:
    def test_monthly_detail_categories_listed_in_order(self):
        """Monthly detail categories must appear in descending order of spending."""
        breakdown = [
            CategorySpending(category_name="Comida", amount=500_000),
            CategorySpending(category_name="Transporte", amount=200_000),
            CategorySpending(category_name="Ocio", amount=50_000),
        ]
        summary = make_summary(
            total_spent=750_000,
            category_breakdown=breakdown,
        )
        result = OnDemandSummaryFormatter.format_monthly_categories_detail(summary)
        pos_comida = result.index("Comida")
        pos_transporte = result.index("Transporte")
        pos_ocio = result.index("Ocio")
        assert pos_comida < pos_transporte < pos_ocio

    def test_detail_categories_capped_with_extra_note(self):
        """Detail view should cap long lists and explain there is more."""
        breakdown = [
            CategorySpending(category_name=f"Cat{i}", amount=(10 - i) * 10_000)
            for i in range(6)
        ]
        summary = make_summary(total_spent=300_000, category_breakdown=breakdown)
        result = OnDemandSummaryFormatter.format_monthly_categories_detail(summary)
        for i in range(6):
            assert f"Cat{i}" in result
        assert "vista resumida" not in result

    def test_detail_categories_numbered_correctly(self):
        breakdown = [
            CategorySpending(category_name="A", amount=300_000),
            CategorySpending(category_name="B", amount=200_000),
            CategorySpending(category_name="C", amount=100_000),
        ]
        summary = make_summary(total_spent=600_000, category_breakdown=breakdown)
        result = OnDemandSummaryFormatter.format_monthly_categories_detail(summary)
        assert "1. A" in result
        assert "2. B" in result
        assert "3. C" in result


class TestAmountFormatting:
    def test_milliunits_divided_by_1000_for_display(self):
        """Amounts stored as milliunits should display without the milli factor."""
        summary = make_summary(
            total_spent=1_500_000,
            category_breakdown=[CategorySpending(category_name="Supermercado", amount=1_500_000)],
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "$1,500" in result

    def test_budget_comparison_milliunits_converted(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Comida",
                budgeted=2_000_000,
                spent=1_500_000,
                remaining=500_000,
            )
        ]
        summary = make_summary(budget_comparison=budget_comparison)
        result = OnDemandSummaryFormatter.format_monthly_budget_detail(summary)
        assert "$2,000" in result
        assert "$1,500" in result
        assert "$500" in result

    def test_budget_detail_uses_disponible_wording(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Energy",
                budgeted=150_000_000,
                spent=172_390_000,
                remaining=29_831_830,
            )
        ]
        summary = make_summary(
            total_spent=172_390_000,
            category_breakdown=[CategorySpending(category_name="Energy", amount=172_390_000)],
            budget_comparison=budget_comparison,
        )
        result = OnDemandSummaryFormatter.format_monthly_budget_detail(summary)
        assert "disponible" in result
        assert "asignado" in result

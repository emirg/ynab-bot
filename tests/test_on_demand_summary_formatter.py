"""Tests for OnDemandSummaryFormatter."""

import pytest
from datetime import date
from typing import List, Optional

from domain.models.on_demand_summary import OnDemandSummary, CategoryBudgetComparison
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
    return OnDemandSummary(
        period_type=period_type,
        period_label=period_label,
        total_spent=total_spent,
        category_breakdown=category_breakdown,
        budget_comparison=budget_comparison,
        has_transactions=has_transactions,
        period_start=period_start,
        period_end=period_end,
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

    def test_month_summary_budget_comparison_section_present(self):
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
        assert "📈 *Presupuesto vs. Gasto:*" in result

    def test_budget_comparison_shows_budgeted_spent_remaining(self):
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
        assert "Comida" in result
        assert "$400" in result
        assert "$300" in result
        assert "$100" in result

    def test_underspent_category_has_green_emoji(self):
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
        # Green emoji for remaining >= 0
        assert "✅ *Transporte:*" in result

    def test_exactly_zero_remaining_has_green_emoji(self):
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
        assert "✅ *Ropa:*" in result


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
        assert "🔴 *Restaurantes:*" in result

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
        assert "-$50" in result

    def test_mixed_overspent_and_underspent(self):
        budget_comparison = [
            CategoryBudgetComparison(
                category_name="Comida",
                budgeted=400_000,
                spent=300_000,
                remaining=100_000,
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
        assert "✅ *Comida:*" in result
        assert "🔴 *Restaurantes:*" in result


class TestMonthSummaryWithoutBudgetData:
    def test_month_summary_without_budget_comparison_has_no_budget_section(self):
        summary = make_summary(budget_comparison=None)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "Presupuesto vs. Gasto" not in result

    def test_month_summary_without_budget_still_shows_categories(self):
        summary = make_summary(budget_comparison=None)
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "📋 *Desglose por categoría:*" in result
        assert "Comida" in result


class TestCategoryBreakdownOrdering:
    def test_categories_listed_in_order(self):
        """Categories must appear in descending order of spending."""
        breakdown = [
            CategorySpending(category_name="Comida", amount=500_000),
            CategorySpending(category_name="Transporte", amount=200_000),
            CategorySpending(category_name="Ocio", amount=50_000),
        ]
        summary = make_summary(
            total_spent=750_000,
            category_breakdown=breakdown,
        )
        result = OnDemandSummaryFormatter.format_summary(summary)
        pos_comida = result.index("Comida")
        pos_transporte = result.index("Transporte")
        pos_ocio = result.index("Ocio")
        assert pos_comida < pos_transporte < pos_ocio

    def test_all_categories_shown(self):
        """All categories in breakdown must appear in output (not just top 3)."""
        breakdown = [
            CategorySpending(category_name=f"Cat{i}", amount=(10 - i) * 10_000)
            for i in range(6)
        ]
        summary = make_summary(total_spent=300_000, category_breakdown=breakdown)
        result = OnDemandSummaryFormatter.format_summary(summary)
        for i in range(6):
            assert f"Cat{i}" in result

    def test_categories_numbered_correctly(self):
        breakdown = [
            CategorySpending(category_name="A", amount=300_000),
            CategorySpending(category_name="B", amount=200_000),
            CategorySpending(category_name="C", amount=100_000),
        ]
        summary = make_summary(total_spent=600_000, category_breakdown=breakdown)
        result = OnDemandSummaryFormatter.format_summary(summary)
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
        result = OnDemandSummaryFormatter.format_summary(summary)
        assert "$2,000" in result
        assert "$1,500" in result
        assert "$500" in result

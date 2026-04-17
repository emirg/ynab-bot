"""Tests for WeeklySummaryFormatter."""

import pytest
from datetime import date

from domain.models.weekly_summary import WeeklySummary, CategorySpending
from presentation.telegram.formatters import WeeklySummaryFormatter


def _make_summary(
    total_spent=50_000_000,
    top_categories=None,
    category_breakdown=None,
    previous_week_total=40_000_000,
    percentage_change=25.0,
    has_transactions=True,
    week_start=date(2026, 3, 9),
    week_end=date(2026, 3, 15),
):
    if top_categories is None:
        top_categories = [
            CategorySpending("Supermercado", 20_000_000),
            CategorySpending("Transporte", 15_000_000),
            CategorySpending("Restaurantes", 10_000_000),
        ]
    if category_breakdown is None:
        category_breakdown = top_categories[:]

    return WeeklySummary(
        total_spent=total_spent,
        category_breakdown=category_breakdown,
        top_categories=top_categories,
        previous_week_total=previous_week_total,
        percentage_change=percentage_change,
        has_transactions=has_transactions,
        week_start=week_start,
        week_end=week_end,
    )


class TestWeeklySummaryFormatterNoTransactions:
    def test_no_transactions_returns_friendly_message(self):
        summary = _make_summary(
            has_transactions=False,
            total_spent=0,
            top_categories=[],
            category_breakdown=[],
            previous_week_total=0,
            percentage_change=None,
        )
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "No hubo movimientos la semana pasada" in result

    def test_no_transactions_includes_date_range(self):
        summary = _make_summary(
            has_transactions=False,
            total_spent=0,
            top_categories=[],
            category_breakdown=[],
            previous_week_total=0,
            percentage_change=None,
            week_start=date(2026, 3, 9),
            week_end=date(2026, 3, 15),
        )
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "09/03" in result
        assert "15/03" in result

    def test_no_transactions_savings_encouragement(self):
        summary = _make_summary(
            has_transactions=False,
            total_spent=0,
            top_categories=[],
            category_breakdown=[],
            previous_week_total=0,
            percentage_change=None,
        )
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "ahorrando" in result.lower()


class TestWeeklySummaryFormatterFullSummary:
    def test_full_summary_header(self):
        summary = _make_summary()
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "*Resumen semanal*" in result

    def test_full_summary_date_range(self):
        summary = _make_summary(week_start=date(2026, 3, 9), week_end=date(2026, 3, 15))
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "09/03" in result
        assert "15/03" in result

    def test_full_summary_total_amount(self):
        summary = _make_summary(total_spent=50_000_000)
        result = WeeklySummaryFormatter.format_summary(summary)
        # 50_000_000 milliunits = 50,000 display
        assert "50,000" in result

    def test_full_summary_categories_listed(self):
        summary = _make_summary()
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "Supermercado" in result
        assert "Transporte" in result
        assert "Restaurantes" in result

    def test_full_summary_category_amounts(self):
        summary = _make_summary()
        result = WeeklySummaryFormatter.format_summary(summary)
        # 20_000_000 milliunits = 20,000 display
        assert "20,000" in result

    def test_full_summary_comparison_line_increase(self):
        summary = _make_summary(percentage_change=25.0)
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "25%" in result
        assert "más" in result

    def test_full_summary_comparison_line_decrease(self):
        summary = _make_summary(percentage_change=-10.0)
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "10%" in result
        assert "menos" in result

    def test_full_summary_uses_markdown_bold(self):
        summary = _make_summary()
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "*" in result


class TestWeeklySummaryFormatterNoPreviousWeek:
    def test_no_previous_week_omits_comparison_line(self):
        summary = _make_summary(percentage_change=None, previous_week_total=0)
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "semana pasada" not in result or "No hubo" not in result
        # More specific: the comparison sentence should not appear
        assert "Gastaste" not in result

    def test_no_previous_week_still_shows_total(self):
        summary = _make_summary(percentage_change=None, previous_week_total=0)
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "*Total gastado:*" in result


class TestWeeklySummaryFormatterSingleCategory:
    def test_single_category_displays_correctly(self):
        cats = [CategorySpending("Comida", 30_000_000)]
        summary = _make_summary(
            total_spent=30_000_000,
            top_categories=cats,
            category_breakdown=cats,
        )
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "Comida" in result
        assert "30,000" in result

    def test_single_category_no_index_out_of_bounds(self):
        cats = [CategorySpending("Comida", 30_000_000)]
        summary = _make_summary(
            total_spent=30_000_000,
            top_categories=cats,
            category_breakdown=cats,
        )
        # Should not raise
        result = WeeklySummaryFormatter.format_summary(summary)
        assert result  # non-empty


class TestWeeklySummaryFormatterSpecialCharacters:
    def test_category_with_accent_characters(self):
        cats = [
            CategorySpending("Educación & Libros", 5_000_000),
            CategorySpending("Café / Snacks", 3_000_000),
        ]
        summary = _make_summary(
            total_spent=8_000_000,
            top_categories=cats,
            category_breakdown=cats,
        )
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "Educación & Libros" in result
        assert "Café / Snacks" in result

    def test_category_with_parentheses(self):
        cats = [CategorySpending("Transporte (Uber/Taxi)", 10_000_000)]
        summary = _make_summary(
            total_spent=10_000_000,
            top_categories=cats,
            category_breakdown=cats,
        )
        result = WeeklySummaryFormatter.format_summary(summary)
        assert "Transporte (Uber/Taxi)" in result

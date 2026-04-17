"""Tests for OnDemandSummary domain model."""
from datetime import date

import pytest

from domain.models.on_demand_summary import CategoryBudgetComparison, OnDemandSummary
from domain.models.weekly_summary import CategorySpending


PERIOD_START = date(2026, 3, 1)
PERIOD_END = date(2026, 3, 19)


def make_txn(amount: int, category_name: str = "Comida") -> dict:
    return {"amount": amount, "category_name": category_name}


# ---------------------------------------------------------------------------
# from_transactions — basic cases
# ---------------------------------------------------------------------------

class TestFromTransactionsNoTransactions:
    def test_empty_list_has_no_transactions(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert summary.has_transactions is False

    def test_empty_list_total_zero(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert summary.total_spent == 0

    def test_empty_list_breakdown_empty(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert summary.category_breakdown == []

    def test_empty_list_budget_comparison_none_when_not_provided(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert summary.budget_comparison is None


class TestFromTransactionsSingleCategory:
    def test_single_expense_total(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-50_000)],
            period_type="dia",
            period_label="Hoy (19/03)",
            period_start=PERIOD_END,
            period_end=PERIOD_END,
        )
        assert summary.total_spent == 50_000

    def test_single_expense_has_transactions(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-50_000)],
            period_type="dia",
            period_label="Hoy (19/03)",
            period_start=PERIOD_END,
            period_end=PERIOD_END,
        )
        assert summary.has_transactions is True

    def test_single_expense_breakdown(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-50_000, "Supermercado")],
            period_type="dia",
            period_label="Hoy (19/03)",
            period_start=PERIOD_END,
            period_end=PERIOD_END,
        )
        assert len(summary.category_breakdown) == 1
        assert summary.category_breakdown[0].category_name == "Supermercado"
        assert summary.category_breakdown[0].amount == 50_000

    def test_period_fields_preserved(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-1_000)],
            period_type="semana",
            period_label="Semana (lun 17/03 - mié 19/03)",
            period_start=date(2026, 3, 17),
            period_end=date(2026, 3, 19),
        )
        assert summary.period_type == "semana"
        assert summary.period_label == "Semana (lun 17/03 - mié 19/03)"
        assert summary.period_start == date(2026, 3, 17)
        assert summary.period_end == date(2026, 3, 19)


class TestFromTransactionsMultipleCategories:
    def _build(self):
        return OnDemandSummary.from_transactions(
            transactions=[
                make_txn(-10_000, "Restaurantes"),
                make_txn(-30_000, "Supermercado"),
                make_txn(-5_000, "Restaurantes"),
                make_txn(-20_000, "Transporte"),
            ],
            period_type="semana",
            period_label="Semana (lun 17/03 - mié 19/03)",
            period_start=date(2026, 3, 17),
            period_end=PERIOD_END,
        )

    def test_total_spent(self):
        assert self._build().total_spent == 65_000

    def test_aggregates_same_category(self):
        summary = self._build()
        restaurantes = next(c for c in summary.category_breakdown if c.category_name == "Restaurantes")
        assert restaurantes.amount == 15_000

    def test_sorted_descending(self):
        breakdown = self._build().category_breakdown
        amounts = [c.amount for c in breakdown]
        assert amounts == sorted(amounts, reverse=True)

    def test_three_categories(self):
        assert len(self._build().category_breakdown) == 3

    def test_top_category_is_supermercado(self):
        assert self._build().category_breakdown[0].category_name == "Supermercado"

    def test_split_subtransactions_are_grouped_by_real_category(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[
                {
                    "amount": -100_000,
                    "category_name": "Split (Multiple Categories)",
                    "subtransactions": [
                        {"amount": -70_000, "category_name": "Groceries"},
                        {"amount": -30_000, "category_name": "Meal delivery"},
                    ],
                }
            ],
            period_type="semana",
            period_label="Semana (lun 17/03 - mié 19/03)",
            period_start=date(2026, 3, 17),
            period_end=PERIOD_END,
        )

        assert summary.total_spent == 100_000
        assert [c.category_name for c in summary.category_breakdown] == ["Groceries", "Meal delivery"]
        assert [c.amount for c in summary.category_breakdown] == [70_000, 30_000]


# ---------------------------------------------------------------------------
# Expense filtering — positive amounts must be ignored
# ---------------------------------------------------------------------------

class TestExpenseFiltering:
    def test_income_ignored_from_total(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[
                make_txn(-20_000, "Comida"),
                make_txn(50_000, "Sueldo"),   # income — must be ignored
            ],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert summary.total_spent == 20_000

    def test_income_not_in_breakdown(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[
                make_txn(-20_000, "Comida"),
                make_txn(50_000, "Sueldo"),
            ],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        names = [c.category_name for c in summary.category_breakdown]
        assert "Sueldo" not in names

    def test_only_income_means_no_transactions(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(100_000, "Sueldo")],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert summary.has_transactions is False

    def test_zero_amount_ignored(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(0, "Ajuste")],
            period_type="dia",
            period_label="Hoy (19/03)",
            period_start=PERIOD_END,
            period_end=PERIOD_END,
        )
        assert summary.has_transactions is False


# ---------------------------------------------------------------------------
# Budget comparison — only populated when budget_data is provided
# ---------------------------------------------------------------------------

class TestBudgetComparison:
    def _budget_data(self):
        return [
            {"name": "Supermercado", "budgeted": 500_000, "activity": -350_000, "balance": 150_000},
            {"name": "Restaurantes", "budgeted": 200_000, "activity": -250_000, "balance": -50_000},  # overspent
            {"name": "Transporte",   "budgeted": 100_000, "activity": 0, "balance": 100_000},
        ]

    def test_budget_comparison_none_when_not_provided(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-10_000)],
            period_type="semana",
            period_label="Semana",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert summary.budget_comparison is None

    def test_budget_comparison_populated_for_monthly(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-10_000)],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            budget_data=self._budget_data(),
        )
        assert summary.budget_comparison is not None
        assert len(summary.budget_comparison) == 3

    def test_remaining_positive_when_under_budget(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-10_000)],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            budget_data=self._budget_data(),
        )
        supermercado = next(c for c in summary.budget_comparison if c.category_name == "Supermercado")
        assert supermercado.budgeted == 500_000
        assert supermercado.spent == 350_000
        assert supermercado.remaining == 150_000

    def test_remaining_negative_when_overspent(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-10_000)],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            budget_data=self._budget_data(),
        )
        restaurantes = next(c for c in summary.budget_comparison if c.category_name == "Restaurantes")
        assert restaurantes.remaining == -50_000

    def test_balance_is_used_when_present_in_budget_data(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-10_000)],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            budget_data=[
                {"name": "Energy", "budgeted": 150_000_000, "activity": -172_390_000, "balance": 29_831_830},
            ],
        )
        energy = summary.budget_comparison[0]
        assert energy.remaining == 29_831_830

    def test_empty_budget_data_gives_empty_list(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-10_000)],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            budget_data=[],
        )
        assert summary.budget_comparison == []

    def test_monthly_spending_uses_transaction_splits_for_totals_and_categories(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[
                {
                    "amount": -655_725_000,
                    "category_name": "Split (Multiple Categories)",
                    "subtransactions": [
                        {"amount": -500_000_000, "category_name": "Groceries"},
                        {"amount": -155_725_000, "category_name": "Meal delivery"},
                    ],
                },
                make_txn(-345_500_000, "Meal delivery"),
            ],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            budget_data=[
                {
                    "name": "Meal delivery",
                    "budgeted": 811_055_000,
                    "activity": -655_725_000,
                    "balance": 155_330_000,
                },
                {
                    "name": "Groceries",
                    "budgeted": 900_000_000,
                    "activity": -120_000_000,
                    "balance": 780_000_000,
                },
            ],
        )

        assert summary.total_spent == 1_001_225_000
        assert summary.category_breakdown[0].category_name == "Meal delivery"
        assert summary.category_breakdown[0].amount == 501_225_000

    def test_budget_comparison_none_for_dia_period(self):
        """budget_data is None (not passed) for non-monthly periods."""
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-10_000)],
            period_type="dia",
            period_label="Hoy (19/03)",
            period_start=PERIOD_END,
            period_end=PERIOD_END,
            # budget_data intentionally omitted
        )
        assert summary.budget_comparison is None

    def test_budget_comparison_type(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            budget_data=self._budget_data(),
        )
        for item in summary.budget_comparison:
            assert isinstance(item, CategoryBudgetComparison)

    def test_monthly_summary_gets_default_top_categories_insight(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[
                make_txn(-50_000, "Comida"),
                make_txn(-10_000, "Transporte"),
            ],
            period_type="mes",
            period_label="Marzo 2026",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            budget_data=self._budget_data(),
        )
        assert summary.monthly_insight is not None
        assert summary.monthly_insight.top_categories[0].category_name == "Comida"


# ---------------------------------------------------------------------------
# CategorySpending reuse
# ---------------------------------------------------------------------------

class TestCategorySpendingReuse:
    def test_breakdown_items_are_category_spending(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[make_txn(-10_000, "Comida")],
            period_type="dia",
            period_label="Hoy (19/03)",
            period_start=PERIOD_END,
            period_end=PERIOD_END,
        )
        for item in summary.category_breakdown:
            assert isinstance(item, CategorySpending)

    def test_missing_category_name_defaults_to_sin_categoria(self):
        summary = OnDemandSummary.from_transactions(
            transactions=[{"amount": -5_000}],  # no category_name key
            period_type="dia",
            period_label="Hoy (19/03)",
            period_start=PERIOD_END,
            period_end=PERIOD_END,
        )
        assert summary.category_breakdown[0].category_name == "Sin categoría"

"""Tests for WeeklySummary domain model."""
import pytest
from datetime import date

from domain.models.weekly_summary import CategorySpending, WeeklySummary


WEEK_START = date(2026, 3, 9)   # Monday
WEEK_END   = date(2026, 3, 15)  # Sunday


# ---------------------------------------------------------------------------
# CategorySpending
# ---------------------------------------------------------------------------

class TestCategorySpending:
    def test_fields(self):
        cs = CategorySpending(category_name="Comida", amount=50_000)
        assert cs.category_name == "Comida"
        assert cs.amount == 50_000


# ---------------------------------------------------------------------------
# WeeklySummary.from_transactions — empty / no transactions
# ---------------------------------------------------------------------------

class TestWeeklySummaryEmpty:
    def test_empty_current_week(self):
        summary = WeeklySummary.from_transactions(
            current_week_txns=[],
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.has_transactions is False
        assert summary.total_spent == 0
        assert summary.previous_week_total == 0
        assert summary.percentage_change is None
        assert summary.category_breakdown == []
        assert summary.top_categories == []
        assert summary.week_start == WEEK_START
        assert summary.week_end == WEEK_END

    def test_income_only_transactions_treated_as_empty(self):
        """Positive-amount transactions (income) should be ignored."""
        income_txns = [
            {"amount": 500_000, "category_name": "Ingreso"},
            {"amount": 200_000, "category_name": "Bono"},
        ]
        summary = WeeklySummary.from_transactions(
            current_week_txns=income_txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.has_transactions is False
        assert summary.total_spent == 0


# ---------------------------------------------------------------------------
# Single transaction
# ---------------------------------------------------------------------------

class TestWeeklySummarySingleTransaction:
    def setup_method(self):
        self.txns = [{"amount": -150_000, "category_name": "Transporte"}]
        self.summary = WeeklySummary.from_transactions(
            current_week_txns=self.txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )

    def test_has_transactions(self):
        assert self.summary.has_transactions is True

    def test_total_spent_is_positive(self):
        assert self.summary.total_spent == 150_000

    def test_category_breakdown_single_entry(self):
        assert len(self.summary.category_breakdown) == 1
        assert self.summary.category_breakdown[0].category_name == "Transporte"
        assert self.summary.category_breakdown[0].amount == 150_000

    def test_top_categories_equals_breakdown_when_fewer_than_three(self):
        assert self.summary.top_categories == self.summary.category_breakdown

    def test_no_previous_week_percentage_change_is_none(self):
        assert self.summary.percentage_change is None

    def test_previous_week_total_zero(self):
        assert self.summary.previous_week_total == 0


# ---------------------------------------------------------------------------
# Multiple categories — sorting and top-3 selection
# ---------------------------------------------------------------------------

class TestWeeklySummaryMultipleCategories:
    def setup_method(self):
        self.txns = [
            {"amount": -100_000, "category_name": "Comida"},
            {"amount": -200_000, "category_name": "Entretenimiento"},
            {"amount": -50_000,  "category_name": "Transporte"},
            {"amount": -300_000, "category_name": "Renta"},
            {"amount": -75_000,  "category_name": "Salud"},
            # Same category, second transaction — should aggregate
            {"amount": -100_000, "category_name": "Comida"},
        ]
        self.summary = WeeklySummary.from_transactions(
            current_week_txns=self.txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )

    def test_total_spent_aggregates_all_expenses(self):
        # 100k + 200k + 50k + 300k + 75k + 100k = 825_000
        assert self.summary.total_spent == 825_000

    def test_category_breakdown_sorted_desc(self):
        amounts = [c.amount for c in self.summary.category_breakdown]
        assert amounts == sorted(amounts, reverse=True)

    def test_category_aggregation(self):
        """Comida appears twice — amounts should be summed."""
        comida = next(c for c in self.summary.category_breakdown if c.category_name == "Comida")
        assert comida.amount == 200_000

    def test_top_categories_is_first_three(self):
        assert self.summary.top_categories == self.summary.category_breakdown[:3]

    def test_top_categories_length(self):
        assert len(self.summary.top_categories) == 3

    def test_top_category_is_highest_spender(self):
        assert self.summary.top_categories[0].category_name == "Renta"
        assert self.summary.top_categories[0].amount == 300_000

    def test_breakdown_contains_all_unique_categories(self):
        names = {c.category_name for c in self.summary.category_breakdown}
        assert names == {"Comida", "Entretenimiento", "Transporte", "Renta", "Salud"}


# ---------------------------------------------------------------------------
# Top-3 selection when fewer than 3 categories
# ---------------------------------------------------------------------------

class TestTop3Selection:
    def test_two_categories_top_categories_has_two(self):
        txns = [
            {"amount": -100_000, "category_name": "A"},
            {"amount": -50_000,  "category_name": "B"},
        ]
        summary = WeeklySummary.from_transactions(
            current_week_txns=txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert len(summary.top_categories) == 2

    def test_exactly_three_categories(self):
        txns = [
            {"amount": -100_000, "category_name": "A"},
            {"amount": -200_000, "category_name": "B"},
            {"amount": -50_000,  "category_name": "C"},
        ]
        summary = WeeklySummary.from_transactions(
            current_week_txns=txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert len(summary.top_categories) == 3

    def test_more_than_three_categories_top_three_only(self):
        txns = [
            {"amount": -amt, "category_name": chr(65 + i)}
            for i, amt in enumerate([500_000, 400_000, 300_000, 200_000, 100_000])
        ]
        summary = WeeklySummary.from_transactions(
            current_week_txns=txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert len(summary.top_categories) == 3
        assert summary.top_categories[0].amount == 500_000


# ---------------------------------------------------------------------------
# Percentage change
# ---------------------------------------------------------------------------

class TestPercentageChange:
    def _make_txns(self, total_milliunits: int) -> list:
        return [{"amount": -total_milliunits, "category_name": "Varios"}]

    def test_increase(self):
        """Spent more this week than last."""
        summary = WeeklySummary.from_transactions(
            current_week_txns=self._make_txns(1_200_000),
            previous_week_txns=self._make_txns(1_000_000),
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.percentage_change == pytest.approx(20.0)

    def test_decrease(self):
        """Spent less this week than last."""
        summary = WeeklySummary.from_transactions(
            current_week_txns=self._make_txns(800_000),
            previous_week_txns=self._make_txns(1_000_000),
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.percentage_change == pytest.approx(-20.0)

    def test_same_spending(self):
        summary = WeeklySummary.from_transactions(
            current_week_txns=self._make_txns(1_000_000),
            previous_week_txns=self._make_txns(1_000_000),
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.percentage_change == pytest.approx(0.0)

    def test_no_previous_week_spending(self):
        """If previous week had no expenses, percentage_change is None."""
        summary = WeeklySummary.from_transactions(
            current_week_txns=self._make_txns(500_000),
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.percentage_change is None

    def test_previous_week_income_only_treated_as_zero(self):
        """Income-only previous week counts as zero spending → None percentage."""
        summary = WeeklySummary.from_transactions(
            current_week_txns=self._make_txns(500_000),
            previous_week_txns=[{"amount": 300_000, "category_name": "Ingreso"}],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.percentage_change is None

    def test_no_current_week_spending_with_previous(self):
        """Spent nothing this week but had spending last week → -100%."""
        summary = WeeklySummary.from_transactions(
            current_week_txns=[],
            previous_week_txns=self._make_txns(1_000_000),
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.percentage_change == pytest.approx(-100.0)


# ---------------------------------------------------------------------------
# Negative amounts (YNAB convention: expenses are negative)
# ---------------------------------------------------------------------------

class TestNegativeAmounts:
    def test_expenses_stored_positive_in_category_spending(self):
        """CategorySpending.amount should always be positive (absolute value)."""
        txns = [{"amount": -75_500, "category_name": "Gym"}]
        summary = WeeklySummary.from_transactions(
            current_week_txns=txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.category_breakdown[0].amount > 0
        assert summary.category_breakdown[0].amount == 75_500

    def test_total_spent_positive_even_when_all_amounts_negative(self):
        txns = [
            {"amount": -300_000, "category_name": "A"},
            {"amount": -200_000, "category_name": "B"},
        ]
        summary = WeeklySummary.from_transactions(
            current_week_txns=txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.total_spent == 500_000

    def test_mixed_positive_negative_only_expenses_counted(self):
        """Income (positive) amounts must not affect total_spent."""
        txns = [
            {"amount": -400_000, "category_name": "Renta"},
            {"amount":  100_000, "category_name": "Reembolso"},  # income
        ]
        summary = WeeklySummary.from_transactions(
            current_week_txns=txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.total_spent == 400_000
        category_names = {c.category_name for c in summary.category_breakdown}
        assert "Reembolso" not in category_names


# ---------------------------------------------------------------------------
# Metadata fields
# ---------------------------------------------------------------------------

class TestWeeklySummaryMetadata:
    def test_week_start_end_preserved(self):
        ws = date(2026, 3, 2)
        we = date(2026, 3, 8)
        summary = WeeklySummary.from_transactions(
            current_week_txns=[],
            previous_week_txns=[],
            week_start=ws,
            week_end=we,
        )
        assert summary.week_start == ws
        assert summary.week_end == we

    def test_no_category_name_defaults_to_sin_categoria(self):
        """Transactions without a category_name key should use 'Sin categoría' as the internal fallback label."""
        txns = [{"amount": -100_000}]  # no category_name key
        summary = WeeklySummary.from_transactions(
            current_week_txns=txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.category_breakdown[0].category_name == "Sin categoría"

    def test_none_category_name_defaults_to_sin_categoria(self):
        txns = [{"amount": -100_000, "category_name": None}]
        summary = WeeklySummary.from_transactions(
            current_week_txns=txns,
            previous_week_txns=[],
            week_start=WEEK_START,
            week_end=WEEK_END,
        )
        assert summary.category_breakdown[0].category_name == "Sin categoría"

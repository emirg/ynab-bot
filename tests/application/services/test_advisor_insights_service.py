from datetime import date

from application.services.advisor_insights_service import AdvisorInsightsService
from domain.models.advisor_dashboard import AdvisorBudgetStatus
from domain.models.weekly_summary import CategorySpending


def test_build_insights_returns_empty_for_no_transactions():
    service = AdvisorInsightsService()

    insights = service.build_insights(
        period_type="mes",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 12),
        total_spent=0,
        transaction_count=0,
        top_categories=[],
        budget_data=[],
        budget_status=[],
    )

    assert insights == []


def test_build_insights_returns_all_clear_when_no_signals():
    service = AdvisorInsightsService()

    insights = service.build_insights(
        period_type="mes",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 12),
        total_spent=54_000,
        transaction_count=3,
        top_categories=[
            CategorySpending(category_name="Comida", amount=20_000),
            CategorySpending(category_name="Transporte", amount=18_000),
            CategorySpending(category_name="Salud", amount=16_000),
        ],
        budget_data=[
            {"name": "Comida", "budgeted": 120_000, "activity": -20_000},
            {"name": "Transporte", "budgeted": 100_000, "activity": -18_000},
            {"name": "Salud", "budgeted": 90_000, "activity": -16_000},
        ],
        budget_status=[
            AdvisorBudgetStatus("Comida", 120_000, 20_000, 100_000, "within_budget"),
            AdvisorBudgetStatus("Transporte", 100_000, 18_000, 82_000, "within_budget"),
            AdvisorBudgetStatus("Salud", 90_000, 16_000, 74_000, "within_budget"),
        ],
    )

    assert [item.code for item in insights] == ["all_clear"]

from datetime import date
from unittest.mock import MagicMock, patch

from application.services.advisor_dashboard_service import AdvisorDashboardService
from application.services.advisor_insights_service import AdvisorInsightsService
from application.services.budget_query_service import BudgetQueryService
from application.services.on_demand_summary_service import OnDemandSummaryService
from domain.models.user import UserConfiguration, UserStatus, YNABCategory


def _configured_user() -> UserConfiguration:
    return UserConfiguration(
        telegram_id=123,
        status=UserStatus.AUTHORIZED,
        budget_id="budget-1",
        default_account_id="acc-1",
        default_account_name="Cuenta principal",
        ynab_access_token="token",
        timezone="America/Bogota",
    )


def _txn(amount: int, txn_date: str, category_name: str) -> dict:
    return {
        "amount": amount,
        "date": txn_date,
        "category_name": category_name,
        "deleted": False,
    }


def _month_transactions() -> list[dict]:
    return [
        {
            "amount": -655_725,
            "date": "2026-04-10",
            "category_name": "Split (Multiple Categories)",
            "subtransactions": [
                {"amount": -500_000, "category_name": "Groceries"},
                {"amount": -155_725, "category_name": "Meal delivery"},
            ],
        },
        _txn(-345_500, "2026-04-11", "Meal delivery"),
        _txn(50_000, "2026-04-11", "Ingreso"),
    ]


def _month_categories() -> list[YNABCategory]:
    return [
        YNABCategory(
            id="1",
            name="Meal delivery",
            group_name="Casa",
            full_name="Casa -> Meal delivery",
            budgeted=811_055,
            activity=-655_725,
            balance=155_330,
        ),
        YNABCategory(
            id="2",
            name="Groceries",
            group_name="Casa",
            full_name="Casa -> Groceries",
            budgeted=900_000,
            activity=-120_000,
            balance=780_000,
        ),
    ]


@patch("application.services.on_demand_summary_service.user_today")
@patch("application.services.advisor_dashboard_service.user_today")
def test_monthly_spending_is_consistent_across_summary_advisor_and_budget_query(
    mock_advisor_today,
    mock_summary_today,
):
    mock_summary_today.return_value = date(2026, 4, 12)
    mock_advisor_today.return_value = date(2026, 4, 12)

    user = _configured_user()
    transactions = _month_transactions()
    categories = _month_categories()

    summary_repo = MagicMock()
    summary_repo.get_transactions.return_value = transactions
    summary_repo.get_categories.return_value = categories
    summary_factory = MagicMock()
    summary_factory.get_repository.return_value = summary_repo
    summary_service = OnDemandSummaryService(summary_factory)

    advisor_repo = MagicMock()
    advisor_repo.get_transactions.return_value = transactions
    advisor_repo.get_categories.return_value = categories
    advisor_factory = MagicMock()
    advisor_factory.get_repository.return_value = advisor_repo
    user_repository = MagicMock()
    user_repository.find_by_telegram_id.return_value = user
    advisor_service = AdvisorDashboardService(
        user_repository,
        advisor_factory,
        AdvisorInsightsService(),
    )

    budget_query_service = BudgetQueryService()

    monthly_summary = summary_service.generate_summary(user, "mes")
    advisor_dashboard = advisor_service.build_dashboard(user.telegram_id, "mes")
    budget_summary = budget_query_service.execute_query(
        "budget_summary",
        None,
        categories,
        [],
        transactions=transactions,
    )

    assert monthly_summary.total_spent == 1_001_225
    assert advisor_dashboard.summary.total_spent == monthly_summary.total_spent
    assert budget_summary.data["total_spent"] == monthly_summary.total_spent

    assert monthly_summary.category_breakdown[0].category_name == "Meal delivery"
    assert monthly_summary.category_breakdown[0].amount == 501_225
    assert advisor_dashboard.top_categories[0].category_name == "Meal delivery"
    assert advisor_dashboard.top_categories[0].amount == 501_225
    assert budget_summary.data["top_spending"][0]["name"] == "Meal delivery"
    assert budget_summary.data["top_spending"][0]["spent"] == 501_225


@patch("application.services.on_demand_summary_service.user_today")
@patch("application.services.advisor_dashboard_service.user_today")
def test_monthly_budget_health_uses_ynab_balance_consistently_across_surfaces(
    mock_advisor_today,
    mock_summary_today,
):
    mock_summary_today.return_value = date(2026, 4, 12)
    mock_advisor_today.return_value = date(2026, 4, 12)

    user = _configured_user()
    transactions = [_txn(-172_390, "2026-04-10", "Energy")]
    categories = [
        YNABCategory(
            id="1",
            name="Energy",
            group_name="Servicios",
            full_name="Servicios -> Energy",
            budgeted=150_000,
            activity=-172_390,
            balance=29_831,
        )
    ]

    summary_repo = MagicMock()
    summary_repo.get_transactions.return_value = transactions
    summary_repo.get_categories.return_value = categories
    summary_factory = MagicMock()
    summary_factory.get_repository.return_value = summary_repo
    summary_service = OnDemandSummaryService(summary_factory)

    advisor_repo = MagicMock()
    advisor_repo.get_transactions.return_value = transactions
    advisor_repo.get_categories.return_value = categories
    advisor_factory = MagicMock()
    advisor_factory.get_repository.return_value = advisor_repo
    user_repository = MagicMock()
    user_repository.find_by_telegram_id.return_value = user
    advisor_service = AdvisorDashboardService(
        user_repository,
        advisor_factory,
        AdvisorInsightsService(),
    )

    monthly_summary = summary_service.generate_summary(user, "mes")
    advisor_dashboard = advisor_service.build_dashboard(user.telegram_id, "mes")

    assert monthly_summary.budget_comparison[0].remaining == 29_831
    assert monthly_summary.monthly_insight.overspent_categories == []
    assert advisor_dashboard.budget_status[0].remaining == 29_831
    assert advisor_dashboard.budget_status[0].status == "within_budget"

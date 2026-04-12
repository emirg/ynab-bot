from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from application.services.advisor_dashboard_service import AdvisorDashboardService
from domain.models.user import UserConfiguration, UserStatus, YNABCategory


@pytest.fixture
def dashboard_service():
    user_repository = MagicMock()
    ynab_factory = MagicMock()
    service = AdvisorDashboardService(user_repository, ynab_factory)
    return service, user_repository, ynab_factory


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
    }


def test_parse_period_defaults_to_month(dashboard_service):
    service, _, _ = dashboard_service
    assert service.parse_period(None) == "mes"


def test_parse_period_rejects_invalid_value(dashboard_service):
    service, _, _ = dashboard_service
    with pytest.raises(ValueError, match="Período no válido"):
        service.parse_period("ano")


@patch("application.services.advisor_dashboard_service.user_today")
def test_build_dashboard_for_month_returns_metrics_and_budget_status(mock_today, dashboard_service):
    service, user_repository, ynab_factory = dashboard_service
    user_repository.find_by_telegram_id.return_value = _configured_user()
    mock_today.return_value = date(2026, 4, 12)

    ynab_repo = MagicMock()
    ynab_repo.get_transactions.return_value = [
        _txn(-30_000, "2026-04-01", "Comida"),
        _txn(-10_000, "2026-04-02", "Transporte"),
        _txn(50_000, "2026-04-02", "Ingreso"),
        _txn(-20_000, "2026-04-12", "Comida"),
    ]
    ynab_repo.get_categories.return_value = [
        YNABCategory(id="1", name="Comida", group_name="Casa", full_name="Casa -> Comida", budgeted=100_000, activity=-50_000),
        YNABCategory(id="2", name="Transporte", group_name="Casa", full_name="Casa -> Transporte", budgeted=40_000, activity=-10_000),
    ]
    ynab_factory.get_repository.return_value = ynab_repo

    dashboard = service.build_dashboard(123, "mes")

    assert dashboard.summary.total_spent == 60_000
    assert dashboard.summary.transaction_count == 3
    assert dashboard.summary.average_daily_spent == 5_000
    assert dashboard.summary.top_category_name == "Comida"
    assert len(dashboard.trend) == 12
    assert dashboard.trend[0].label == "01"
    assert dashboard.budget_status is not None
    assert dashboard.budget_status[0].category_name == "Comida"
    ynab_repo.get_transactions.assert_called_once_with("budget-1", since_date="2026-04-01")
    ynab_repo.get_categories.assert_called_once_with("budget-1")


@patch("application.services.advisor_dashboard_service.user_today")
def test_build_dashboard_for_week_uses_monday_start_and_omits_budget_status(mock_today, dashboard_service):
    service, user_repository, ynab_factory = dashboard_service
    user_repository.find_by_telegram_id.return_value = _configured_user()
    mock_today.return_value = date(2026, 4, 9)

    ynab_repo = MagicMock()
    ynab_repo.get_transactions.return_value = [
        _txn(-8_000, "2026-04-06", "Cafe"),
        _txn(-12_000, "2026-04-09", "Mercado"),
    ]
    ynab_factory.get_repository.return_value = ynab_repo

    dashboard = service.build_dashboard(123, "semana")

    assert dashboard.period_start == date(2026, 4, 6)
    assert dashboard.period_end == date(2026, 4, 9)
    assert [point.label for point in dashboard.trend] == ["lun", "mar", "mié", "jue"]
    assert dashboard.budget_status is None
    ynab_repo.get_categories.assert_not_called()


@patch("application.services.advisor_dashboard_service.user_today")
def test_build_dashboard_for_day_creates_single_trend_point(mock_today, dashboard_service):
    service, user_repository, ynab_factory = dashboard_service
    user_repository.find_by_telegram_id.return_value = _configured_user()
    mock_today.return_value = date(2026, 4, 12)

    ynab_repo = MagicMock()
    ynab_repo.get_transactions.return_value = [_txn(-15_000, "2026-04-12", "Almuerzo")]
    ynab_factory.get_repository.return_value = ynab_repo

    dashboard = service.build_dashboard(123, "dia")

    assert len(dashboard.trend) == 1
    assert dashboard.trend[0].label == "Hoy"
    assert dashboard.summary.average_daily_spent == 15_000


@patch("application.services.advisor_dashboard_service.user_today")
def test_build_dashboard_without_transactions_returns_empty_dashboard(mock_today, dashboard_service):
    service, user_repository, ynab_factory = dashboard_service
    user_repository.find_by_telegram_id.return_value = _configured_user()
    mock_today.return_value = date(2026, 4, 12)

    ynab_repo = MagicMock()
    ynab_repo.get_transactions.return_value = []
    ynab_repo.get_categories.return_value = []
    ynab_factory.get_repository.return_value = ynab_repo

    dashboard = service.build_dashboard(123, "mes")

    assert dashboard.has_transactions is False
    assert dashboard.summary.total_spent == 0
    assert dashboard.top_categories == []

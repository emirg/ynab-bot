from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from application.services.advisor_dashboard_service import AdvisorDashboardService
from application.services.advisor_insights_service import AdvisorInsightsService
from domain.models.user import UserConfiguration, UserStatus, YNABCategory


@pytest.fixture
def dashboard_service():
    user_repository = MagicMock()
    ynab_factory = MagicMock()
    service = AdvisorDashboardService(user_repository, ynab_factory, AdvisorInsightsService())
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
    assert dashboard.insights == []


@patch("application.services.advisor_dashboard_service.user_today")
def test_build_dashboard_emits_warning_insights_for_budget_pressure(mock_today, dashboard_service):
    service, user_repository, ynab_factory = dashboard_service
    user_repository.find_by_telegram_id.return_value = _configured_user()
    mock_today.return_value = date(2026, 4, 12)

    ynab_repo = MagicMock()
    ynab_repo.get_transactions.return_value = [
        _txn(-90_000, "2026-04-03", "Comida"),
        _txn(-30_000, "2026-04-08", "Comida"),
        _txn(-15_000, "2026-04-10", "Transporte"),
    ]
    ynab_repo.get_categories.return_value = [
        YNABCategory(id="1", name="Comida", group_name="Casa", full_name="Casa -> Comida", budgeted=100_000, activity=-120_000),
        YNABCategory(id="2", name="Transporte", group_name="Casa", full_name="Casa -> Transporte", budgeted=30_000, activity=-15_000),
        YNABCategory(id="3", name="Ahorro viaje", group_name="Metas", full_name="Metas -> Ahorro viaje", budgeted=80_000, activity=0),
    ]
    ynab_factory.get_repository.return_value = ynab_repo

    dashboard = service.build_dashboard(123, "mes")

    insight_codes = {item.code for item in dashboard.insights}
    assert "spending_concentration" in insight_codes
    assert "monthly_pace_warning" in insight_codes
    assert "overspent_category" in insight_codes
    assert "inactive_budget" in insight_codes
    assert "all_clear" not in insight_codes

    concentration = next(item for item in dashboard.insights if item.code == "spending_concentration")
    assert concentration.evidence["category_name"] == "Comida"
    assert concentration.evidence["share_percent"] == 89


@patch("application.services.advisor_dashboard_service.user_today")
def test_build_dashboard_emits_all_clear_when_no_signals_are_detected(mock_today, dashboard_service):
    service, user_repository, ynab_factory = dashboard_service
    user_repository.find_by_telegram_id.return_value = _configured_user()
    mock_today.return_value = date(2026, 4, 12)

    ynab_repo = MagicMock()
    ynab_repo.get_transactions.return_value = [
        _txn(-20_000, "2026-04-03", "Comida"),
        _txn(-18_000, "2026-04-08", "Transporte"),
        _txn(-16_000, "2026-04-10", "Salud"),
    ]
    ynab_repo.get_categories.return_value = [
        YNABCategory(id="1", name="Comida", group_name="Casa", full_name="Casa -> Comida", budgeted=120_000, activity=-20_000),
        YNABCategory(id="2", name="Transporte", group_name="Casa", full_name="Casa -> Transporte", budgeted=100_000, activity=-18_000),
        YNABCategory(id="3", name="Salud", group_name="Casa", full_name="Casa -> Salud", budgeted=90_000, activity=-16_000),
    ]
    ynab_factory.get_repository.return_value = ynab_repo

    dashboard = service.build_dashboard(123, "mes")

    assert [item.code for item in dashboard.insights] == ["all_clear"]
    payload = dashboard.to_payload()
    assert payload["insights"][0]["severity"] == "positive"
    assert payload["insights"][0]["code"] == "all_clear"

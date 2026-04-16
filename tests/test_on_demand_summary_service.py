"""Tests for OnDemandSummaryService."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from application.services.on_demand_summary_service import OnDemandSummaryService
from domain.models.on_demand_summary import OnDemandSummary
from domain.models.user import UserConfiguration, UserStatus, YNABCategory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(
    *,
    budget_id: str = "budget-1",
    timezone: str = "UTC",
) -> UserConfiguration:
    user = UserConfiguration(telegram_id=12345)
    user.status = UserStatus.AUTHORIZED
    user.budget_id = budget_id
    user.default_account_id = "acct-1"
    user.ynab_access_token = "token-123"
    user.timezone = timezone
    return user


def _make_txn(amount: int, category_name: str, txn_date: str) -> dict:
    return {
        "amount": amount,
        "category_name": category_name,
        "date": txn_date,
        "deleted": False,
    }


def _make_category(
    name: str,
    budgeted: int = 0,
    activity: int = 0,
    balance: int | None = None,
    hidden: bool = False,
    deleted: bool = False,
) -> YNABCategory:
    return YNABCategory(
        id=f"cat-{name}",
        name=name,
        group_name="Group",
        full_name=f"Group: {name}",
        budgeted=budgeted,
        activity=activity,
        balance=(budgeted + activity) if balance is None else balance,
        hidden=hidden,
        deleted=deleted,
    )


def _make_service(transactions=None, categories=None):
    """Return an OnDemandSummaryService with mocked YNAB factory."""
    mock_factory = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_transactions.return_value = transactions or []
    mock_repo.get_categories.return_value = categories or []
    mock_factory.get_repository.return_value = mock_repo

    service = OnDemandSummaryService(ynab_factory=mock_factory)
    return service, mock_repo, mock_factory


# ---------------------------------------------------------------------------
# parse_period
# ---------------------------------------------------------------------------

class TestParsePeriod:

    @pytest.mark.parametrize("input_str,expected", [
        ("dia",    "dia"),
        ("día",    "dia"),
        ("hoy",    "dia"),
        ("today",  "dia"),
        ("DIA",    "dia"),
        ("HOY",    "dia"),
        ("semana", "semana"),
        ("week",   "semana"),
        ("SEMANA", "semana"),
        ("mes",    "mes"),
        ("month",  "mes"),
        ("MES",    "mes"),
        ("",       "mes"),     # default is mes
        ("  ",     "mes"),     # whitespace -> empty -> mes
    ])
    def test_valid_aliases(self, input_str, expected):
        service = OnDemandSummaryService(ynab_factory=MagicMock())
        assert service.parse_period(input_str) == expected

    @pytest.mark.parametrize("bad_input", [
        "año", "year", "yesterday", "ayer", "trimestre", "quincena",
    ])
    def test_invalid_input_raises_value_error(self, bad_input):
        service = OnDemandSummaryService(ynab_factory=MagicMock())
        with pytest.raises(ValueError, match=bad_input):
            service.parse_period(bad_input)


# ---------------------------------------------------------------------------
# Date range computation
# ---------------------------------------------------------------------------

class TestComputeDateRange:

    def test_dia_range_is_today_to_today(self):
        today = date(2026, 3, 19)
        start, end = OnDemandSummaryService._compute_date_range("dia", today)
        assert start == today
        assert end == today

    def test_semana_range_starts_on_monday(self):
        # 2026-03-19 is a Thursday (weekday=3)
        today = date(2026, 3, 19)
        start, end = OnDemandSummaryService._compute_date_range("semana", today)
        assert start == date(2026, 3, 16)  # Monday
        assert end == today

    def test_semana_range_when_today_is_monday(self):
        # 2026-03-16 is a Monday
        today = date(2026, 3, 16)
        start, end = OnDemandSummaryService._compute_date_range("semana", today)
        assert start == date(2026, 3, 16)
        assert end == today

    def test_mes_range_starts_on_first(self):
        today = date(2026, 3, 19)
        start, end = OnDemandSummaryService._compute_date_range("mes", today)
        assert start == date(2026, 3, 1)
        assert end == today

    def test_mes_range_on_first_of_month(self):
        today = date(2026, 3, 1)
        start, end = OnDemandSummaryService._compute_date_range("mes", today)
        assert start == date(2026, 3, 1)
        assert end == date(2026, 3, 1)

    def test_unknown_period_type_raises(self):
        with pytest.raises(ValueError):
            OnDemandSummaryService._compute_date_range("trimestre", date(2026, 3, 19))


# ---------------------------------------------------------------------------
# Spanish period label builder
# ---------------------------------------------------------------------------

class TestBuildPeriodLabel:

    def test_dia_label(self):
        label = OnDemandSummaryService._build_period_label(
            "dia", date(2026, 3, 19), date(2026, 3, 19)
        )
        assert label == "Hoy (19/03)"

    def test_dia_label_single_digit_day(self):
        label = OnDemandSummaryService._build_period_label(
            "dia", date(2026, 3, 1), date(2026, 3, 1)
        )
        assert label == "Hoy (01/03)"

    def test_semana_label_thursday(self):
        # Mon 2026-03-16 -> Thu 2026-03-19
        label = OnDemandSummaryService._build_period_label(
            "semana", date(2026, 3, 16), date(2026, 3, 19)
        )
        assert label == "Semana (lun 16/03 - jue 19/03)"

    def test_semana_label_monday_to_monday(self):
        label = OnDemandSummaryService._build_period_label(
            "semana", date(2026, 3, 16), date(2026, 3, 16)
        )
        assert label == "Semana (lun 16/03 - lun 16/03)"

    def test_mes_label_march(self):
        label = OnDemandSummaryService._build_period_label(
            "mes", date(2026, 3, 1), date(2026, 3, 19)
        )
        assert label == "Mes de marzo 2026"

    def test_mes_label_december(self):
        label = OnDemandSummaryService._build_period_label(
            "mes", date(2025, 12, 1), date(2025, 12, 31)
        )
        assert label == "Mes de diciembre 2025"

    def test_mes_label_january(self):
        label = OnDemandSummaryService._build_period_label(
            "mes", date(2026, 1, 1), date(2026, 1, 15)
        )
        assert label == "Mes de enero 2026"


# ---------------------------------------------------------------------------
# generate_summary — period selection & transaction filtering
# ---------------------------------------------------------------------------

class TestGenerateSummary:

    @patch("application.services.on_demand_summary_service.user_today")
    def test_dia_fetches_from_today_and_filters(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            _make_txn(-10_000, "Comida", "2026-03-19"),   # in range
            _make_txn(-5_000, "Transporte", "2026-03-18"), # outside — before today
            _make_txn(20_000, "Ingreso", "2026-03-19"),    # positive — not expense
        ]
        service, mock_repo, _ = _make_service(transactions=txns)
        user = _make_user()

        summary = service.generate_summary(user, "dia")

        mock_repo.get_transactions.assert_called_once_with("budget-1", since_date="2026-03-19")
        assert summary.period_start == date(2026, 3, 19)
        assert summary.period_end == date(2026, 3, 19)
        assert summary.total_spent == 10_000
        assert len(summary.category_breakdown) == 1
        assert summary.budget_comparison is None

    @patch("application.services.on_demand_summary_service.user_today")
    def test_semana_fetches_from_monday_and_filters(self, mock_today):
        # Thursday 2026-03-19 -> Monday is 2026-03-16
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            _make_txn(-10_000, "Comida", "2026-03-16"),   # Monday — in range
            _make_txn(-8_000, "Comida", "2026-03-19"),    # Thursday — in range
            _make_txn(-5_000, "Transporte", "2026-03-15"), # Sunday before — outside
        ]
        service, mock_repo, _ = _make_service(transactions=txns)
        user = _make_user()

        summary = service.generate_summary(user, "semana")

        mock_repo.get_transactions.assert_called_once_with("budget-1", since_date="2026-03-16")
        assert summary.period_start == date(2026, 3, 16)
        assert summary.period_end == date(2026, 3, 19)
        assert summary.total_spent == 18_000
        assert summary.budget_comparison is None

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_fetches_from_first_and_includes_categories(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            _make_txn(-30_000, "Comida", "2026-03-01"),
            _make_txn(-10_000, "Transporte", "2026-03-10"),
        ]
        categories = [
            _make_category("Comida", budgeted=100_000, activity=-30_000),
            _make_category("Transporte", budgeted=50_000, activity=-10_000),
            _make_category("Ahorro", budgeted=0, activity=0),  # excluded (0/0)
        ]
        service, mock_repo, _ = _make_service(transactions=txns, categories=categories)
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        mock_repo.get_transactions.assert_called_once_with("budget-1", since_date="2026-03-01")
        mock_repo.get_categories.assert_called_once_with("budget-1")
        assert summary.period_start == date(2026, 3, 1)
        assert summary.period_end == date(2026, 3, 19)
        assert summary.total_spent == 40_000
        # Only 2 categories have budgeted > 0 or activity != 0
        assert summary.budget_comparison is not None
        assert len(summary.budget_comparison) == 2
        assert summary.monthly_insight is not None

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_builds_only_overspent_insights(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            _make_txn(-30_000, "Comida", "2026-03-01"),
            _make_txn(-10_000, "Transporte", "2026-03-10"),
        ]
        categories = [
            _make_category("Comida", budgeted=100_000, activity=-95_000),
            _make_category("Restaurantes", budgeted=50_000, activity=-70_000),
            _make_category("Transporte", budgeted=60_000, activity=-10_000),
        ]
        service, _, _ = _make_service(transactions=txns, categories=categories)
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        assert summary.monthly_insight is not None
        assert summary.monthly_insight.overspent_categories[0].category_name == "Restaurantes"
        assert summary.monthly_insight.status == "alerta"

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_uses_ynab_balance_for_carryover_instead_of_budgeted_minus_spent(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [_make_txn(-172_390_000, "Energy", "2026-03-10")]
        categories = [
            _make_category(
                "Energy",
                budgeted=150_000_000,
                activity=-172_390_000,
                balance=29_831_830,
            )
        ]
        service, _, _ = _make_service(transactions=txns, categories=categories)
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        comp = summary.budget_comparison[0]
        assert comp.remaining == 29_831_830
        assert summary.monthly_insight.overspent_categories == []
        assert summary.monthly_insight.status == "estable"

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_category_breakdown_uses_transaction_splits(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            {
                "amount": -655_725_000,
                "category_name": "Split (Multiple Categories)",
                "date": "2026-03-10",
                "subtransactions": [
                    {"amount": -500_000_000, "category_name": "Groceries"},
                    {"amount": -155_725_000, "category_name": "Meal delivery"},
                ],
            },
            _make_txn(-345_500_000, "Meal delivery", "2026-03-11"),
        ]
        categories = [
            _make_category(
                "Meal delivery",
                budgeted=811_055_000,
                activity=-655_725_000,
                balance=155_330_000,
            ),
            _make_category(
                "Groceries",
                budgeted=900_000_000,
                activity=-120_000_000,
                balance=780_000_000,
            ),
        ]
        service, _, _ = _make_service(transactions=txns, categories=categories)
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        assert summary.total_spent == 1_001_225_000
        assert summary.category_breakdown[0].category_name == "Meal delivery"
        assert summary.category_breakdown[0].amount == 501_225_000

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_category_breakdown_includes_zero_sum_shared_split_expenses(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            {
                "amount": 0,
                "category_name": "Split (Multiple Categories)",
                "date": "2026-03-10",
                "subtransactions": [
                    {"amount": -180_000, "category_name": "Restaurantes"},
                    {"amount": 180_000, "category_name": "Shared Transactions"},
                ],
            },
            _make_txn(-20_000, "Cafe", "2026-03-11"),
        ]
        categories = [
            _make_category(
                "Restaurantes",
                budgeted=500_000,
                activity=-180_000,
                balance=320_000,
            ),
            _make_category(
                "Cafe",
                budgeted=100_000,
                activity=-20_000,
                balance=80_000,
            ),
        ]
        service, _, _ = _make_service(transactions=txns, categories=categories)
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        assert summary.total_spent == 200_000
        assert summary.category_breakdown[0].category_name == "Restaurantes"
        assert summary.category_breakdown[0].amount == 180_000
        assert summary.category_breakdown[1].category_name == "Cafe"

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_total_spent_ignores_transfer_outflows(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            {
                "amount": -300_000,
                "category_name": None,
                "date": "2026-03-10",
                "transfer_account_id": "acct-savings",
                "transfer_transaction_id": "txn-savings",
            },
            _make_txn(-45_000, "Restaurantes", "2026-03-11"),
        ]
        service, _, _ = _make_service(transactions=txns, categories=[])
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        assert summary.total_spent == 45_000
        assert [c.category_name for c in summary.category_breakdown] == ["Restaurantes"]
        assert [c.amount for c in summary.category_breakdown] == [45_000]

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_total_spent_nets_category_inflows_like_reflect(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            {
                "amount": -80_000,
                "category_name": "Split (Multiple Categories)",
                "date": "2026-03-10",
                "subtransactions": [
                    {"amount": -50_000, "category_id": "cat-meal", "category_name": "Restaurantes"},
                    {"amount": -30_000, "category_id": "cat-split", "category_name": "Splitwise"},
                ],
            },
            {
                "amount": 60_000,
                "category_id": "cat-split",
                "category_name": "Splitwise",
                "date": "2026-03-11",
            },
        ]
        service, _, _ = _make_service(transactions=txns, categories=[])
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        assert summary.total_spent == 20_000
        assert [c.category_name for c in summary.category_breakdown] == ["Restaurantes", "Splitwise"]
        assert [c.amount for c in summary.category_breakdown] == [50_000, 30_000]

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_without_budget_data_sets_fallback_status(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [_make_txn(-30_000, "Comida", "2026-03-01")]
        service, _, _ = _make_service(transactions=txns, categories=[])
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        assert summary.monthly_insight is not None
        assert summary.monthly_insight.status == "sin_presupuesto"

    @patch("application.services.on_demand_summary_service.user_today")
    def test_budget_data_not_fetched_for_dia(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        service, mock_repo, _ = _make_service()
        user = _make_user()

        service.generate_summary(user, "dia")

        mock_repo.get_categories.assert_not_called()

    @patch("application.services.on_demand_summary_service.user_today")
    def test_budget_data_not_fetched_for_semana(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        service, mock_repo, _ = _make_service()
        user = _make_user()

        service.generate_summary(user, "semana")

        mock_repo.get_categories.assert_not_called()

    @patch("application.services.on_demand_summary_service.user_today")
    def test_budget_excludes_hidden_and_deleted_categories(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = []
        categories = [
            _make_category("Visible", budgeted=50_000, activity=-20_000),
            _make_category("Oculta", budgeted=10_000, activity=-5_000, hidden=True),
            _make_category("Borrada", budgeted=10_000, activity=-5_000, deleted=True),
        ]
        service, mock_repo, _ = _make_service(transactions=txns, categories=categories)
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        assert summary.budget_comparison is not None
        names = [c.category_name for c in summary.budget_comparison]
        assert "Visible" in names
        assert "Oculta" not in names
        assert "Borrada" not in names

    @patch("application.services.on_demand_summary_service.user_today")
    def test_no_transactions_returns_empty_summary(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        service, _, _ = _make_service(transactions=[])
        user = _make_user()

        summary = service.generate_summary(user, "dia")

        assert summary.has_transactions is False
        assert summary.total_spent == 0
        assert len(summary.category_breakdown) == 0

    @patch("application.services.on_demand_summary_service.user_today")
    def test_positive_amounts_ignored(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            _make_txn(50_000, "Ingreso", "2026-03-19"),
            _make_txn(20_000, "Reembolso", "2026-03-19"),
        ]
        service, _, _ = _make_service(transactions=txns)
        user = _make_user()

        summary = service.generate_summary(user, "dia")

        assert summary.total_spent == 0
        assert summary.has_transactions is False

    @patch("application.services.on_demand_summary_service.user_today")
    def test_category_breakdown_sorted_descending(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        txns = [
            _make_txn(-5_000, "Transporte", "2026-03-19"),
            _make_txn(-30_000, "Comida", "2026-03-19"),
            _make_txn(-15_000, "Ocio", "2026-03-19"),
        ]
        service, _, _ = _make_service(transactions=txns)
        user = _make_user()

        summary = service.generate_summary(user, "dia")

        amounts = [c.amount for c in summary.category_breakdown]
        assert amounts == sorted(amounts, reverse=True)
        assert summary.category_breakdown[0].category_name == "Comida"

    @patch("application.services.on_demand_summary_service.user_today")
    def test_period_label_in_summary(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        service, _, _ = _make_service()
        user = _make_user()

        summary = service.generate_summary(user, "dia")

        assert summary.period_label == "Hoy (19/03)"

    @patch("application.services.on_demand_summary_service.user_today")
    def test_uses_user_timezone(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        service, _, _ = _make_service()
        user = _make_user(timezone="America/Bogota")

        service.generate_summary(user, "dia")

        mock_today.assert_called_once_with("America/Bogota")

    @patch("application.services.on_demand_summary_service.user_today")
    def test_get_repository_called_with_user_config(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        service, _, mock_factory = _make_service()
        user = _make_user()

        service.generate_summary(user, "dia")

        mock_factory.get_repository.assert_called_once_with(user)

    @patch("application.services.on_demand_summary_service.user_today")
    def test_mes_label_in_spanish(self, mock_today):
        mock_today.return_value = date(2026, 3, 19)
        service, _, _ = _make_service(categories=[])
        user = _make_user()

        summary = service.generate_summary(user, "mes")

        assert summary.period_label == "Mes de marzo 2026"

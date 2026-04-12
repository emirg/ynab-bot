from __future__ import annotations

from datetime import date, timedelta

from domain.exceptions import AdvisorAuthenticationException
from domain.models.advisor_dashboard import AdvisorDashboard
from domain.time_utils import user_today
from domain.repositories.user_repository import UserRepository
from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory

_SPANISH_MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
_SPANISH_WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_SUPPORTED_PERIODS = ("dia", "semana", "mes")


def _monday_of_week(current: date) -> date:
    return current - timedelta(days=current.weekday())


class AdvisorDashboardService:
    def __init__(
        self,
        user_repository: UserRepository,
        ynab_factory: YNABRepositoryFactory,
    ) -> None:
        self._user_repository = user_repository
        self._ynab_factory = ynab_factory

    @staticmethod
    def parse_period(period: str | None) -> str:
        normalized = (period or "mes").strip().lower()
        if normalized not in _SUPPORTED_PERIODS:
            raise ValueError("Período no válido. Usa dia, semana o mes.")
        return normalized

    @staticmethod
    def supported_periods() -> list[str]:
        return list(_SUPPORTED_PERIODS)

    def build_dashboard(self, telegram_user_id: int, period_type: str) -> AdvisorDashboard:
        user = self._user_repository.find_by_telegram_id(telegram_user_id)
        if user is None:
            raise AdvisorAuthenticationException("Advisor session user was not found")

        if not user.has_ynab_token() or not user.budget_id:
            raise ValueError("El usuario no tiene configuracion suficiente para el dashboard.")

        today = user_today(user.timezone)
        period_start, period_end = self._compute_date_range(period_type, today)
        period_label = self._build_period_label(period_type, period_start, period_end)

        ynab_repo = self._ynab_factory.get_repository(user)
        all_transactions = ynab_repo.get_transactions(user.budget_id, since_date=period_start.isoformat())

        start_str = period_start.isoformat()
        end_str = period_end.isoformat()
        transactions = [
            txn
            for txn in all_transactions
            if start_str <= txn.get("date", "") <= end_str
        ]

        budget_data = None
        if period_type == "mes":
            budget_data = self._build_budget_data(ynab_repo.get_categories(user.budget_id))

        return AdvisorDashboard.from_ynab_data(
            period_type=period_type,
            period_label=period_label,
            period_start=period_start,
            period_end=period_end,
            transactions=transactions,
            budget_data=budget_data,
        )

    @staticmethod
    def _compute_date_range(period_type: str, today: date) -> tuple[date, date]:
        if period_type == "dia":
            return today, today
        if period_type == "semana":
            return _monday_of_week(today), today
        if period_type == "mes":
            return today.replace(day=1), today
        raise ValueError(f"period_type desconocido: '{period_type}'")

    @staticmethod
    def _build_period_label(period_type: str, period_start: date, period_end: date) -> str:
        if period_type == "dia":
            return f"Hoy ({period_end.day:02d}/{period_end.month:02d})"
        if period_type == "semana":
            start_label = f"{_SPANISH_WEEKDAYS[period_start.weekday()]} {period_start.day:02d}/{period_start.month:02d}"
            end_label = f"{_SPANISH_WEEKDAYS[period_end.weekday()]} {period_end.day:02d}/{period_end.month:02d}"
            return f"Semana ({start_label} - {end_label})"
        if period_type == "mes":
            return f"Mes de {_SPANISH_MONTHS[period_end.month - 1]} {period_end.year}"
        raise ValueError(f"period_type desconocido: '{period_type}'")

    @staticmethod
    def _build_budget_data(categories: list) -> list[dict]:
        return [
            {
                "name": category.name,
                "budgeted": category.budgeted,
                "activity": category.activity,
            }
            for category in categories
            if not category.deleted
            and not category.hidden
            and (category.budgeted > 0 or category.activity != 0)
        ]

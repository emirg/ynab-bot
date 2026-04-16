from __future__ import annotations

from datetime import date, timedelta

from application.services.advisor_insights_service import AdvisorInsightsService
from domain.exceptions import AdvisorAuthenticationException
from domain.models.advisor_dashboard import (
    AdvisorBudgetStatus,
    AdvisorDashboard,
    AdvisorSummary,
    AdvisorTrendPoint,
)
from domain.models.weekly_summary import CategorySpending
from domain.services.spending_aggregation import (
    extract_expense_entries,
    normalize_budget_category_snapshots,
    summarize_transaction_spending,
)
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
        advisor_insights_service: AdvisorInsightsService,
    ) -> None:
        self._user_repository = user_repository
        self._ynab_factory = ynab_factory
        self._advisor_insights_service = advisor_insights_service

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
            budget_data = normalize_budget_category_snapshots(
                ynab_repo.get_categories(user.budget_id)
            )

        expenses = extract_expense_entries(transactions)
        raw_expense_transactions = [txn for txn in transactions if txn.get("amount", 0) < 0]
        transaction_count = len(raw_expense_transactions)
        active_days = (period_end - period_start).days + 1

        total_spent, top_categories = self._build_top_categories(transactions)
        budget_status = None if budget_data is None else self._build_budget_status(budget_data)
        insights = self._advisor_insights_service.build_insights(
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            total_spent=total_spent,
            transaction_count=transaction_count,
            top_categories=top_categories,
            budget_data=budget_data,
            budget_status=budget_status,
        )
        return AdvisorDashboard(
            period_type=period_type,
            period_label=period_label,
            period_start=period_start,
            period_end=period_end,
            summary=AdvisorSummary(
                period_label=period_label,
                total_spent=total_spent,
                transaction_count=transaction_count,
                average_daily_spent=total_spent // active_days if active_days > 0 else 0,
                top_category_name=top_categories[0].category_name if top_categories else None,
                top_category_amount=top_categories[0].amount if top_categories else 0,
                active_days=active_days,
            ),
            trend=self._build_trend(
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                expenses=expenses,
            ),
            top_categories=top_categories,
            budget_status=budget_status,
            insights=insights,
            has_transactions=transaction_count > 0,
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
    def _build_top_categories(transactions: list[dict]) -> tuple[int, list[CategorySpending]]:
        total_spent, category_totals = summarize_transaction_spending(transactions)
        categories = sorted(
            [
                CategorySpending(category_name=name, amount=amount)
                for name, amount in category_totals.items()
            ],
            key=lambda item: item.amount,
            reverse=True,
        )
        return total_spent, categories[:5]

    @staticmethod
    def _build_trend(
        *,
        period_type: str,
        period_start: date,
        period_end: date,
        expenses: list[dict],
    ) -> list[AdvisorTrendPoint]:
        amounts_by_date: dict[str, int] = {}
        for txn in expenses:
            txn_date = txn.get("date")
            if not txn_date:
                continue
            amounts_by_date[txn_date] = amounts_by_date.get(txn_date, 0) + abs(txn["amount"])

        current = period_start
        points: list[AdvisorTrendPoint] = []
        while current <= period_end:
            points.append(
                AdvisorTrendPoint(
                    date=current,
                    label=AdvisorDashboardService._build_trend_label(period_type, current, period_start),
                    amount=amounts_by_date.get(current.isoformat(), 0),
                )
            )
            current += timedelta(days=1)
        return points

    @staticmethod
    def _build_trend_label(period_type: str, point_date: date, period_start: date) -> str:
        if period_type == "dia":
            return "Hoy"
        if period_type == "semana":
            return _SPANISH_WEEKDAYS[point_date.weekday()]
        if point_date == period_start:
            return f"{point_date.day:02d}"
        return str(point_date.day)

    @staticmethod
    def _build_budget_status(budget_data: list[dict]) -> list[AdvisorBudgetStatus]:
        statuses: list[AdvisorBudgetStatus] = []
        for entry in budget_data:
            budgeted = entry.get("budgeted", 0)
            spent = abs(entry.get("activity", 0))
            remaining = entry["balance"]
            statuses.append(
                AdvisorBudgetStatus(
                    category_name=entry["name"],
                    budgeted=budgeted,
                    spent=spent,
                    remaining=remaining,
                    status="overspent" if remaining < 0 else "within_budget",
                )
            )

        statuses.sort(key=lambda item: item.spent, reverse=True)
        return statuses[:5]

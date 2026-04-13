import logging
from datetime import date, timedelta

from domain.models.on_demand_summary import MonthlySummaryInsight, OnDemandSummary
from domain.models.user import UserConfiguration
from domain.time_utils import user_today
from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory

logger = logging.getLogger(__name__)
_AT_RISK_USAGE_THRESHOLD = 0.9

_SPANISH_MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

_SPANISH_WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _monday_of_week(d: date) -> date:
    """Return the Monday of the ISO week containing *d*."""
    return d - timedelta(days=d.weekday())


class OnDemandSummaryService:
    """Builds on-demand spending summaries for day, week, or month periods."""

    def __init__(self, ynab_factory: YNABRepositoryFactory) -> None:
        self.ynab_factory = ynab_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def parse_period(args: str) -> str:
        """Parse user input into a normalized period type.

        Accepts:
            "dia" / "día" / "hoy" / "today"  -> "dia"
            "semana" / "week"                 -> "semana"
            "mes" / "month" / "" (empty)      -> "mes"

        Raises ValueError for unrecognized input.
        """
        normalized = args.strip().lower()
        if normalized in ("dia", "día", "hoy", "today"):
            return "dia"
        if normalized in ("semana", "week"):
            return "semana"
        if normalized in ("mes", "month", ""):
            return "mes"
        raise ValueError(f"Período no reconocido: '{args}'. Usa: dia, semana o mes.")

    def generate_summary(
        self,
        user_config: UserConfiguration,
        period_type: str,
    ) -> OnDemandSummary:
        """Fetch YNAB data and return an OnDemandSummary for the requested period.

        Args:
            user_config:  The authenticated user's configuration.
            period_type:  One of "dia", "semana", "mes".
        """
        today = user_today(user_config.timezone)

        period_start, period_end = self._compute_date_range(period_type, today)
        period_label = self._build_period_label(period_type, period_start, period_end)

        ynab_repo = self.ynab_factory.get_repository(user_config)
        budget_id = user_config.budget_id

        # Fetch transactions from period_start onwards
        all_transactions = ynab_repo.get_transactions(
            budget_id, since_date=period_start.isoformat()
        )

        # Filter to the exact period window
        period_start_str = period_start.isoformat()
        period_end_str = period_end.isoformat()
        transactions = [
            t for t in all_transactions
            if period_start_str <= t.get("date", "") <= period_end_str
        ]

        # For monthly period, also fetch categories for budget comparison
        budget_data = None
        if period_type == "mes":
            categories = ynab_repo.get_categories(budget_id)
            budget_data = [
                {
                    "name": cat.name,
                    "budgeted": cat.budgeted,
                    "activity": cat.activity,
                    "balance": cat.balance,
                }
                for cat in categories
                if not cat.deleted
                and not cat.hidden
                and (cat.budgeted > 0 or cat.activity != 0)
            ]

        summary = OnDemandSummary.from_transactions(
            transactions=transactions,
            period_type=period_type,
            period_label=period_label,
            period_start=period_start,
            period_end=period_end,
            budget_data=budget_data,
        )
        if period_type == "mes":
            summary.monthly_insight = self._build_monthly_insight(summary)
        return summary

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_monthly_insight(summary: OnDemandSummary) -> MonthlySummaryInsight:
        """Derive concise monthly insights from budget data for the compact summary."""
        comparisons = summary.budget_comparison or []

        def usage_ratio(comp):
            total_available = comp.spent + max(comp.remaining, 0)
            if total_available <= 0:
                return 0
            return comp.spent / total_available

        overspent = sorted(
            [comp for comp in comparisons if comp.remaining < 0],
            key=lambda comp: comp.remaining,
        )
        at_risk = sorted(
            [
                comp for comp in comparisons
                if comp.remaining >= 0
                and usage_ratio(comp) >= _AT_RISK_USAGE_THRESHOLD
            ],
            key=lambda comp: (usage_ratio(comp), comp.spent),
            reverse=True,
        )
        healthy_categories_count = sum(
            1
            for comp in comparisons
            if (comp.spent > 0 or comp.budgeted > 0 or comp.remaining != 0)
            and comp not in overspent
            and comp not in at_risk
        )

        if overspent:
            worst = overspent[0]
            status = "alerta"
            status_summary = (
                f"Vas pasado en {len(overspent)} categor"
                f"{'ía' if len(overspent) == 1 else 'ías'}. "
                f"La mayor presión está en {worst.category_name}."
            )
            recommended_action = "Revisa esas categorías antes de seguir gastando este mes."
        elif at_risk:
            closest = at_risk[0]
            status = "riesgo"
            status_summary = (
                f"No vas pasado, pero ya tienes {len(at_risk)} categor"
                f"{'ía' if len(at_risk) == 1 else 'ías'} al límite. "
                f"{closest.category_name} está muy cerca de agotarse."
            )
            recommended_action = "Si puedes, frena gasto variable en esas categorías por unos días."
        elif comparisons:
            status = "estable"
            if healthy_categories_count:
                status_summary = (
                    f"Tu mes va dentro del presupuesto en {healthy_categories_count} categor"
                    f"{'ía' if healthy_categories_count == 1 else 'ías'} activas."
                )
            else:
                status_summary = "Tu mes va dentro del presupuesto por ahora."
            recommended_action = "Mantén el ritmo actual y revisa solo las categorías más activas."
        else:
            status = "sin_presupuesto"
            status_summary = "Puedo mostrarte en qué has gastado, pero no pude comparar contra presupuesto."
            recommended_action = "Usa el detalle por categorías para revisar dónde se fue el gasto."

        return MonthlySummaryInsight(
            overspent_categories=overspent[:3],
            at_risk_categories=at_risk[:3],
            top_categories=summary.category_breakdown[:3],
            healthy_categories_count=healthy_categories_count,
            status=status,
            status_summary=status_summary,
            recommended_action=recommended_action,
        )

    @staticmethod
    def _compute_date_range(period_type: str, today: date) -> tuple:
        """Return (period_start, period_end) for the given period type."""
        if period_type == "dia":
            return today, today
        if period_type == "semana":
            monday = _monday_of_week(today)
            return monday, today
        if period_type == "mes":
            first_of_month = today.replace(day=1)
            return first_of_month, today
        raise ValueError(f"period_type desconocido: '{period_type}'")

    @staticmethod
    def _build_period_label(period_type: str, period_start: date, period_end: date) -> str:
        """Build a human-readable period label in Spanish."""
        if period_type == "dia":
            return f"Hoy ({period_end.day:02d}/{period_end.month:02d})"

        if period_type == "semana":
            start_weekday = _SPANISH_WEEKDAYS[period_start.weekday()]
            end_weekday = _SPANISH_WEEKDAYS[period_end.weekday()]
            start_str = f"{start_weekday} {period_start.day:02d}/{period_start.month:02d}"
            end_str = f"{end_weekday} {period_end.day:02d}/{period_end.month:02d}"
            return f"Semana ({start_str} - {end_str})"

        if period_type == "mes":
            month_name = _SPANISH_MONTHS[period_end.month - 1]
            return f"Mes de {month_name} {period_end.year}"

        raise ValueError(f"period_type desconocido: '{period_type}'")

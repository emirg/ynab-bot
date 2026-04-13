from presentation.http.advisor_auth import (
    ADVISOR_SESSION_COOKIE,
    build_clear_session_cookie,
    get_cookie_value,
)


class AdvisorAPIHandler:
    def __init__(self, container):
        self._advisor_access_service = container.get_advisor_access_service()
        self._advisor_dashboard_service = container.get_advisor_dashboard_service()
        self._config = container.get_config()

    def handle_bootstrap(self, headers: dict) -> tuple[int, dict, dict]:
        session_token = get_cookie_value(headers, ADVISOR_SESSION_COOKIE)
        telegram_id = self._advisor_access_service.get_session_telegram_id(session_token)
        if telegram_id is None:
            return 401, {
                "status": "error",
                "error_code": "ADVISOR_AUTH_REQUIRED",
                "message": "Advisor session is missing or invalid.",
            }, {"Set-Cookie": build_clear_session_cookie(self._is_secure())}

        payload = self._advisor_access_service.get_bootstrap_payload(telegram_id)
        return 200, payload, {}

    def handle_logout(self, headers: dict) -> tuple[int, dict, dict]:
        session_token = get_cookie_value(headers, ADVISOR_SESSION_COOKIE)
        self._advisor_access_service.logout(session_token)
        return 200, {"status": "ok", "message": "Sesion cerrada."}, {
            "Set-Cookie": build_clear_session_cookie(self._is_secure())
        }

    def handle_dashboard(
        self,
        headers: dict,
        query_params: dict[str, list[str]],
    ) -> tuple[int, dict, dict]:
        session_token = get_cookie_value(headers, ADVISOR_SESSION_COOKIE)
        telegram_id = self._advisor_access_service.get_session_telegram_id(session_token)
        if telegram_id is None:
            return 401, {
                "status": "error",
                "error_code": "ADVISOR_AUTH_REQUIRED",
                "message": "Advisor session is missing or invalid.",
            }, {"Set-Cookie": build_clear_session_cookie(self._is_secure())}

        try:
            period = self._advisor_dashboard_service.parse_period(query_params.get("period", [None])[0])
        except ValueError as exc:
            return 400, {
                "status": "error",
                "error_code": "INVALID_PERIOD",
                "message": str(exc),
            }, {}

        bootstrap = self._advisor_access_service.get_bootstrap_payload(telegram_id)
        advisor_state = bootstrap["advisor_state"]

        if advisor_state in {"needs_ynab", "needs_budget", "needs_account"}:
            return 200, self._build_state_payload(advisor_state, period), {}

        dashboard = self._advisor_dashboard_service.build_dashboard(telegram_id, period)
        payload = {
            "status": "ok",
            "advisor_state": advisor_state,
            "selected_period": period,
            "available_periods": self._advisor_dashboard_service.supported_periods(),
            **dashboard.to_payload(),
            "empty_state": self._build_empty_state(advisor_state, dashboard.has_transactions, period),
        }
        return 200, payload, {}

    def _is_secure(self) -> bool:
        return self._config.resolved_advisor_base_url.startswith("https://")

    def _build_state_payload(self, advisor_state: str, period: str) -> dict:
        return {
            "status": "ok",
            "advisor_state": advisor_state,
            "selected_period": period,
            "available_periods": self._advisor_dashboard_service.supported_periods(),
            "summary": {
                "period_label": "",
                "total_spent": 0,
                "transaction_count": 0,
                "average_daily_spent": 0,
                "top_category_name": None,
                "top_category_amount": 0,
                "active_days": 0,
            },
            "trend": [],
            "top_categories": [],
            "budget_status": None,
            "insights": [],
            "empty_state": self._build_empty_state(advisor_state, False, period),
        }

    @staticmethod
    def _build_empty_state(advisor_state: str, has_transactions: bool, period: str) -> dict | None:
        if advisor_state == "needs_ynab":
            return {
                "code": "needs_ynab",
                "title": "Conecta YNAB para empezar",
                "message": "Todavía no tienes una cuenta YNAB conectada. Vuelve a Telegram y usa /connect.",
            }
        if advisor_state == "needs_budget":
            return {
                "code": "needs_budget",
                "title": "Te falta elegir un presupuesto",
                "message": "Antes de usar el advisor, selecciona tu presupuesto en Telegram con /budgets.",
            }
        if advisor_state == "needs_account":
            return {
                "code": "needs_account",
                "title": "Te falta configurar una cuenta",
                "message": "Antes de usar el advisor, selecciona tu cuenta por defecto en Telegram con /accounts.",
            }
        if has_transactions:
            return None
        return {
            "code": "no_transactions",
            "title": "Todavía no hay gastos en este período",
            "message": f"No encontré gastos para {period}. Cuando registres movimientos en YNAB, aparecerán aquí.",
        }

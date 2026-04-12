from application.services.advisor_access_service import AdvisorAccessService
from presentation.http.advisor_auth import (
    ADVISOR_SESSION_COOKIE,
    build_clear_session_cookie,
    get_cookie_value,
)


class AdvisorAPIHandler:
    def __init__(self, container):
        self._advisor_access_service = container.get_advisor_access_service()
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

    def _is_secure(self) -> bool:
        return self._config.resolved_advisor_base_url.startswith("https://")

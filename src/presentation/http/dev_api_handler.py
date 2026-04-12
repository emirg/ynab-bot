import json
import logging
from types import SimpleNamespace

from domain.models.user import UserConfiguration, UserStatus
from domain.exceptions import ExpenseParsingException, UserNotConfiguredException
from application.services.expense_service import ExpenseService
from application.services.on_demand_summary_service import OnDemandSummaryService
from presentation.http.auth import HTTPAuthError, validate_bearer_token
from presentation.http.request_models import (
    TextMessageRequestValidationError,
    parse_text_message_request,
)
from presentation.telegram.formatters import (
    BudgetQueryFormatter,
    ConfigResponseFormatter,
    ExpenseResponseFormatter,
    GeneralResponseFormatter,
    OnDemandSummaryFormatter,
)

logger = logging.getLogger(__name__)


class DevAPIHandler:
    """Development-only HTTP endpoints for local workflows."""

    def __init__(self, container):
        self.container = container
        self.config = container.get_config()
        self.auth_service = container.get_auth_service()
        self.user_repository = container.get_user_repository()
        self.user_config_service = container.get_user_config_service()
        self.onboarding_service = container.get_onboarding_service()
        self.expense_service = container.get(ExpenseService)
        self.summary_service = container.get(OnDemandSummaryService)
        self.expense_formatter = ExpenseResponseFormatter()
        self.query_formatter = BudgetQueryFormatter()
        self.config_formatter = ConfigResponseFormatter()
        self.general_formatter = GeneralResponseFormatter()
        self.summary_formatter = OnDemandSummaryFormatter()
        self.ynab_factory = container.get_ynab_factory()

    def handle_post(self, path: str, headers: dict, body: bytes) -> tuple[int, dict]:
        try:
            validate_bearer_token(headers, self.config.dev_api_key)
            if path == "/dev/bootstrap":
                return self._handle_bootstrap(body)
            if path == "/dev/messages/text":
                return self._handle_message(body)
            return 404, self._error("ROUTE_NOT_FOUND", "The requested dev route does not exist.")
        except HTTPAuthError as exc:
            return 401, self._error(exc.error_code, exc.message)
        except TextMessageRequestValidationError as exc:
            return 400, self._error(exc.error_code, exc.message)
        except Exception:
            logger.exception("Unexpected error in development HTTP handler")
            return 500, self._error("INTERNAL_ERROR", "Unexpected error handling development request.")

    def _handle_bootstrap(self, body: bytes) -> tuple[int, dict]:
        payload = self._parse_json(body)
        telegram_user_id = payload.get("telegram_user_id", 1)
        first_name = payload.get("first_name", "Dev")
        username = payload.get("username", "devuser")
        ynab_connected = payload.get("ynab_connected", True)
        configured = payload.get("configured", True)
        confirmation_mode = payload.get("confirmation_mode", False)

        user = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user:
            user = UserConfiguration(
                telegram_id=telegram_user_id,
                status=UserStatus.AUTHORIZED,
                username=username,
                first_name=first_name,
            )
        else:
            user.status = UserStatus.AUTHORIZED
            user.update_profile(username=username, first_name=first_name)

        if ynab_connected:
            user.update_ynab_tokens("dev-access-token", "dev-refresh-token", 24 * 3600)
            if hasattr(self.ynab_factory, "bootstrap_user"):
                user = self.ynab_factory.bootstrap_user(user)
        else:
            user.clear_ynab_tokens()
            user.budget_id = None
            user.default_account_id = None
            user.default_account_name = None

        if not configured:
            user.default_account_id = None
            user.default_account_name = None

        user.toggle_confirmation(bool(confirmation_mode))
        saved = self.user_repository.save(user)

        status = self.user_config_service.get_user_status(saved.telegram_id)
        return 200, {
            "status": "ok",
            "telegram_user_id": saved.telegram_id,
            "onboarding_step": self.onboarding_service.get_onboarding_step(saved.telegram_id).value,
            "user_status": status,
        }

    def _handle_message(self, body: bytes) -> tuple[int, dict]:
        payload = parse_text_message_request(body)
        telegram_user_id = payload.telegram_user_id
        text = payload.text
        force_commit = payload.force_commit

        if text.startswith("/"):
            return self._simulate_command(telegram_user_id, text)
        return self._simulate_text_message(telegram_user_id, text, force_commit)

    def _simulate_command(self, telegram_user_id: int, text: str) -> tuple[int, dict]:
        command, _, raw_args = text.partition(" ")
        command = command.lower()
        args = raw_args.strip()

        if command == "/start":
            user = self.auth_service.register_user(
                SimpleNamespace(
                    id=telegram_user_id,
                    username=f"dev{telegram_user_id}",
                    first_name="Dev",
                    last_name=None,
                )
            )
            if not user.is_authorized():
                user.authorize(telegram_user_id)
                self.user_repository.save(user)
            step = self.onboarding_service.get_onboarding_step(telegram_user_id)
            message = self.general_formatter.format_onboarding_welcome(user.get_display_name(), step)
            return 200, {
                "status": "ok",
                "kind": "command",
                "command": "/start",
                "message": message,
                "onboarding_step": step.value,
            }

        if command == "/status":
            status = self.user_config_service.get_user_status(telegram_user_id)
            return 200, {
                "status": "ok",
                "kind": "command",
                "command": "/status",
                "message": self.config_formatter.format_user_status(status),
                "user_status": status,
            }

        if command == "/budgets":
            budgets = self.user_config_service.get_available_budgets(telegram_user_id)
            return 200, {
                "status": "ok",
                "kind": "command",
                "command": "/budgets",
                "message": self.config_formatter.format_budgets_list(budgets),
                "budgets": [{"id": budget.id, "name": budget.name} for budget in budgets],
            }

        if command == "/accounts":
            accounts, error = self.user_config_service.get_user_accounts(telegram_user_id)
            if error:
                return 409, self._error("USER_NOT_CONFIGURED", error)
            return 200, {
                "status": "ok",
                "kind": "command",
                "command": "/accounts",
                "message": self.config_formatter.format_accounts_list(accounts),
                "accounts": [{"id": account.id, "name": account.name} for account in accounts],
            }

        if command == "/resumen":
            period = self.summary_service.parse_period(args)
            user = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user or not user.is_configured():
                raise UserNotConfiguredException(telegram_user_id, "budget configuration")
            summary = self.summary_service.generate_summary(user, period)
            return 200, {
                "status": "ok",
                "kind": "command",
                "command": "/resumen",
                "period": period,
                "message": self.summary_formatter.format_summary(summary),
            }

        return 404, self._error("COMMAND_NOT_SUPPORTED", f"Command {command} is not supported by the local dev harness.")

    def _simulate_text_message(self, telegram_user_id: int, text: str, force_commit: bool) -> tuple[int, dict]:
        user = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user:
            return 404, self._error("USER_NOT_FOUND", "No registered user exists for that telegram_user_id.")

        if user.confirm_before_create and not force_commit:
            try:
                prepared = self.expense_service.prepare_shared_expense(telegram_user_id, text)
            except ExpenseParsingException:
                prepared = self.expense_service.prepare_expense(telegram_user_id, text)

            return 200, {
                "status": "preview",
                "kind": "message",
                "intent": prepared.intent,
                "message": self.expense_formatter.format_preview(prepared.expense_result, user_tz=user.timezone),
            }

        result = self.expense_service.process_message(telegram_user_id, text)
        if result.intent == "query":
            return 200, {
                "status": "ok",
                "kind": "message",
                "intent": "query",
                "message": self.query_formatter.format_response(result.query_result),
            }

        if result.expense_result and result.expense_result.success:
            return 200, {
                "status": "ok",
                "kind": "message",
                "intent": result.intent,
                "message": self.expense_formatter.format_success(result.expense_result, user_tz=user.timezone),
                "transaction_id": result.expense_result.transaction_id,
            }

        return 422, {
            "status": "error",
            "kind": "message",
            "intent": result.intent,
            "message": self.expense_formatter.format_error(result.expense_result),
        }

    @staticmethod
    def _parse_json(body: bytes) -> dict:
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    @staticmethod
    def _error(error_code: str, message: str) -> dict:
        return {
            "status": "error",
            "error_code": error_code,
            "message": message,
        }

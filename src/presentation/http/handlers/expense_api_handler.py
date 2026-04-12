import logging

from application.services.expense_service import ExpenseService
from domain.models.expense import PreparedExpense
from domain.exceptions import ExpenseParsingException, OAuthException, YNABApiException
from presentation.http.auth import HTTPAuthError, validate_bearer_token
from presentation.http.request_models import (
    TextMessageRequestValidationError,
    parse_text_message_request,
)
from presentation.http.serializers import (
    serialize_committed_response,
    serialize_error_response,
    serialize_preview_response,
)

logger = logging.getLogger(__name__)


class HTTPRequestError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class ExpenseAPIHandler:
    def __init__(self, container):
        self.container = container
        self.expense_service = container.get(ExpenseService)
        self.user_config_service = container.get_user_config_service()
        self.config = container.get_config()

    def handle_post(self, headers: dict, body: bytes) -> tuple[int, dict]:
        try:
            validate_bearer_token(headers, self.config.http_api_key)
            payload = self._parse_request(body)
            telegram_user_id = payload.telegram_user_id
            text = payload.text
            force_commit = payload.force_commit

            user = self.user_config_service.user_repository.find_by_telegram_id(telegram_user_id)
            if not user:
                return self._error(404, "USER_NOT_FOUND", "No registered user exists for that telegram_user_id.")

            if not user.has_ynab_token() or not user.is_configured():
                return self._error(
                    409,
                    "USER_NOT_CONFIGURED",
                    "The user does not have a configured budget or default account yet.",
                )

            prepared = self._prepare_expense(telegram_user_id, text)
            requires_confirmation = user.confirm_before_create and not force_commit

            if requires_confirmation:
                return 200, serialize_preview_response(
                    intent=prepared.intent,
                    result=prepared.expense_result,
                    message=self._build_preview_message(prepared.expense),
                )

            result = self._commit_prepared_expense(telegram_user_id, prepared)
            return 200, serialize_committed_response(
                intent=prepared.intent,
                result=result,
                message=self._build_committed_message(result.expense),
            )

        except HTTPAuthError as exc:
            return self._error(401, exc.error_code, exc.message)
        except TextMessageRequestValidationError as exc:
            return self._error(400, exc.error_code, exc.message)
        except HTTPRequestError as exc:
            return self._error(exc.status_code, exc.error_code, exc.message)
        except (YNABApiException, OAuthException):
            return self._error(
                502,
                "UPSTREAM_SERVICE_ERROR",
                "There was a problem connecting to YNAB. Try again in a few seconds.",
            )
        except ExpenseParsingException as exc:
            logger.info("Expense could not be processed for HTTP request: %s", exc)
            return self._error(
                422,
                "EXPENSE_NOT_PROCESSABLE",
                "The expense message could not be processed.",
            )
        except Exception:
            logger.exception("Unexpected error handling POST /api/v1/expenses/text")
            return self._error(500, "INTERNAL_ERROR", "An internal error occurred while processing the request.")

    def _parse_request(self, body: bytes):
        return parse_text_message_request(body)

    def _prepare_expense(self, telegram_user_id: int, text: str) -> PreparedExpense:
        try:
            return self.expense_service.prepare_shared_expense(telegram_user_id, text)
        except ExpenseParsingException:
            pass

        try:
            return self.expense_service.prepare_expense(telegram_user_id, text)
        except ExpenseParsingException:
            result = self.expense_service.process_message(telegram_user_id, text)
            if result.intent == "query":
                raise HTTPRequestError(
                    422,
                    "QUERY_NOT_SUPPORTED",
                    "This endpoint only supports expense logging, not queries.",
                )

            error_message = "The expense message could not be processed."
            if result.expense_result and result.expense_result.error_message:
                logger.info(
                    "Expense service returned a user-facing parsing error for HTTP request: %s",
                    result.expense_result.error_message,
                )
            raise HTTPRequestError(422, "EXPENSE_NOT_PROCESSABLE", error_message)

    def _commit_prepared_expense(self, telegram_user_id: int, prepared: PreparedExpense):
        if prepared.intent == "shared_expense":
            return self.expense_service.commit_shared_expense(telegram_user_id, prepared)

        return self.expense_service.commit_expense(
            telegram_user_id,
            prepared.expense,
            prepared.budget_id,
            prepared.account_id,
        )

    @staticmethod
    def _build_preview_message(expense) -> str:
        return f"I am about to log: {expense.payee} ${expense.amount:,.0f}."

    @staticmethod
    def _build_committed_message(expense) -> str:
        return f"Logged: {expense.payee} ${expense.amount:,.0f}."

    @staticmethod
    def _error(status_code: int, error_code: str, message: str) -> tuple[int, dict]:
        return status_code, serialize_error_response(error_code=error_code, message=message)

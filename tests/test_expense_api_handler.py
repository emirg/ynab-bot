import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from application.services.expense_service import ExpenseService
from domain.exceptions import (
    ExpenseParsingException,
    OAuthException,
    YNABApiException,
)
from domain.models.budget_query import MessageResult
from domain.models.expense import Expense, ExpenseResult
from domain.models.user import UserConfiguration, UserStatus
from presentation.http.handlers.expense_api_handler import ExpenseAPIHandler


def _headers() -> dict:
    return {"Authorization": "Bearer http-key"}


def _body(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _configured_user(confirm_before_create: bool = False) -> UserConfiguration:
    user = UserConfiguration(
        telegram_id=123,
        status=UserStatus.AUTHORIZED,
        budget_id="budget-1",
        default_account_id="acc-1",
        default_account_name="Cuenta principal",
        ynab_access_token="token",
        confirm_before_create=confirm_before_create,
    )
    return user


def _sample_expense() -> Expense:
    return Expense(
        amount=Decimal("25000"),
        payee="Carulla",
        memo="Compra",
        category_name="Mercado",
        account_name="Cuenta principal",
        date=datetime(2026, 4, 11, 8, 0, 0),
    )


def _build_handler(user=None) -> tuple[ExpenseAPIHandler, MagicMock, MagicMock, MagicMock]:
    expense_service = MagicMock(spec=ExpenseService)
    user_config_service = MagicMock()
    user_config_service.user_repository.find_by_telegram_id.return_value = user
    container = MagicMock()
    container.get.return_value = expense_service
    container.get_user_config_service.return_value = user_config_service
    container.get_config.return_value = MagicMock(http_api_key="http-key")
    return ExpenseAPIHandler(container), expense_service, user_config_service, container


class TestExpenseAPIHandlerValidation:
    def test_returns_400_for_invalid_json(self):
        handler, _, _, _ = _build_handler(user=_configured_user())

        status_code, payload = handler.handle_post(_headers(), b"{invalid")

        assert status_code == 400
        assert payload["error_code"] == "INVALID_JSON"
        assert payload["message"] == "Request body does not contain valid JSON."

    def test_returns_400_for_missing_required_fields(self):
        handler, _, _, _ = _build_handler(user=_configured_user())

        status_code, payload = handler.handle_post(_headers(), _body({"text": "almuerzo 25k"}))

        assert status_code == 400
        assert payload["error_code"] == "INVALID_REQUEST"
        assert payload["message"] == "telegram_user_id must be an integer."

    def test_returns_400_for_invalid_field_types(self):
        handler, _, _, _ = _build_handler(user=_configured_user())

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": "123", "text": 5}),
        )

        assert status_code == 400
        assert payload["error_code"] == "INVALID_REQUEST"
        assert payload["message"] == "telegram_user_id must be an integer."

    def test_returns_404_for_unknown_user(self):
        handler, _, _, _ = _build_handler(user=None)

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "almuerzo 25k"}),
        )

        assert status_code == 404
        assert payload["error_code"] == "USER_NOT_FOUND"
        assert payload["message"] == "No registered user exists for that telegram_user_id."

    def test_returns_409_for_unconfigured_user(self):
        handler, _, _, _ = _build_handler(user=UserConfiguration(telegram_id=123, status=UserStatus.AUTHORIZED))

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "almuerzo 25k"}),
        )

        assert status_code == 409
        assert payload["error_code"] == "USER_NOT_CONFIGURED"
        assert payload["message"] == "The user does not have a configured budget or default account yet."


class TestExpenseAPIHandlerBusinessErrors:
    def test_returns_422_for_unparseable_message(self):
        handler, expense_service, _, _ = _build_handler(user=_configured_user())
        expense_service.prepare_shared_expense.side_effect = ExpenseParsingException("almuerzo 25k")
        expense_service.prepare_expense.side_effect = ExpenseParsingException("almuerzo 25k")
        expense_service.process_message.return_value = MessageResult(
            intent="expense",
            expense_result=ExpenseResult.error_result("No pude entender tu mensaje."),
        )

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "almuerzo 25k"}),
        )

        assert status_code == 422
        assert payload["error_code"] == "EXPENSE_NOT_PROCESSABLE"
        assert payload["message"] == "The expense message could not be processed."

    def test_returns_422_for_query_intent(self):
        handler, expense_service, _, _ = _build_handler(user=_configured_user())
        expense_service.prepare_shared_expense.side_effect = ExpenseParsingException("cuanto me queda")
        expense_service.prepare_expense.side_effect = ExpenseParsingException("cuanto me queda")
        expense_service.process_message.return_value = MessageResult(intent="query", query_result=MagicMock())

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "cuanto me queda en mercado"}),
        )

        assert status_code == 422
        assert payload["error_code"] == "QUERY_NOT_SUPPORTED"
        assert payload["message"] == "This endpoint only supports expense logging, not queries."

    def test_returns_502_for_expected_ynab_error(self):
        handler, expense_service, _, _ = _build_handler(user=_configured_user(confirm_before_create=False))
        prepared = {
            "expense": _sample_expense(),
            "budget_id": "budget-1",
            "account_id": "acc-1",
            "expense_result": ExpenseResult.success_result(_sample_expense()),
            "intent": "expense",
        }
        expense_service.prepare_shared_expense.side_effect = ExpenseParsingException("gaste 25k")
        expense_service.prepare_expense.return_value = prepared
        expense_service.commit_expense.side_effect = YNABApiException("timeout")

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "Gaste 25k en Carulla"}),
        )

        assert status_code == 502
        assert payload["error_code"] == "UPSTREAM_SERVICE_ERROR"
        assert payload["message"] == "There was a problem connecting to YNAB. Try again in a few seconds."

    def test_returns_500_for_unexpected_error(self):
        handler, expense_service, _, _ = _build_handler(user=_configured_user(confirm_before_create=False))
        expense_service.prepare_shared_expense.side_effect = RuntimeError("boom")
        expense_service.prepare_expense.side_effect = RuntimeError("boom")

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "Gaste 25k en Carulla"}),
        )

        assert status_code == 500
        assert payload["error_code"] == "INTERNAL_ERROR"
        assert payload["message"] == "An internal error occurred while processing the request."


class TestExpenseAPIHandlerAuth:
    def test_returns_401_for_invalid_token(self):
        handler, _, _, _ = _build_handler(user=_configured_user())

        status_code, payload = handler.handle_post(
            {"Authorization": "Bearer wrong"},
            _body({"telegram_user_id": 123, "text": "Gaste 25k en Carulla"}),
        )

        assert status_code == 401
        assert payload["error_code"] == "INVALID_API_KEY"
        assert payload["message"] == "Invalid authentication token."


class TestExpenseAPIHandlerFlows:
    def test_returns_preview_when_confirmation_enabled(self):
        handler, expense_service, _, _ = _build_handler(user=_configured_user(confirm_before_create=True))
        prepared = {
            "expense": _sample_expense(),
            "budget_id": "budget-1",
            "account_id": "acc-1",
            "expense_result": ExpenseResult.success_result(_sample_expense()),
            "intent": "expense",
        }
        expense_service.prepare_shared_expense.side_effect = ExpenseParsingException("gaste 25k")
        expense_service.prepare_expense.return_value = prepared

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "Gaste 25k en Carulla"}),
        )

        assert status_code == 200
        assert payload["status"] == "preview"
        assert payload["intent"] == "expense"
        assert payload["requires_confirmation"] is True
        assert payload["transaction_id"] is None
        assert payload["message"] == "I am about to log: Carulla $25,000."

    def test_commits_when_confirmation_disabled(self):
        handler, expense_service, _, _ = _build_handler(user=_configured_user(confirm_before_create=False))
        prepared = {
            "expense": _sample_expense(),
            "budget_id": "budget-1",
            "account_id": "acc-1",
            "expense_result": ExpenseResult.success_result(_sample_expense()),
            "intent": "expense",
        }
        committed = ExpenseResult.success_result(_sample_expense(), transaction_id="txn-1")
        expense_service.prepare_shared_expense.side_effect = ExpenseParsingException("gaste 25k")
        expense_service.prepare_expense.return_value = prepared
        expense_service.commit_expense.return_value = committed

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "Gaste 25k en Carulla"}),
        )

        assert status_code == 200
        assert payload["status"] == "committed"
        assert payload["transaction_id"] == "txn-1"
        assert payload["message"] == "Logged: Carulla $25,000."

    def test_force_commit_overrides_confirmation(self):
        handler, expense_service, _, _ = _build_handler(user=_configured_user(confirm_before_create=True))
        prepared = {
            "expense": _sample_expense(),
            "budget_id": "budget-1",
            "account_id": "acc-1",
            "expense_result": ExpenseResult.success_result(_sample_expense()),
            "intent": "expense",
        }
        committed = ExpenseResult.success_result(_sample_expense(), transaction_id="txn-42")
        expense_service.prepare_shared_expense.side_effect = ExpenseParsingException("gaste 25k")
        expense_service.prepare_expense.return_value = prepared
        expense_service.commit_expense.return_value = committed

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "Gaste 25k en Carulla", "force_commit": True}),
        )

        assert status_code == 200
        assert payload["status"] == "committed"
        assert payload["transaction_id"] == "txn-42"
        assert payload["message"] == "Logged: Carulla $25,000."

    def test_commits_shared_expense(self):
        handler, expense_service, _, _ = _build_handler(user=_configured_user(confirm_before_create=False))
        shared_expense = _sample_expense()
        shared_expense.is_split = True
        shared_expense.split_person = "Ana"
        prepared = {
            "expense": shared_expense,
            "budget_id": "budget-1",
            "account_id": "acc-1",
            "expense_result": ExpenseResult.success_result(shared_expense),
            "intent": "shared_expense",
        }
        committed = ExpenseResult.success_result(shared_expense, transaction_id="txn-shared-1")
        expense_service.prepare_shared_expense.return_value = prepared
        expense_service.commit_shared_expense.return_value = committed

        status_code, payload = handler.handle_post(
            _headers(),
            _body({"telegram_user_id": 123, "text": "Gaste 25k en Carulla con Ana"}),
        )

        assert status_code == 200
        assert payload["status"] == "committed"
        assert payload["intent"] == "shared_expense"
        assert payload["transaction_id"] == "txn-shared-1"
        assert payload["message"] == "Logged: Carulla $25,000."

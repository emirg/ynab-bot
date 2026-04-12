import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from application.services.expense_service import ExpenseService
from application.services.on_demand_summary_service import OnDemandSummaryService
from domain.models.expense import Expense, ExpenseResult
from domain.models.user import UserConfiguration, UserStatus
from presentation.http.dev_api_handler import DevAPIHandler
from presentation.http.server import set_dev_endpoint_handler, set_expense_endpoint_handler
from infrastructure.health import route_health_request


def _post(path, payload, auth="dev-api-key"):
    status, response_type, response_payload, _extra_headers = route_health_request(
        method="POST",
        path=path,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth}",
        },
        body=json.dumps(payload).encode("utf-8"),
    )
    assert response_type == "json"
    return status, response_payload


def _make_container():
    config = SimpleNamespace(dev_api_key="dev-api-key")
    user = UserConfiguration(
        telegram_id=42,
        status=UserStatus.AUTHORIZED,
        username="dev42",
        first_name="Dev",
    )
    user.update_ynab_tokens("dev-access-token", "dev-refresh-token", 3600)
    user.budget_id = "budget-dev-main"
    user.default_account_id = "acc-dev-nu"
    user.default_account_name = "Nu Card"

    user_repository = MagicMock()
    user_repository.find_by_telegram_id.return_value = user
    user_repository.save.side_effect = lambda saved_user: saved_user

    user_config_service = MagicMock()
    user_config_service.user_repository = user_repository
    user_config_service.get_user_status.return_value = "configured"

    onboarding_service = MagicMock()
    onboarding_service.get_onboarding_step.return_value = SimpleNamespace(value="complete")

    auth_service = MagicMock()
    auth_service.register_user.return_value = user

    expense_service = MagicMock(spec=ExpenseService)
    expense = Expense(
        amount=25000,
        payee="Carulla",
        memo="Gaste 25k en Carulla",
        category_name="Groceries",
        account_name="Nu Card",
        confidence=0.92,
        category_explanation="sugerido por IA",
    )
    expense_result = ExpenseResult(
        success=True,
        transaction_id="txn-123",
        expense=expense,
    )
    expense_service.process_message.return_value = SimpleNamespace(
        intent="expense",
        expense_result=expense_result,
    )

    summary_service = MagicMock(spec=OnDemandSummaryService)
    ynab_factory = MagicMock()

    service_map = {
        ExpenseService: expense_service,
        OnDemandSummaryService: summary_service,
    }

    container = MagicMock()
    container.get_config.return_value = config
    container.get_auth_service.return_value = auth_service
    container.get_user_repository.return_value = user_repository
    container.get_user_config_service.return_value = user_config_service
    container.get_onboarding_service.return_value = onboarding_service
    container.get_ynab_factory.return_value = ynab_factory
    container.get.side_effect = lambda service_type: service_map[service_type]
    return container


class TestDevAPIHandler:
    def setup_method(self):
        set_expense_endpoint_handler(None)
        set_dev_endpoint_handler(None)

    def teardown_method(self):
        set_expense_endpoint_handler(None)
        set_dev_endpoint_handler(None)

    def test_bootstrap_and_simulate_text_message(self):
        container = _make_container()
        set_dev_endpoint_handler(DevAPIHandler(container))

        status, payload = _post("/dev/bootstrap", {"telegram_user_id": 42})
        assert status == 200
        assert payload["status"] == "ok"
        assert payload["onboarding_step"] == "complete"

        status, payload = _post("/dev/messages/text", {"telegram_user_id": 42, "text": "Gaste 25k en Carulla"})
        assert status == 200
        assert payload["kind"] == "message"
        assert "Gasto registrado" in payload["message"]

    def test_simulate_start_command(self):
        container = _make_container()
        set_dev_endpoint_handler(DevAPIHandler(container))

        status, payload = _post("/dev/messages/text", {"telegram_user_id": 7, "text": "/start"})
        assert status == 200
        assert payload["kind"] == "command"
        assert payload["command"] == "/start"

    def test_invalid_dev_token_is_rejected(self):
        container = _make_container()
        set_dev_endpoint_handler(DevAPIHandler(container))

        status, payload = _post("/dev/bootstrap", {"telegram_user_id": 1}, auth="wrong")
        assert status == 401
        assert payload["error_code"] == "INVALID_API_KEY"

    def test_invalid_force_commit_type_is_rejected(self):
        container = _make_container()
        set_dev_endpoint_handler(DevAPIHandler(container))

        status, payload = _post(
            "/dev/messages/text",
            {"telegram_user_id": 42, "text": "Gaste 25k en Carulla", "force_commit": "false"},
        )
        assert status == 400
        assert payload["error_code"] == "INVALID_REQUEST"
        assert payload["message"] == "force_commit must be a boolean."

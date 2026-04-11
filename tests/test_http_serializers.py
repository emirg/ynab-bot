from datetime import datetime
from decimal import Decimal

from domain.models.expense import Expense, ExpenseResult
from presentation.http.serializers import (
    serialize_committed_response,
    serialize_error_response,
    serialize_preview_response,
)


def _sample_expense() -> Expense:
    return Expense(
        amount=Decimal("25000"),
        payee="Carulla",
        memo="Compra",
        category_id="cat-1",
        category_name="Mercado",
        account_id="acc-1",
        account_name="Cuenta principal",
        confidence=0.92,
        category_explanation="aprendido",
        date=datetime(2026, 4, 11, 9, 30, 0),
    )


class TestSerializePreviewResponse:
    def test_serializes_preview_payload(self):
        result = ExpenseResult.success_result(_sample_expense(), transaction_id=None)

        payload = serialize_preview_response(
            intent="expense",
            result=result,
            message="Voy a registrar: Carulla $25.000 en Mercado.",
        )

        assert payload == {
            "status": "preview",
            "intent": "expense",
            "message": "Voy a registrar: Carulla $25.000 en Mercado.",
            "requires_confirmation": True,
            "transaction_id": None,
            "expense": {
                "payee": "Carulla",
                "amount": "25000",
                "category_name": "Mercado",
                "account_name": "Cuenta principal",
                "date": "2026-04-11",
                "memo": "Compra",
                "is_split": False,
                "split_person": None,
                "split_proportion": "0.5",
                "split_fixed_amount": None,
                "split_category_name": None,
                "payer": "user",
            },
        }


class TestSerializeCommittedResponse:
    def test_serializes_committed_payload(self):
        expense = _sample_expense()
        expense.is_split = True
        expense.split_person = "Ana"
        expense.split_category_name = "Gastos Compartidos"
        expense.payer = "other"
        result = ExpenseResult.success_result(expense, transaction_id="ynab-tx-123")

        payload = serialize_committed_response(
            intent="shared_expense",
            result=result,
            message="Registrado: Carulla $25.000.",
        )

        assert payload["status"] == "committed"
        assert payload["intent"] == "shared_expense"
        assert payload["message"] == "Registrado: Carulla $25.000."
        assert payload["requires_confirmation"] is False
        assert payload["transaction_id"] == "ynab-tx-123"
        assert payload["expense"]["amount"] == "25000"
        assert payload["expense"]["date"] == "2026-04-11"
        assert payload["expense"]["is_split"] is True
        assert payload["expense"]["split_person"] == "Ana"
        assert payload["expense"]["split_category_name"] == "Gastos Compartidos"
        assert payload["expense"]["payer"] == "other"


class TestSerializeErrorResponse:
    def test_serializes_error_payload(self):
        payload = serialize_error_response(
            error_code="USER_NOT_CONFIGURED",
            message="Tu cuenta aún no tiene presupuesto o cuenta por defecto configurados.",
        )

        assert payload == {
            "status": "error",
            "error_code": "USER_NOT_CONFIGURED",
            "message": "Tu cuenta aún no tiene presupuesto o cuenta por defecto configurados.",
        }

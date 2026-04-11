from decimal import Decimal

from domain.models.expense import Expense, ExpenseResult


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None

    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def serialize_expense(expense: Expense) -> dict:
    return {
        "payee": expense.payee,
        "amount": _decimal_to_string(expense.amount),
        "category_name": expense.category_name,
        "account_name": expense.account_name,
        "date": expense.date.strftime("%Y-%m-%d") if expense.date else None,
        "memo": expense.memo,
        "is_split": expense.is_split,
        "split_person": expense.split_person,
        "split_proportion": _decimal_to_string(expense.split_proportion),
        "split_fixed_amount": _decimal_to_string(expense.split_fixed_amount),
        "split_category_name": expense.split_category_name,
        "payer": expense.payer,
    }


def serialize_preview_response(intent: str, result: ExpenseResult, message: str) -> dict:
    return {
        "status": "preview",
        "intent": intent,
        "message": message,
        "requires_confirmation": True,
        "transaction_id": result.transaction_id,
        "expense": serialize_expense(result.expense) if result.expense else None,
    }


def serialize_committed_response(intent: str, result: ExpenseResult, message: str) -> dict:
    return {
        "status": "committed",
        "intent": intent,
        "message": message,
        "requires_confirmation": False,
        "transaction_id": result.transaction_id,
        "expense": serialize_expense(result.expense) if result.expense else None,
    }


def serialize_error_response(error_code: str, message: str) -> dict:
    return {
        "status": "error",
        "error_code": error_code,
        "message": message,
    }

import logging
import re
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from domain.models.expense import Expense
from domain.models.user import YNABAccount, YNABBudget, YNABCategory, YNABPayee
from domain.repositories.ynab_repository import YNABRepository

logger = logging.getLogger(__name__)

_AMOUNT_PATTERN = re.compile(r'(\d+(?:[.,]\d+)?)\s*(k|mil|lucas)?', re.IGNORECASE)


def _stub_budgets():
    return [
        YNABBudget(id="budget-dev-main", name="Dev Budget", currency_format={"iso_code": "COP"}),
    ]


def _stub_accounts():
    return [
        YNABAccount(id="acc-dev-nu", name="Nu Card", type="creditCard", balance=95000000),
        YNABAccount(id="acc-dev-banco", name="Bancolombia", type="checking", balance=210000000),
        YNABAccount(id="acc-dev-cash", name="Efectivo", type="cash", balance=5000000),
    ]


def _stub_categories():
    return [
        YNABCategory(id="cat-dev-groceries", name="Groceries", group_name="Essentials", full_name="Essentials → Groceries", budgeted=700000000, activity=-120000000),
        YNABCategory(id="cat-dev-restaurants", name="Restaurants", group_name="Lifestyle", full_name="Lifestyle → Restaurants", budgeted=450000000, activity=-95000000),
        YNABCategory(id="cat-dev-transport", name="Transport", group_name="Essentials", full_name="Essentials → Transport", budgeted=300000000, activity=-40000000),
        YNABCategory(id="cat-dev-shopping", name="Shopping", group_name="Lifestyle", full_name="Lifestyle → Shopping", budgeted=250000000, activity=-35000000),
        YNABCategory(id="cat-dev-services", name="Services", group_name="Bills", full_name="Bills → Services", budgeted=600000000, activity=-180000000),
    ]


def _stub_payees():
    return [
        YNABPayee(id="payee-dev-carulla", name="Carulla"),
        YNABPayee(id="payee-dev-exito", name="Exito"),
        YNABPayee(id="payee-dev-uber", name="Uber"),
        YNABPayee(id="payee-dev-netflix", name="Netflix"),
    ]


class StubLLMExpenseParser:
    """Deterministic parser for local development."""

    def __init__(self):
        self.ynab_categories = []
        self.ynab_accounts = []

    def update_categories(self, categories: list):
        self.ynab_categories = categories or []

    def update_accounts(self, accounts: list):
        self.ynab_accounts = accounts or []

    def parse_message(self, message: str, timezone_str=None, learning_hints=None):
        message = (message or "").strip()
        lowered = message.lower()
        if not message:
            return None

        if any(word in lowered for word in ("saldo", "presupuesto", "cuánto me queda", "cuanto me queda", "balance")):
            query_target = "budget"
            query_type = "budget_summary"
            if "cuenta" in lowered:
                query_type = "account_balance"
                query_target = self._pick_account_name(lowered)
            elif "categor" in lowered or "mercado" in lowered or "comida" in lowered:
                query_type = "category_balance"
                query_target = self._pick_category_name(lowered)
            return {
                "intent": "query",
                "query_type": query_type,
                "query_target": query_target,
            }

        return self.parse_expense(message, timezone_str=timezone_str, learning_hints=learning_hints) | {"intent": "expense"}

    def parse_expense(self, message: str, timezone_str=None, learning_hints=None):
        amount = self._extract_amount(message)
        payee = self._extract_payee(message)
        category = self._pick_category_name(message.lower())
        account = self._pick_account_name(message.lower())

        return {
            "amount": float(amount),
            "category": category,
            "payee": payee,
            "account": account,
            "memo": message,
            "date": None,
            "confidence": 0.92,
        }

    def parse_receipt_image(self, image_bytes, mime_type=None, timezone_str=None, learning_hints=None):
        return self.parse_expense("Recibo 25000 en Carulla", timezone_str=timezone_str, learning_hints=learning_hints)

    @staticmethod
    def _extract_amount(message: str) -> Decimal:
        match = _AMOUNT_PATTERN.search(message.lower())
        if not match:
            return Decimal("25000")
        raw_value, multiplier = match.groups()
        normalized = raw_value.replace(".", "").replace(",", ".")
        value = Decimal(normalized)
        if multiplier and multiplier.lower() in {"k", "mil", "lucas"}:
            value *= Decimal("1000")
        return value

    def _pick_category_name(self, lowered: str) -> str:
        keyword_map = {
            "uber": "Transport",
            "taxi": "Transport",
            "bus": "Transport",
            "mercado": "Groceries",
            "carulla": "Groceries",
            "exito": "Groceries",
            "almuerzo": "Restaurants",
            "cena": "Restaurants",
            "restaurante": "Restaurants",
            "ropa": "Shopping",
            "amazon": "Shopping",
            "mercadolibre": "Shopping",
            "netflix": "Services",
            "internet": "Services",
        }
        for keyword, category_name in keyword_map.items():
            if keyword in lowered:
                return category_name
        if not self.ynab_categories:
            return "Groceries"
        first = self.ynab_categories[0]
        return first["name"] if isinstance(first, dict) else first.name

    def _pick_account_name(self, lowered: str):
        for account in self.ynab_accounts:
            account_name = account if isinstance(account, str) else account.name
            if account_name.lower() in lowered:
                return account_name
        return None

    @staticmethod
    def _extract_payee(message: str) -> str:
        lowered = message.lower()
        for marker in (" en ", " a ", " con "):
            if marker in lowered:
                suffix = message[lowered.index(marker) + len(marker):].strip()
                if suffix:
                    return suffix.split(" con ")[0].split(" usando ")[0].strip().title()
        return "Comercio Dev"


class StubYNABOAuthService:
    """Minimal OAuth substitute for local development."""

    def __init__(self, config, user_repository):
        self.config = config
        self.user_repository = user_repository

    def generate_auth_url(self, telegram_user_id: int) -> str:
        return f"http://localhost:8080/dev/bootstrap?telegram_user_id={telegram_user_id}"

    def exchange_code_for_tokens(self, code: str, state: str):
        user = self.user_repository.find_by_telegram_id(int(state))
        if not user:
            raise ValueError("Usuario no encontrado para OAuth de desarrollo")
        user.update_ynab_tokens("dev-access-token", "dev-refresh-token", 3600)
        return self.user_repository.save(user)

    def get_valid_access_token(self, user_config):
        if not user_config.has_ynab_token():
            user_config.update_ynab_tokens("dev-access-token", "dev-refresh-token", 3600)
        return user_config.ynab_access_token

    def disconnect_user(self, telegram_user_id: int) -> bool:
        user = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user:
            return False
        user.clear_ynab_tokens()
        self.user_repository.save(user)
        return True


class StubYNABRepository(YNABRepository):
    def __init__(self, store: dict):
        self._store = store

    def get_budgets(self):
        return list(self._store["budgets"])

    def get_accounts(self, budget_id: str):
        return list(self._store["accounts"])

    def get_categories(self, budget_id: str):
        return list(self._store["categories"])

    def get_payees(self, budget_id: str):
        return list(self._store["payees"])

    def create_transaction(self, expense: Expense, budget_id: str, account_id: str):
        transaction_id = f"dev-txn-{uuid4().hex[:10]}"
        self._store["transactions"][transaction_id] = {
            "id": transaction_id,
            "date": expense.date.date().isoformat() if expense.date else datetime.now().date().isoformat(),
            "amount": int(expense.amount * Decimal("1000")) * -1,
            "payee_name": expense.payee,
            "category_name": expense.category_name or "Sin categoría",
            "category_id": expense.category_id,
            "account_id": account_id,
            "memo": expense.memo,
            "deleted": False,
        }
        return transaction_id

    def update_transaction_category(self, budget_id: str, transaction_id: str, category_id: str):
        txn = self._store["transactions"].get(transaction_id)
        if not txn:
            return False
        txn["category_id"] = category_id
        category = next((cat for cat in self._store["categories"] if cat.id == category_id), None)
        txn["category_name"] = category.name if category else txn["category_name"]
        return True

    def get_transactions(self, budget_id: str, since_date: str):
        return [
            txn for txn in self._store["transactions"].values()
            if txn["date"] >= since_date and not txn.get("deleted", False)
        ]

    def delete_transaction(self, budget_id: str, transaction_id: str):
        txn = self._store["transactions"].get(transaction_id)
        if not txn:
            return False
        txn["deleted"] = True
        return True

    def update_transaction(self, budget_id: str, transaction_id: str, fields: dict):
        txn = self._store["transactions"].get(transaction_id)
        if not txn:
            return False
        txn.update(fields)
        return True


class StubYNABRepositoryFactory:
    """Shared in-memory YNAB substitute for local development."""

    def __init__(self):
        self._store = {
            "budgets": _stub_budgets(),
            "accounts": _stub_accounts(),
            "categories": _stub_categories(),
            "payees": _stub_payees(),
            "transactions": {},
        }

    def get_repository(self, user_config):
        if not user_config.has_ynab_token():
            raise ValueError("Usuario de desarrollo sin conexión YNAB simulada")
        return StubYNABRepository(self._store)

    def bootstrap_user(self, user_config):
        if not user_config.has_ynab_token():
            user_config.update_ynab_tokens("dev-access-token", "dev-refresh-token", 24 * 3600)
        if not user_config.budget_id:
            user_config.update_budget(self._store["budgets"][0].id)
        if not user_config.default_account_id:
            account = self._store["accounts"][0]
            user_config.update_default_account(account.id, account.name)
        return user_config

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from domain.repositories.ynab_repository import YNABRepository
from domain.models.expense import Expense
from domain.models.user import UserConfiguration, YNABBudget, YNABAccount, YNABCategory, YNABPayee
from domain.exceptions import YNABApiException, OAuthException
from infrastructure.http_client import ResilientHTTPClient

if TYPE_CHECKING:
    from application.services.oauth_service import YNABOAuthService

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300  # 5 minutes


class YNABApiRepository(YNABRepository):
    """YNAB API implementation of YNABRepository"""

    def __init__(self, client: ResilientHTTPClient):
        self.client = client
        # TTL cache: key -> (timestamp, data)
        self._cache: Dict[str, Tuple[float, object]] = {}

    def _get_cached(self, key: str) -> Optional[object]:
        """Return cached value if still valid, else None"""
        entry = self._cache.get(key)
        if entry and (time.monotonic() - entry[0]) < _CACHE_TTL_SECONDS:
            return entry[1]
        return None

    def _set_cached(self, key: str, value: object) -> None:
        self._cache[key] = (time.monotonic(), value)

    def get_budgets(self) -> List[YNABBudget]:
        """Get all available budgets"""
        try:
            response = self.client.get("/budgets")
            response.raise_for_status()

            budgets_data = response.json()["data"]["budgets"]
            return [YNABBudget.from_api_response(budget) for budget in budgets_data]

        except YNABApiException:
            raise
        except Exception as e:
            logger.error(f"Failed to get budgets: {e}", extra={"operation": "get_budgets"})
            raise YNABApiException(f"Failed to get budgets: {e}")

    def get_accounts(self, budget_id: str) -> List[YNABAccount]:
        """Get all accounts for a budget (cached with TTL)"""
        cache_key = f"accounts:{budget_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            response = self.client.get(f"/budgets/{budget_id}/accounts")
            response.raise_for_status()

            accounts_data = response.json()["data"]["accounts"]
            result = [
                YNABAccount.from_api_response(account)
                for account in accounts_data
                if not account.get('deleted', False) and not account.get('closed', False)
            ]

            self._set_cached(cache_key, result)
            return result

        except YNABApiException:
            raise
        except Exception as e:
            logger.error(f"Failed to get accounts for budget {budget_id}: {e}", extra={"operation": "get_accounts"})
            raise YNABApiException(f"Failed to get accounts: {e}")

    def get_categories(self, budget_id: str) -> List[YNABCategory]:
        """Get all categories for a budget (cached with TTL)"""
        cache_key = f"categories:{budget_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            response = self.client.get(f"/budgets/{budget_id}/categories")
            response.raise_for_status()

            categories = []
            for group in response.json()["data"]["category_groups"]:
                group_name = group["name"]
                for category in group["categories"]:
                    if not category.get("deleted", False):
                        categories.append(
                            YNABCategory.from_api_response(category, group_name)
                        )

            self._set_cached(cache_key, categories)
            return categories

        except YNABApiException:
            raise
        except Exception as e:
            logger.error(f"Failed to get categories for budget {budget_id}: {e}", extra={"operation": "get_categories"})
            raise YNABApiException(f"Failed to get categories: {e}")

    def get_payees(self, budget_id: str) -> List[YNABPayee]:
        """Get all payees for a budget (cached with TTL)"""
        cache_key = f"payees:{budget_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            response = self.client.get(f"/budgets/{budget_id}/payees")
            response.raise_for_status()

            payees_data = response.json()["data"]["payees"]
            result = [
                YNABPayee.from_api_response(payee)
                for payee in payees_data
                if not payee.get('deleted', False)
            ]

            self._set_cached(cache_key, result)
            return result

        except YNABApiException:
            raise
        except Exception as e:
            logger.error(f"Failed to get payees for budget {budget_id}: {e}", extra={"operation": "get_payees"})
            raise YNABApiException(f"Failed to get payees: {e}")

    def create_transaction(self, expense: Expense, budget_id: str, account_id: str) -> Optional[str]:
        """Create transaction and return transaction ID if successful"""
        try:
            if not expense.is_valid():
                raise YNABApiException("Invalid expense data")

            transaction_data = expense.to_ynab_format(budget_id, account_id)

            response = self.client.post(
                f"/budgets/{budget_id}/transactions",
                json=transaction_data,
            )

            if response.status_code in [200, 201]:
                result = response.json()
                transaction_id = result["data"]["transaction"]["id"]
                logger.info(f"Transaction created successfully: {transaction_id}", extra={"operation": "create_transaction"})
                return transaction_id
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Failed to create transaction: {error_msg}", extra={"operation": "create_transaction"})
                raise YNABApiException(error_msg, response.status_code, response.text)

        except YNABApiException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating transaction: {e}", extra={"operation": "create_transaction"})
            raise YNABApiException(f"Unexpected error: {e}")

    def get_transactions(self, budget_id: str, since_date: str) -> List[dict]:
        """Get transactions since a given date. Returns raw dicts, deleted transactions excluded."""
        try:
            response = self.client.get(
                f"/budgets/{budget_id}/transactions",
                params={"since_date": since_date},
            )
            response.raise_for_status()

            transactions = response.json()["data"]["transactions"]
            return [txn for txn in transactions if not txn.get("deleted", False)]

        except YNABApiException:
            raise
        except Exception as e:
            logger.error(f"Failed to get transactions for budget {budget_id}: {e}", extra={"operation": "get_transactions"})
            raise YNABApiException(f"Failed to get transactions: {e}")

    def delete_transaction(self, budget_id: str, transaction_id: str) -> bool:
        """Delete a transaction. Returns True if deletion succeeded."""
        try:
            response = self.client.delete(
                f"/budgets/{budget_id}/transactions/{transaction_id}"
            )

            if response.status_code in [200, 201]:
                logger.info(
                    f"Transaction {transaction_id} deleted successfully",
                    extra={"operation": "delete_transaction"},
                )
                return True
            else:
                logger.error(
                    f"Failed to delete transaction: HTTP {response.status_code}: {response.text}",
                    extra={"operation": "delete_transaction"},
                )
                return False

        except YNABApiException:
            logger.error(
                f"Failed to delete transaction: YNAB API error",
                extra={"operation": "delete_transaction"},
            )
            return False
        except Exception as e:
            logger.error(
                f"Failed to delete transaction: {e}",
                extra={"operation": "delete_transaction"},
            )
            return False

    def update_transaction(self, budget_id: str, transaction_id: str, fields: dict) -> bool:
        """Update fields of an existing transaction. Returns True on success."""
        try:
            response = self.client.put(
                f"/budgets/{budget_id}/transactions/{transaction_id}",
                json={"transaction": fields},
            )

            if response.status_code in [200, 201]:
                logger.info(
                    f"Transaction {transaction_id} updated successfully",
                    extra={"operation": "update_transaction"},
                )
                return True
            else:
                logger.error(
                    f"Failed to update transaction: HTTP {response.status_code}: {response.text}",
                    extra={"operation": "update_transaction"},
                )
                return False

        except YNABApiException:
            logger.error(
                "Failed to update transaction: YNAB API error",
                extra={"operation": "update_transaction"},
            )
            return False
        except Exception as e:
            logger.error(
                f"Failed to update transaction: {e}",
                extra={"operation": "update_transaction"},
            )
            return False

    def update_transaction_category(self, budget_id: str, transaction_id: str, category_id: str) -> bool:
        """Update the category of an existing transaction. Returns True on success."""
        try:
            response = self.client.put(
                f"/budgets/{budget_id}/transactions/{transaction_id}",
                json={"transaction": {"category_id": category_id}},
            )

            if response.status_code in [200, 201]:
                logger.info(f"Transaction {transaction_id} category updated to {category_id}", extra={"operation": "update_transaction_category"})
                return True
            else:
                logger.error(
                    f"Failed to update transaction category: HTTP {response.status_code}: {response.text}",
                    extra={"operation": "update_transaction_category"},
                )
                return False

        except YNABApiException:
            logger.error(f"Failed to update transaction category: YNAB API error", extra={"operation": "update_transaction_category"})
            return False
        except Exception as e:
            logger.error(f"Failed to update transaction category: {e}", extra={"operation": "update_transaction_category"})
            return False


class YNABRepositoryFactory:
    """Creates per-user YNABApiRepository instances using OAuth tokens."""

    def __init__(self, oauth_service: YNABOAuthService):
        self.oauth_service = oauth_service

    def get_repository(self, user_config: UserConfiguration) -> YNABApiRepository:
        if not user_config.has_ynab_token():
            raise OAuthException(
                "No tienes una cuenta YNAB conectada. Usa /connect para vincular tu cuenta."
            )
        token = self.oauth_service.get_valid_access_token(user_config)
        client = ResilientHTTPClient(
            base_url="https://api.ynab.com/v1",
            default_headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        return YNABApiRepository(client)

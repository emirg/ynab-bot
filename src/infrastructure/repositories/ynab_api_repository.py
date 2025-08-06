import requests
import logging
from typing import List, Optional
from domain.repositories.ynab_repository import YNABRepository
from domain.models.expense import Expense
from domain.models.user import YNABBudget, YNABAccount, YNABCategory
from domain.exceptions import YNABApiException

logger = logging.getLogger(__name__)


class YNABApiRepository(YNABRepository):
    """YNAB API implementation of YNABRepository"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.ynab.com/v1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_budgets(self) -> List[YNABBudget]:
        """Get all available budgets"""
        try:
            response = requests.get(f"{self.base_url}/budgets", headers=self.headers)
            response.raise_for_status()
            
            budgets_data = response.json()["data"]["budgets"]
            return [YNABBudget.from_api_response(budget) for budget in budgets_data]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get budgets: {e}")
            raise YNABApiException(f"Failed to get budgets: {e}")
    
    def get_accounts(self, budget_id: str) -> List[YNABAccount]:
        """Get all accounts for a budget"""
        try:
            response = requests.get(
                f"{self.base_url}/budgets/{budget_id}/accounts", 
                headers=self.headers
            )
            response.raise_for_status()
            
            accounts_data = response.json()["data"]["accounts"]
            return [
                YNABAccount.from_api_response(account) 
                for account in accounts_data 
                if not account.get('deleted', False) and not account.get('closed', False)
            ]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get accounts for budget {budget_id}: {e}")
            raise YNABApiException(f"Failed to get accounts: {e}")
    
    def get_categories(self, budget_id: str) -> List[YNABCategory]:
        """Get all categories for a budget"""
        try:
            response = requests.get(
                f"{self.base_url}/budgets/{budget_id}/categories", 
                headers=self.headers
            )
            response.raise_for_status()
            
            categories = []
            for group in response.json()["data"]["category_groups"]:
                group_name = group["name"]
                for category in group["categories"]:
                    if not category.get("deleted", False):
                        categories.append(
                            YNABCategory.from_api_response(category, group_name)
                        )
            
            return categories
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get categories for budget {budget_id}: {e}")
            raise YNABApiException(f"Failed to get categories: {e}")
    
    def create_transaction(self, expense: Expense, budget_id: str, account_id: str) -> Optional[str]:
        """Create transaction and return transaction ID if successful"""
        try:
            if not expense.is_valid():
                raise YNABApiException("Invalid expense data")
            
            transaction_data = expense.to_ynab_format(budget_id, account_id)
            
            response = requests.post(
                f"{self.base_url}/budgets/{budget_id}/transactions",
                headers=self.headers,
                json=transaction_data
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                transaction_id = result["data"]["transaction"]["id"]
                logger.info(f"Transaction created successfully: {transaction_id}")
                return transaction_id
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Failed to create transaction: {error_msg}")
                raise YNABApiException(error_msg, response.status_code, response.text)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create transaction: {e}")
            raise YNABApiException(f"Failed to create transaction: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating transaction: {e}")
            raise YNABApiException(f"Unexpected error: {e}")
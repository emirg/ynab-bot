import logging
from typing import List, Optional, Dict

from domain.models.split_config import SplitGroup, SharedAccountConfig
from domain.models.user import YNABCategory, YNABAccount
from domain.repositories.split_config_repository import SplitConfigRepository
from domain.repositories.user_repository import UserRepository
from domain.exceptions import YNABApiException
from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory

logger = logging.getLogger(__name__)


class SplitConfigService:
    """Service for managing split-wise transaction configuration"""

    def __init__(
        self, 
        split_config_repository: SplitConfigRepository, 
        user_repository: UserRepository, 
        ynab_factory: YNABRepositoryFactory
    ):
        self.repo = split_config_repository
        self.user_repository = user_repository
        self.ynab_factory = ynab_factory

    def _get_ynab_repo(self, telegram_id: int):
        """Internal helper to get YNAB repository for a user"""
        user_config = self.user_repository.find_by_telegram_id(telegram_id)
        if not user_config:
            raise YNABApiException("Usuario no encontrado")
        if not user_config.has_ynab_token():
            raise YNABApiException("YNAB no está conectado")
        if not user_config.budget_id:
            raise YNABApiException("Presupuesto no configurado")
            
        return self.ynab_factory.get_repository(user_config), user_config

    def get_split_config_summary(self, telegram_id: int) -> dict:
        """Returns a summary of the split configuration for display"""
        groups = self.repo.get_split_groups(telegram_id)
        shared_account = self.repo.get_shared_account(telegram_id)
        
        return {
            "groups": groups,
            "shared_account": shared_account,
            "configured": len(groups) > 0
        }

    def add_split_group(self, telegram_id: int, category_id: str) -> SplitGroup:
        """Validates category exists in YNAB and adds it as a split group"""
        ynab_repo, user_config = self._get_ynab_repo(telegram_id)
        
        # Fetch categories to validate and get name
        categories = ynab_repo.get_categories(user_config.budget_id)
        category = next((c for c in categories if c.id == category_id), None)
        
        if not category:
            raise YNABApiException(f"Categoría {category_id} no encontrada en YNAB")
            
        return self.repo.add_split_group(telegram_id, category_id, category.name)

    def remove_split_group(self, telegram_id: int, category_id: str) -> bool:
        """Removes a split group"""
        return self.repo.remove_split_group(telegram_id, category_id)

    def add_person_alias(self, telegram_id: int, category_id: str, alias: str) -> bool:
        """Adds a person alias to a split group"""
        alias_clean = alias.strip()
        if not alias_clean:
            return False
        return self.repo.add_person_alias(telegram_id, category_id, alias_clean)

    def remove_person_alias(self, telegram_id: int, category_id: str, alias: str) -> bool:
        """Removes a person alias from a split group"""
        return self.repo.remove_person_alias(telegram_id, category_id, alias)

    def set_shared_account(self, telegram_id: int, account_id: str) -> SharedAccountConfig:
        """Validates account exists in YNAB and sets it as shared account"""
        ynab_repo, user_config = self._get_ynab_repo(telegram_id)
        
        # Fetch accounts to validate and get name
        accounts = ynab_repo.get_accounts(user_config.budget_id)
        account = next((a for a in accounts if a.id == account_id), None)
        
        if not account:
            raise YNABApiException(f"Cuenta {account_id} no encontrada en YNAB")
            
        return self.repo.set_shared_account(telegram_id, account_id, account.name)

    def remove_shared_account(self, telegram_id: int) -> bool:
        """Removes the shared account configuration"""
        return self.repo.remove_shared_account(telegram_id)

    def get_available_categories_for_split(self, telegram_id: int) -> List[YNABCategory]:
        """Returns active, non-hidden YNAB categories"""
        try:
            ynab_repo, user_config = self._get_ynab_repo(telegram_id)
            categories = ynab_repo.get_categories(user_config.budget_id)
            # Filter: not internal (like "Internal Master Category"), not hidden, not deleted
            return [c for c in categories if not c.hidden and not getattr(c, 'deleted', False)]
        except Exception as e:
            logger.error(f"Failed to get categories for split: {e}")
            raise YNABApiException(f"No se pudieron obtener las categorías: {e}")

    def get_available_accounts_for_split(self, telegram_id: int) -> List[YNABAccount]:
        """Returns active, non-closed YNAB accounts"""
        try:
            ynab_repo, user_config = self._get_ynab_repo(telegram_id)
            accounts = ynab_repo.get_accounts(user_config.budget_id)
            # Filter: not closed, not deleted
            return [a for a in accounts if not a.closed and not getattr(a, 'deleted', False)]
        except Exception as e:
            logger.error(f"Failed to get accounts for split: {e}")
            raise YNABApiException(f"No se pudieron obtener las cuentas: {e}")

    def is_split_configured(self, telegram_id: int) -> bool:
        """Returns True if at least one split group exists"""
        groups = self.repo.get_split_groups(telegram_id)
        return len(groups) > 0

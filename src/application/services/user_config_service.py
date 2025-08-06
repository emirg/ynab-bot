import logging
from typing import List, Optional, Tuple

from domain.models.user import UserConfiguration, YNABBudget, YNABAccount
from domain.repositories.user_repository import UserRepository
from domain.repositories.ynab_repository import YNABRepository
from domain.exceptions import YNABApiException

logger = logging.getLogger(__name__)


class UserConfigService:
    """Service for managing user configuration"""
    
    def __init__(self, user_repository: UserRepository, ynab_repository: YNABRepository):
        self.user_repository = user_repository
        self.ynab_repository = ynab_repository
    
    def get_or_create_user_config(self, telegram_user_id: int) -> UserConfiguration:
        """Get existing user configuration or create new one"""
        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        
        if not user_config:
            user_config = UserConfiguration(telegram_id=telegram_user_id)
            user_config = self.user_repository.save_by_telegram_id(user_config)
            logger.info(f"Created new user configuration for {telegram_user_id}")
        
        return user_config
    
    def get_available_budgets(self) -> List[YNABBudget]:
        """Get all available YNAB budgets"""
        try:
            budgets = self.ynab_repository.get_budgets()
            logger.info(f"Retrieved {len(budgets)} available budgets")
            return budgets
        except Exception as e:
            logger.error(f"Failed to get budgets: {e}")
            raise YNABApiException(f"No se pudieron obtener los presupuestos: {e}")
    
    def set_user_budget(self, telegram_user_id: int, budget_id: str) -> UserConfiguration:
        """Set user's budget configuration"""
        try:
            # Verify budget exists
            budgets = self.ynab_repository.get_budgets()
            budget = next((b for b in budgets if b.id == budget_id), None)
            
            if not budget:
                raise YNABApiException(f"Presupuesto {budget_id} no encontrado")
            
            # Get or create user config
            user_config = self.get_or_create_user_config(telegram_user_id)
            
            # Update budget
            user_config.update_budget(budget_id)
            
            # Save changes
            user_config = self.user_repository.save_by_telegram_id(user_config)
            
            logger.info(f"Set budget {budget_id} for user {telegram_user_id}")
            return user_config
            
        except Exception as e:
            logger.error(f"Failed to set user budget: {e}")
            raise YNABApiException(f"Error configurando presupuesto: {e}")
    
    def get_user_accounts(self, telegram_user_id: int) -> Tuple[List[YNABAccount], Optional[str]]:
        """Get accounts for user's configured budget"""
        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        
        if not user_config or not user_config.budget_id:
            return [], "Usuario no tiene presupuesto configurado"
        
        try:
            accounts = self.ynab_repository.get_accounts(user_config.budget_id)
            logger.info(f"Retrieved {len(accounts)} accounts for user {telegram_user_id}")
            return accounts, None
        except Exception as e:
            logger.error(f"Failed to get user accounts: {e}")
            return [], f"Error obteniendo cuentas: {e}"
    
    def set_default_account(self, telegram_user_id: int, account_id: str) -> UserConfiguration:
        """Set user's default account"""
        try:
            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            
            if not user_config or not user_config.budget_id:
                raise YNABApiException("Usuario debe configurar presupuesto primero")
            
            # Verify account exists
            accounts = self.ynab_repository.get_accounts(user_config.budget_id)
            account = next((a for a in accounts if a.id == account_id), None)
            
            if not account:
                raise YNABApiException(f"Cuenta {account_id} no encontrada")
            
            # Update default account
            user_config.update_default_account(account_id, account.name)
            
            # Save changes
            user_config = self.user_repository.save_by_telegram_id(user_config)
            
            logger.info(f"Set default account {account_id} for user {telegram_user_id}")
            return user_config
            
        except Exception as e:
            logger.error(f"Failed to set default account: {e}")
            raise YNABApiException(f"Error configurando cuenta por defecto: {e}")
    
    def get_user_status(self, telegram_user_id: int) -> dict:
        """Get user configuration status"""
        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        
        if not user_config:
            return {
                "configured": False,
                "budget_id": None,
                "budget_name": None,
                "default_account_id": None,
                "default_account_name": None,
                "message": "Usuario no configurado"
            }
        
        status = {
            "configured": user_config.is_configured(),
            "budget_id": user_config.budget_id,
            "budget_name": None,
            "default_account_id": user_config.default_account_id,
            "default_account_name": user_config.default_account_name,
            "created_at": user_config.created_at.isoformat(),
            "updated_at": user_config.updated_at.isoformat()
        }
        
        # Get budget name if configured
        if user_config.budget_id:
            try:
                budgets = self.ynab_repository.get_budgets()
                budget = next((b for b in budgets if b.id == user_config.budget_id), None)
                if budget:
                    status["budget_name"] = budget.name
            except Exception as e:
                logger.error(f"Failed to get budget name: {e}")
        
        if status["configured"]:
            status["message"] = "Usuario completamente configurado"
        elif user_config.budget_id:
            status["message"] = "Falta configurar cuenta por defecto"
        else:
            status["message"] = "Falta configurar presupuesto y cuenta"
        
        return status
    
    def reset_user_config(self, telegram_user_id: int) -> bool:
        """Reset user configuration"""
        try:
            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user_config:
                return True  # Nothing to reset
            
            # Reset to defaults
            user_config.budget_id = None
            user_config.default_account_id = None
            user_config.default_account_name = None
            
            # Save changes
            self.user_repository.save_by_telegram_id(user_config)
            
            logger.info(f"Reset configuration for user {telegram_user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset user config: {e}")
            return False
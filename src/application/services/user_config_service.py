import logging
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from domain.models.user import UserConfiguration, YNABBudget, YNABAccount
from domain.repositories.user_repository import UserRepository
from domain.exceptions import YNABApiException
from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory

logger = logging.getLogger(__name__)


class UserConfigService:
    """Service for managing user configuration"""

    def __init__(self, user_repository: UserRepository, ynab_factory: YNABRepositoryFactory):
        self.user_repository = user_repository
        self.ynab_factory = ynab_factory

    def get_or_create_user_config(self, telegram_user_id: int) -> UserConfiguration:
        """Get existing user configuration or create new one"""
        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)

        if not user_config:
            user_config = UserConfiguration(telegram_id=telegram_user_id)
            user_config = self.user_repository.save(user_config)
            logger.info(f"Created new user configuration for {telegram_user_id}")

        return user_config

    def _get_ynab_repo(self, telegram_user_id: int):
        """Get per-user YNAB repository"""
        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user_config:
            raise YNABApiException("Usuario no encontrado")
        return self.ynab_factory.get_repository(user_config), user_config

    def get_available_budgets(self, telegram_user_id: int) -> List[YNABBudget]:
        """Get all available YNAB budgets for the user"""
        try:
            ynab_repo, _ = self._get_ynab_repo(telegram_user_id)
            budgets = ynab_repo.get_budgets()
            logger.info(f"Retrieved {len(budgets)} available budgets for user {telegram_user_id}")
            return budgets
        except Exception as e:
            logger.error(f"Failed to get budgets: {e}")
            raise YNABApiException(f"No se pudieron obtener los presupuestos: {e}")

    def set_user_budget(self, telegram_user_id: int, budget_id: str) -> UserConfiguration:
        """Set user's budget configuration"""
        try:
            ynab_repo, user_config = self._get_ynab_repo(telegram_user_id)

            # Verify budget exists
            budgets = ynab_repo.get_budgets()
            budget = next((b for b in budgets if b.id == budget_id), None)

            if not budget:
                raise YNABApiException(f"Presupuesto {budget_id} no encontrado")

            # Update budget
            user_config.update_budget(budget_id)

            # Save changes
            user_config = self.user_repository.save(user_config)

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
            ynab_repo = self.ynab_factory.get_repository(user_config)
            accounts = ynab_repo.get_accounts(user_config.budget_id)
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
            ynab_repo = self.ynab_factory.get_repository(user_config)
            accounts = ynab_repo.get_accounts(user_config.budget_id)
            account = next((a for a in accounts if a.id == account_id), None)

            if not account:
                raise YNABApiException(f"Cuenta {account_id} no encontrada")

            # Update default account
            user_config.update_default_account(account_id, account.name)

            # Save changes
            user_config = self.user_repository.save(user_config)

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
                "ynab_connected": False,
                "message": "Usuario no configurado"
            }

        status = {
            "configured": user_config.is_configured(),
            "budget_id": user_config.budget_id,
            "budget_name": None,
            "default_account_id": user_config.default_account_id,
            "default_account_name": user_config.default_account_name,
            "ynab_connected": user_config.has_ynab_token(),
            "timezone": user_config.timezone,
            "created_at": user_config.created_at.isoformat(),
            "updated_at": user_config.updated_at.isoformat()
        }

        # Get budget name if configured and has YNAB token
        if user_config.budget_id and user_config.has_ynab_token():
            try:
                ynab_repo = self.ynab_factory.get_repository(user_config)
                budgets = ynab_repo.get_budgets()
                budget = next((b for b in budgets if b.id == user_config.budget_id), None)
                if budget:
                    status["budget_name"] = budget.name
            except Exception as e:
                logger.error(f"Failed to get budget name: {e}")

        if not user_config.has_ynab_token():
            status["message"] = "Falta conectar cuenta YNAB (/connect)"
        elif status["configured"]:
            status["message"] = "Usuario completamente configurado"
        elif user_config.budget_id:
            status["message"] = "Falta configurar cuenta por defecto"
        else:
            status["message"] = "Falta configurar presupuesto y cuenta"

        return status

    def update_timezone(self, telegram_user_id: int, timezone_str: str) -> UserConfiguration:
        """Update user's timezone. Validates IANA timezone string."""
        try:
            ZoneInfo(timezone_str)
        except (KeyError, Exception):
            raise ValueError(f"Zona horaria invalida: '{timezone_str}'. Usa un nombre IANA valido (ej: America/Bogota).")

        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user_config:
            raise YNABApiException("Usuario no encontrado")

        user_config.update_timezone(timezone_str)
        user_config = self.user_repository.save(user_config)
        logger.info(f"Updated timezone for user {telegram_user_id} to {timezone_str}")
        return user_config

    def set_confirmation_mode(self, telegram_user_id: int, enabled: bool) -> UserConfiguration:
        """Enable or disable confirmation mode for the user before creating transactions."""
        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user_config:
            raise YNABApiException("Usuario no encontrado")

        user_config.toggle_confirmation(enabled)
        user_config = self.user_repository.save(user_config)
        logger.info(f"Set confirmation_mode={enabled} for user {telegram_user_id}")
        return user_config

    def get_confirmation_mode(self, telegram_user_id: int) -> bool:
        """Return whether confirmation before creating is enabled for the user."""
        user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
        if not user_config:
            return False
        return user_config.confirm_before_create

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
            self.user_repository.save(user_config)

            logger.info(f"Reset configuration for user {telegram_user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to reset user config: {e}")
            return False

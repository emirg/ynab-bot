import logging
from typing import TypeVar, Callable, Dict, Any, Type

from application.services.advisor_access_service import AdvisorAccessService
from infrastructure.config.app_config import AppConfig
from infrastructure.dev.stubbed_integrations import (
    StubLLMExpenseParser,
    StubYNABOAuthService,
    StubYNABRepositoryFactory,
)
from infrastructure.repositories.postgres_learning_repository import PostgresLearningRepository
from infrastructure.repositories.postgres_advisor_auth_repository import PostgresAdvisorAuthRepository
from infrastructure.repositories.postgres_manager import PostgresDatabaseManager
from infrastructure.repositories.postgres_split_config_repository import PostgresSplitConfigRepository
from infrastructure.repositories.postgres_user_repository import PostgresUserRepository
from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory
from infrastructure.token_encryption import TokenEncryptor
from application.services.expense_service import ExpenseService
from application.services.budget_query_service import BudgetQueryService
from application.services.user_config_service import UserConfigService
from application.services.learning_service import LearningService
from application.services.onboarding_service import OnboardingService
from application.services.split_config_service import SplitConfigService
from application.services.oauth_service import YNABOAuthService
from application.services.weekly_summary_service import WeeklySummaryService
from application.services.on_demand_summary_service import OnDemandSummaryService
from domain.repositories.advisor_auth_repository import AdvisorAuthRepository
from domain.repositories.learning_repository import LearningRepository
from domain.repositories.split_config_repository import SplitConfigRepository
from domain.repositories.user_repository import UserRepository
from domain.services.auth_service import AuthorizationService
from parsers.llm_expense_parser import LLMExpenseParser
from integrations.speech_to_text import SpeechToTextProcessor

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DIContainer:
    """Dependency Injection Container"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._services: Dict[Type, Callable] = {}
        self._singletons: Dict[Type, Any] = {}
        self._configure_services()

    def _configure_services(self):
        """Configure all service registrations"""

        # Token encryptor
        self.register_singleton(
            TokenEncryptor,
            lambda: TokenEncryptor(self.config.token_encryption_key)
        )

        self._register_persistence_services()

        # OAuth service
        self.register_singleton(
            YNABOAuthService,
            self._create_oauth_service
        )

        # YNAB repository factory (per-user)
        self.register_singleton(
            YNABRepositoryFactory,
            self._create_ynab_factory
        )

        # Register parsers as singletons
        self.register_singleton(
            LLMExpenseParser,
            self._create_llm_parser
        )

        # Register optional speech processor
        self.register_singleton(
            SpeechToTextProcessor,
            self._create_speech_processor_safely
        )

        # Register application services as transients
        self.register_transient(
            BudgetQueryService,
            lambda: BudgetQueryService()
        )

        self.register_transient(
            ExpenseService,
            lambda: ExpenseService(
                user_repository=self.get(UserRepository),
                ynab_factory=self.get(YNABRepositoryFactory),
                learning_repository=self.get(LearningRepository),
                llm_parser=self.get(LLMExpenseParser),
                budget_query_service=self.get(BudgetQueryService),
                split_config_repository=self.get(SplitConfigRepository),
            )
        )

        self.register_transient(
            UserConfigService,
            lambda: UserConfigService(
                user_repository=self.get(UserRepository),
                ynab_factory=self.get(YNABRepositoryFactory)
            )
        )

        self.register_transient(
            LearningService,
            lambda: LearningService(
                learning_repository=self.get(LearningRepository)
            )
        )

        self.register_transient(
            OnboardingService,
            lambda: OnboardingService(
                user_repository=self.get(UserRepository)
            )
        )

        self.register_transient(
            SplitConfigService,
            lambda: SplitConfigService(
                split_config_repository=self.get(SplitConfigRepository),
                user_repository=self.get(UserRepository),
                ynab_factory=self.get(YNABRepositoryFactory)
            )
        )

        self.register_transient(
            WeeklySummaryService,
            lambda: WeeklySummaryService(
                ynab_factory=self.get(YNABRepositoryFactory),
                user_repository=self.get(UserRepository)
            )
        )

        self.register_transient(
            OnDemandSummaryService,
            lambda: OnDemandSummaryService(
                ynab_factory=self.get(YNABRepositoryFactory),
            )
        )

        self.register_transient(
            AdvisorAccessService,
            lambda: AdvisorAccessService(
                config=self.get_config(),
                advisor_auth_repository=self.get(AdvisorAuthRepository),
                user_repository=self.get(UserRepository),
                learning_repository=self.get(LearningRepository),
            )
        )

        # Register authentication service as singleton
        self.register_singleton(
            AuthorizationService,
            lambda: AuthorizationService(
                user_repository=self.get(UserRepository),
                admin_ids=self.config.admin_ids
            )
        )

        logger.info("Dependency injection container configured successfully")

    def _register_persistence_services(self) -> None:
        self.register_singleton(
            PostgresDatabaseManager,
            self._create_postgres_manager
        )
        self.register_singleton(
            PostgresUserRepository,
            lambda: PostgresUserRepository(
                self.get(PostgresDatabaseManager),
                self.get(TokenEncryptor)
            )
        )
        self.register_singleton(
            UserRepository,
            lambda: self.get(PostgresUserRepository)
        )
        self.register_singleton(
            PostgresLearningRepository,
            lambda: PostgresLearningRepository(self.get(PostgresDatabaseManager))
        )
        self.register_singleton(
            LearningRepository,
            lambda: self.get(PostgresLearningRepository)
        )
        self.register_singleton(
            PostgresSplitConfigRepository,
            lambda: PostgresSplitConfigRepository(self.get(PostgresDatabaseManager))
        )
        self.register_singleton(
            SplitConfigRepository,
            lambda: self.get(PostgresSplitConfigRepository)
        )
        self.register_singleton(
            PostgresAdvisorAuthRepository,
            lambda: PostgresAdvisorAuthRepository(self.get(PostgresDatabaseManager))
        )
        self.register_singleton(
            AdvisorAuthRepository,
            lambda: self.get(PostgresAdvisorAuthRepository)
        )

    def _create_speech_processor_safely(self) -> SpeechToTextProcessor:
        """Create speech processor with error handling"""
        if not self.config.use_live_integrations:
            logger.info("Speech processor disabled in stub integration mode")
            return None
        try:
            return SpeechToTextProcessor()
        except Exception as e:
            logger.warning(f"Speech processor not available: {e}")
            return None

    def _create_oauth_service(self):
        if self.config.use_live_integrations:
            return YNABOAuthService(
                config=self.config,
                user_repository=self.get(UserRepository)
            )
        return StubYNABOAuthService(
            config=self.config,
            user_repository=self.get(UserRepository),
        )

    def _create_ynab_factory(self):
        if self.config.use_live_integrations:
            return YNABRepositoryFactory(
                oauth_service=self.get(YNABOAuthService)
            )
        return StubYNABRepositoryFactory()

    def _create_postgres_manager(self) -> PostgresDatabaseManager:
        manager = PostgresDatabaseManager(self.config.postgres_dsn)
        manager.initialize_schema()
        return manager

    def _create_llm_parser(self):
        if self.config.use_live_integrations:
            return LLMExpenseParser()
        return StubLLMExpenseParser()

    def register_singleton(self, interface: Type[T], factory: Callable[[], T]):
        """Register a singleton service"""
        self._services[interface] = ('singleton', factory)

    def register_transient(self, interface: Type[T], factory: Callable[[], T]):
        """Register a transient service"""
        self._services[interface] = ('transient', factory)

    def get(self, interface: Type[T]) -> T:
        """Get service instance"""
        if interface not in self._services:
            raise ValueError(f"Service {interface.__name__} not registered")

        service_type, factory = self._services[interface]

        if service_type == 'singleton':
            if interface not in self._singletons:
                try:
                    instance = factory()
                    self._singletons[interface] = instance
                    logger.debug(f"Created singleton instance of {interface.__name__}")
                except Exception as e:
                    logger.error(f"Failed to create {interface.__name__}: {e}")
                    raise
            return self._singletons[interface]

        elif service_type == 'transient':
            try:
                instance = factory()
                logger.debug(f"Created transient instance of {interface.__name__}")
                return instance
            except Exception as e:
                logger.error(f"Failed to create {interface.__name__}: {e}")
                raise

        else:
            raise ValueError(f"Unknown service type: {service_type}")

    def get_config(self) -> AppConfig:
        """Get application configuration"""
        return self.config

    def has_service(self, interface: Type) -> bool:
        """Check if service is registered"""
        return interface in self._services

    # Convenience methods for commonly used services
    def get_user_repository(self):
        return self.get(UserRepository)

    def get_ynab_factory(self):
        return self.get(YNABRepositoryFactory)

    def get_oauth_service(self):
        return self.get(YNABOAuthService)

    def get_learning_repository(self):
        return self.get(LearningRepository)

    def get_auth_service(self):
        return self.get(AuthorizationService)

    def get_authorization_service(self):
        return self.get(AuthorizationService)

    def get_expense_service(self):
        return self.get(ExpenseService)

    def get_user_config_service(self):
        return self.get(UserConfigService)

    def get_learning_service(self):
        return self.get(LearningService)

    def get_onboarding_service(self):
        return self.get(OnboardingService)

    def get_split_config_service(self):
        return self.get(SplitConfigService)

    def get_speech_processor(self):
        return self.get(SpeechToTextProcessor)

    def get_weekly_summary_service(self):
        return self.get(WeeklySummaryService)

    def get_on_demand_summary_service(self):
        return self.get(OnDemandSummaryService)

    def get_advisor_access_service(self):
        return self.get(AdvisorAccessService)


def create_container(config_path: str = 'config/.env') -> DIContainer:
    """Factory function to create configured DI container"""
    try:
        config = AppConfig.from_env(config_path)
        container = DIContainer(config)
        logger.info("Dependency injection container created successfully")
        return container
    except Exception as e:
        logger.error(f"Failed to create DI container: {e}")
        raise

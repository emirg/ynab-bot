import logging
from typing import TypeVar, Callable, Dict, Any, Type

from infrastructure.config.app_config import AppConfig
from infrastructure.repositories.sqlite_user_repository import SQLiteUserRepository
from infrastructure.repositories.ynab_api_repository import YNABApiRepository
from infrastructure.repositories.json_learning_repository import JSONLearningRepository
from application.services.expense_service import ExpenseService
from application.services.user_config_service import UserConfigService
from application.services.learning_service import LearningService
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
        
        # Register repositories as singletons
        self.register_singleton(
            SQLiteUserRepository,
            lambda: SQLiteUserRepository(self.config.database_absolute_path)
        )
        
        self.register_singleton(
            YNABApiRepository,
            lambda: YNABApiRepository(self.config.ynab_token)
        )
        
        self.register_singleton(
            JSONLearningRepository,
            lambda: JSONLearningRepository(self.config.learning_data_absolute_path)
        )
        
        # Register parsers as singletons
        self.register_singleton(
            LLMExpenseParser,
            lambda: LLMExpenseParser()
        )
        
        # Register optional speech processor
        self.register_singleton(
            SpeechToTextProcessor,
            self._create_speech_processor_safely
        )
        
        # Register application services as transients
        self.register_transient(
            ExpenseService,
            lambda: ExpenseService(
                user_repository=self.get(SQLiteUserRepository),
                ynab_repository=self.get(YNABApiRepository),
                learning_repository=self.get(JSONLearningRepository),
                llm_parser=self.get(LLMExpenseParser)
            )
        )
        
        self.register_transient(
            UserConfigService,
            lambda: UserConfigService(
                user_repository=self.get(SQLiteUserRepository),
                ynab_repository=self.get(YNABApiRepository)
            )
        )
        
        self.register_transient(
            LearningService,
            lambda: LearningService(
                learning_repository=self.get(JSONLearningRepository)
            )
        )
        
        logger.info("Dependency injection container configured successfully")
    
    def _create_speech_processor_safely(self) -> SpeechToTextProcessor:
        """Create speech processor with error handling"""
        try:
            return SpeechToTextProcessor()
        except Exception as e:
            logger.warning(f"Speech processor not available: {e}")
            return None
    
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
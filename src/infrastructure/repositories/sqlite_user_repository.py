import sqlite3
import logging
from datetime import datetime
from typing import Optional
from domain.repositories.user_repository import UserRepository
from domain.models.user import UserConfiguration
from domain.exceptions import YNABBotException

logger = logging.getLogger(__name__)


class SQLiteUserRepository(UserRepository):
    """SQLite implementation of UserRepository"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_configurations (
                        telegram_id INTEGER PRIMARY KEY,
                        budget_id TEXT,
                        default_account_id TEXT,
                        default_account_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                logger.info(f"User database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize user database: {e}")
            raise YNABBotException(f"Database initialization failed: {e}")
    
    def find_by_telegram_id(self, telegram_id: int) -> Optional[UserConfiguration]:
        """Find user configuration by Telegram user ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM user_configurations WHERE telegram_id = ?',
                    (telegram_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return UserConfiguration(
                        telegram_id=row['telegram_id'],
                        budget_id=row['budget_id'],
                        default_account_id=row['default_account_id'],
                        default_account_name=row['default_account_name'],
                        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now()
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to find user {telegram_id}: {e}")
            return None
    
    def find_by_id(self, id: str) -> Optional[UserConfiguration]:
        """Find by string ID (converts to telegram_id)"""
        try:
            telegram_id = int(id)
            return self.find_by_telegram_id(telegram_id)
        except ValueError:
            logger.error(f"Invalid user ID format: {id}")
            return None
    
    def save(self, entity: UserConfiguration) -> UserConfiguration:
        """Save user configuration"""
        return self.save_by_telegram_id(entity)
    
    def save_by_telegram_id(self, user_config: UserConfiguration) -> UserConfiguration:
        """Save user configuration using telegram_id as key"""
        try:
            user_config.updated_at = datetime.now()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO user_configurations 
                    (telegram_id, budget_id, default_account_id, default_account_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user_config.telegram_id,
                    user_config.budget_id,
                    user_config.default_account_id,
                    user_config.default_account_name,
                    user_config.created_at.isoformat(),
                    user_config.updated_at.isoformat()
                ))
                conn.commit()
                
                logger.info(f"User configuration saved for {user_config.telegram_id}")
                return user_config
        except Exception as e:
            logger.error(f"Failed to save user configuration: {e}")
            raise YNABBotException(f"Failed to save user configuration: {e}")
    
    def delete(self, id: str) -> bool:
        """Delete user configuration by ID"""
        try:
            telegram_id = int(id)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'DELETE FROM user_configurations WHERE telegram_id = ?',
                    (telegram_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete user {id}: {e}")
            return False
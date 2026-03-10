import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional, List
from domain.repositories.user_repository import UserRepository
from domain.models.user import UserConfiguration, UserStatus
from domain.exceptions import YNABBotException

logger = logging.getLogger(__name__)


class SQLiteUserRepository(UserRepository):
    """SQLite implementation of UserRepository"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_user_config(row: sqlite3.Row) -> UserConfiguration:
        """Convert a database row to a UserConfiguration domain model"""
        return UserConfiguration(
            telegram_id=row['telegram_id'],
            status=UserStatus(row['status']) if row['status'] else UserStatus.PENDING,
            budget_id=row['budget_id'],
            default_account_id=row['default_account_id'],
            default_account_name=row['default_account_name'],
            username=row['username'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
            approved_at=datetime.fromisoformat(row['approved_at']) if row['approved_at'] else None,
            approved_by=row['approved_by']
        )
    
    def _init_database(self):
        """Initialize database tables"""
        try:
            # Create data directory if it doesn't exist
            data_dir = os.path.dirname(self.db_path)
            if data_dir:
                os.makedirs(data_dir, exist_ok=True)

            conn = self._get_connection()
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_configurations (
                    telegram_id INTEGER PRIMARY KEY,
                    status TEXT DEFAULT 'pending',
                    budget_id TEXT,
                    default_account_id TEXT,
                    default_account_name TEXT,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_at TIMESTAMP,
                    approved_by INTEGER
                )
            ''')

            # Migration for existing tables - add new columns if they don't exist
            try:
                conn.execute('ALTER TABLE user_configurations ADD COLUMN status TEXT DEFAULT "pending"')
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                conn.execute('ALTER TABLE user_configurations ADD COLUMN username TEXT')
                conn.execute('ALTER TABLE user_configurations ADD COLUMN first_name TEXT')
                conn.execute('ALTER TABLE user_configurations ADD COLUMN last_name TEXT')
                conn.execute('ALTER TABLE user_configurations ADD COLUMN approved_at TIMESTAMP')
                conn.execute('ALTER TABLE user_configurations ADD COLUMN approved_by INTEGER')
            except sqlite3.OperationalError:
                pass  # Columns already exist
            conn.commit()
            logger.info(f"User database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize user database: {e}")
            raise YNABBotException(f"Database initialization failed: {e}")
    
    def find_by_telegram_id(self, telegram_id: int) -> Optional[UserConfiguration]:
        """Find user configuration by Telegram user ID"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT * FROM user_configurations WHERE telegram_id = ?',
                (telegram_id,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_user_config(row)
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

            conn = self._get_connection()
            conn.execute('''
                INSERT OR REPLACE INTO user_configurations
                (telegram_id, status, budget_id, default_account_id, default_account_name,
                 username, first_name, last_name, created_at, updated_at, approved_at, approved_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_config.telegram_id,
                user_config.status.value,
                user_config.budget_id,
                user_config.default_account_id,
                user_config.default_account_name,
                user_config.username,
                user_config.first_name,
                user_config.last_name,
                user_config.created_at.isoformat(),
                user_config.updated_at.isoformat(),
                user_config.approved_at.isoformat() if user_config.approved_at else None,
                user_config.approved_by
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
            conn = self._get_connection()
            cursor = conn.execute(
                'DELETE FROM user_configurations WHERE telegram_id = ?',
                (telegram_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete user {id}: {e}")
            return False
    
    def find_by_status(self, status: UserStatus) -> List[UserConfiguration]:
        """Find all users with given status"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT * FROM user_configurations WHERE status = ? ORDER BY created_at DESC',
                (status.value,)
            )
            rows = cursor.fetchall()

            return [self._row_to_user_config(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to find users by status {status}: {e}")
            return []

    def find_all(self) -> List[UserConfiguration]:
        """Find all users"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT * FROM user_configurations ORDER BY created_at DESC'
            )
            rows = cursor.fetchall()

            return [self._row_to_user_config(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to find all users: {e}")
            return []
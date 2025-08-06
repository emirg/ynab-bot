from typing import List, Optional
from telegram import User as TelegramUser

from domain.models.user import UserConfiguration, UserStatus
from domain.repositories.user_repository import UserRepository


class AuthorizationService:
    """Service for handling user authentication and authorization"""
    
    def __init__(self, user_repository: UserRepository, admin_ids: List[int]):
        self.user_repository = user_repository
        self.admin_ids = admin_ids
    
    def is_admin(self, telegram_id: int) -> bool:
        """Check if user is an admin"""
        return telegram_id in self.admin_ids
    
    def register_user(self, telegram_user: TelegramUser) -> UserConfiguration:
        """Register a new user (pending approval)"""
        # Check if user already exists
        existing_user = self.user_repository.find_by_telegram_id(telegram_user.id)
        if existing_user:
            # Update profile information if user exists
            existing_user.update_profile(
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name
            )
            self.user_repository.save(existing_user)
            return existing_user
        
        # Create new user with pending status
        user_config = UserConfiguration(
            telegram_id=telegram_user.id,
            status=UserStatus.AUTHORIZED if self.is_admin(telegram_user.id) else UserStatus.PENDING,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name
        )
        
        # Auto-approve if user is admin
        if self.is_admin(telegram_user.id):
            user_config.authorize(telegram_user.id)
        
        return self.user_repository.save(user_config)
    
    def authorize_user(self, telegram_id: int, admin_id: int) -> bool:
        """Authorize a pending user"""
        if not self.is_admin(admin_id):
            return False
        
        user = self.user_repository.find_by_telegram_id(telegram_id)
        if not user:
            return False
        
        user.authorize(admin_id)
        self.user_repository.save(user)
        return True
    
    def block_user(self, telegram_id: int, admin_id: int) -> bool:
        """Block a user"""
        if not self.is_admin(admin_id):
            return False
        
        user = self.user_repository.find_by_telegram_id(telegram_id)
        if not user:
            return False
        
        user.block()
        self.user_repository.save(user)
        return True
    
    def get_user_status(self, telegram_id: int) -> Optional[UserStatus]:
        """Get user's authorization status"""
        user = self.user_repository.find_by_telegram_id(telegram_id)
        return user.status if user else None
    
    def is_authorized(self, telegram_id: int) -> bool:
        """Check if user is authorized to use the bot"""
        user = self.user_repository.find_by_telegram_id(telegram_id)
        return user and user.is_authorized()
    
    def get_pending_users(self) -> List[UserConfiguration]:
        """Get all users pending approval"""
        return self.user_repository.find_by_status(UserStatus.PENDING)
    
    def get_all_users(self) -> List[UserConfiguration]:
        """Get all registered users"""
        return self.user_repository.find_all()
    
    def get_authorized_users(self) -> List[UserConfiguration]:
        """Get all authorized users"""
        return self.user_repository.find_by_status(UserStatus.AUTHORIZED)
    
    def get_blocked_users(self) -> List[UserConfiguration]:
        """Get all blocked users"""
        return self.user_repository.find_by_status(UserStatus.BLOCKED)
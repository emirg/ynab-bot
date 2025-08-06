import logging
import re
from decimal import Decimal
from typing import List, Optional

from domain.models.expense import Expense, ExpenseResult
from domain.models.user import UserConfiguration, YNABCategory
from domain.repositories.user_repository import UserRepository
from domain.repositories.ynab_repository import YNABRepository
from domain.repositories.learning_repository import LearningRepository
from domain.exceptions import (
    UserNotConfiguredException, 
    ExpenseParsingException,
    YNABApiException,
    InvalidExpenseException
)
from parsers.llm_expense_parser import LLMExpenseParser

logger = logging.getLogger(__name__)


class ExpenseService:
    """Service for processing expense messages and transactions"""
    
    def __init__(
        self,
        user_repository: UserRepository,
        ynab_repository: YNABRepository,
        learning_repository: LearningRepository,
        llm_parser: LLMExpenseParser
    ):
        self.user_repository = user_repository
        self.ynab_repository = ynab_repository
        self.learning_repository = learning_repository
        self.llm_parser = llm_parser
    
    def process_expense_message(self, telegram_user_id: int, message: str) -> ExpenseResult:
        """Main business logic for processing expense messages"""
        try:
            # 1. Get user configuration
            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user_config or not user_config.is_configured():
                missing = "budget_id and account_id" if not user_config else "budget configuration"
                raise UserNotConfiguredException(telegram_user_id, missing)
            
            # 2. Load YNAB data for parsing
            categories = self.ynab_repository.get_categories(user_config.budget_id)
            accounts = self.ynab_repository.get_accounts(user_config.budget_id)
            
            # 3. Update LLM parser with current YNAB data
            self._update_llm_parser_data(categories, accounts)
            
            # 4. Parse expense message
            expense = self._parse_expense_message(message, categories)
            if not expense:
                raise ExpenseParsingException(message, 0.0)
            
            # 5. Enhance with learning predictions
            expense = self._enhance_with_learning(expense, categories)
            
            # 6. Set default account if not specified
            if not expense.account_id:
                expense.account_id = user_config.default_account_id
            
            # 7. Create transaction in YNAB
            transaction_id = self.ynab_repository.create_transaction(
                expense, user_config.budget_id, expense.account_id
            )
            
            if not transaction_id:
                raise YNABApiException("Failed to create transaction")
            
            # 8. Learn from successful transaction
            self.learning_repository.record_successful_transaction(expense)
            self.learning_repository.add_recent_transaction(expense)
            
            logger.info(f"Successfully processed expense: {expense.payee} ${expense.amount}")
            return ExpenseResult.success_result(expense, transaction_id)
            
        except (UserNotConfiguredException, ExpenseParsingException, YNABApiException) as e:
            logger.error(f"Expected error processing expense: {e}")
            return ExpenseResult.error_result(str(e))
        except Exception as e:
            logger.error(f"Unexpected error processing expense: {e}")
            return ExpenseResult.error_result(f"Error interno: {str(e)}")
    
    def _update_llm_parser_data(self, categories: List[YNABCategory], accounts: List):
        """Update LLM parser with current YNAB categories and accounts"""
        try:
            # Convert categories to format expected by LLM parser
            category_list = [
                {
                    'id': cat.id,
                    'full_name': cat.full_name,
                    'name': cat.name,
                    'group_name': cat.group_name
                }
                for cat in categories if not cat.deleted and not cat.hidden
            ]
            
            # Convert accounts to format expected by LLM parser
            account_names = [acc.name for acc in accounts if not acc.deleted and not acc.closed]
            
            self.llm_parser.update_categories(category_list)
            self.llm_parser.update_accounts(account_names)
            
            logger.info(f"Updated LLM parser with {len(category_list)} categories and {len(account_names)} accounts")
            
        except Exception as e:
            logger.error(f"Failed to update LLM parser data: {e}")
    
    def _parse_expense_message(self, message: str, categories: List[YNABCategory]) -> Optional[Expense]:
        """Parse expense message using LLM parser"""
        try:
            result = self.llm_parser.parse_expense(message)
            if not result or result.get('confidence', 0) < 0.3:
                logger.warning(f"Low confidence parse result for: '{message}'")
                return None
            
            # Convert category name to category ID
            category_name = result.get('category')
            category_id = None
            if category_name:
                category_id = self._find_category_id_by_name(category_name, categories)
                if not category_id:
                    logger.warning(f"Could not find category ID for name: '{category_name}'")
            
            # Convert to domain model
            expense = Expense(
                amount=Decimal(str(result['amount'])),
                payee=result['payee'],
                memo=result.get('memo', message),
                category_id=category_id,
                account_id=self._find_account_id_by_name(result.get('account')),
                confidence=result.get('confidence', 0.0),
                parser_source='llm'
            )
            
            # Set category name from the LLM result
            if category_name:
                expense.category_name = category_name
            
            # Validate expense
            if not expense.is_valid():
                logger.error(f"Invalid expense data: {expense}")
                return None
            
            return expense
            
        except Exception as e:
            logger.error(f"Error parsing expense message: {e}")
            return None
    
    def _find_account_id_by_name(self, account_name: str) -> Optional[str]:
        """Find account ID by name (simplified - could be enhanced)"""
        # This is a simplified implementation
        # In a real scenario, you'd want to maintain a mapping of account names to IDs
        return None  # For now, let the service use default account
    
    def _find_category_id_by_name(self, category_name: str, categories: List[YNABCategory]) -> Optional[str]:
        """Find category ID by name with fuzzy matching"""
        if not category_name or not categories:
            return None
        
        category_name = category_name.strip()
        
        # First, try exact match on name
        for category in categories:
            if category.name == category_name:
                logger.debug(f"Exact category name match: '{category_name}' -> {category.id}")
                return category.id
        
        # Try exact match on full_name (includes group)
        for category in categories:
            if category.full_name == category_name:
                logger.debug(f"Exact category full_name match: '{category_name}' -> {category.id}")
                return category.id
        
        # Try case-insensitive match on name
        category_name_lower = category_name.lower()
        for category in categories:
            if category.name.lower() == category_name_lower:
                logger.debug(f"Case-insensitive category match: '{category_name}' -> {category.id}")
                return category.id
        
        # Try partial match (category name contains the search term or vice versa)
        for category in categories:
            if (category_name_lower in category.name.lower() or 
                category.name.lower() in category_name_lower):
                logger.debug(f"Partial category match: '{category_name}' -> '{category.name}' ({category.id})")
                return category.id
        
        # Try match without emojis/special characters
        category_name_clean = re.sub(r'[^\w\s]', '', category_name).strip()
        if category_name_clean:
            for category in categories:
                category_clean = re.sub(r'[^\w\s]', '', category.name).strip()
                if category_name_clean.lower() == category_clean.lower():
                    logger.debug(f"Clean text category match: '{category_name}' -> '{category.name}' ({category.id})")
                    return category.id
        
        logger.warning(f"No category match found for: '{category_name}'")
        logger.debug(f"Available categories: {[cat.name for cat in categories[:10]]}")
        return None
    
    def _is_valid_uuid(self, uuid_string: str) -> bool:
        """Check if string is a valid UUID format"""
        if not uuid_string:
            return False
        
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(uuid_string))
    
    def _enhance_with_learning(self, expense: Expense, categories: List[YNABCategory]) -> Expense:
        """Enhance expense with learning predictions if confidence is low"""
        if expense.confidence > 0.7:  # High confidence, don't override
            return expense
        
        # Try to get learning prediction
        category_list = [{'id': cat.id, 'name': cat.name} for cat in categories]
        prediction = self.learning_repository.predict_category(expense.payee, category_list)
        
        if prediction:
            predicted_category_id, learning_confidence = prediction
            
            # Use learning prediction if it's more confident
            if learning_confidence > expense.confidence:
                logger.info(f"Using learning prediction for {expense.payee}: {predicted_category_id} (confidence: {learning_confidence:.2f})")
                expense.category_id = predicted_category_id
                expense.confidence = learning_confidence
                
                # Update category name
                category = next((cat for cat in categories if cat.id == predicted_category_id), None)
                if category:
                    expense.category_name = category.name
        
        return expense
    
    def correct_recent_transaction(self, telegram_user_id: int, transaction_index: int, new_category_id: str) -> bool:
        """Correct a recent transaction category for learning purposes"""
        try:
            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user_config:
                return False
            
            recent_transactions = self.learning_repository.get_recent_transactions(20)
            
            if transaction_index >= len(recent_transactions):
                logger.error(f"Transaction index {transaction_index} out of range")
                return False
            
            transaction = recent_transactions[transaction_index]
            old_category_id = transaction.get('category_id')
            payee = transaction.get('payee')
            
            if not old_category_id or not payee:
                logger.error("Invalid transaction data for correction")
                return False
            
            # Record the correction for learning
            self.learning_repository.record_user_correction(payee, old_category_id, new_category_id)
            
            logger.info(f"Recorded correction: {payee} {old_category_id} -> {new_category_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error correcting transaction: {e}")
            return False
import logging
import re
import unicodedata
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from domain.models.expense import Expense, ExpenseResult
from domain.models.budget_query import BudgetQueryResult, MessageResult
from domain.models.user import UserConfiguration, YNABCategory, YNABPayee
from domain.time_utils import user_now, DEFAULT_TIMEZONE
from domain.repositories.user_repository import UserRepository
from domain.repositories.learning_repository import LearningRepository
from domain.exceptions import (
    UserNotConfiguredException,
    ExpenseParsingException,
    YNABApiException,
    OAuthException,
    InvalidExpenseException,
    ImageProcessingException
)
from application.services.budget_query_service import BudgetQueryService
from domain.repositories.split_config_repository import SplitConfigRepository
from infrastructure.repositories.ynab_api_repository import YNABRepositoryFactory
from parsers.llm_expense_parser import LLMExpenseParser

logger = logging.getLogger(__name__)

_SPECIAL_CHARS_PATTERN = re.compile(r'[^\w\s]')
_MAX_MESSAGE_LENGTH = 500
_MAX_PAYEE_LENGTH = 200
_CONTROL_CHARS_PATTERN = re.compile(r'[\x00-\x1f\x7f-\x9f]')


class ExpenseService:
    """Service for processing expense messages and transactions"""

    def __init__(
        self,
        user_repository: UserRepository,
        ynab_factory: YNABRepositoryFactory,
        learning_repository: LearningRepository,
        llm_parser: LLMExpenseParser,
        budget_query_service: BudgetQueryService = None,
        split_config_repository: SplitConfigRepository = None,
    ):
        self.user_repository = user_repository
        self.ynab_factory = ynab_factory
        self.learning_repository = learning_repository
        self.llm_parser = llm_parser
        self.budget_query_service = budget_query_service or BudgetQueryService()
        self.split_config_repository = split_config_repository
        self._account_by_name: Dict[str, str] = {}
        self._account_by_name_lower: Dict[str, str] = {}
        self._payee_by_name: Dict[str, Tuple[str, str]] = {}
        self._payee_by_name_lower: Dict[str, Tuple[str, str]] = {}
        self._payee_by_name_normalized: Dict[str, Tuple[str, str]] = {}

    def process_message(self, telegram_user_id: int, message: str) -> MessageResult:
        """Classify and process a user message as expense or query."""
        try:
            if len(message) > _MAX_MESSAGE_LENGTH:
                return MessageResult(
                    intent='expense',
                    expense_result=ExpenseResult.error_result(
                        f"El mensaje es demasiado largo (máximo {_MAX_MESSAGE_LENGTH} caracteres)."
                    ),
                )

            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user_config or not user_config.is_configured():
                missing = "budget_id and account_id" if not user_config else "budget configuration"
                raise UserNotConfiguredException(telegram_user_id, missing)

            ynab_repository = self.ynab_factory.get_repository(user_config)
            categories = ynab_repository.get_categories(user_config.budget_id)
            accounts = ynab_repository.get_accounts(user_config.budget_id)
            payees = ynab_repository.get_payees(user_config.budget_id)
            self._update_llm_parser_data(categories, accounts, payees)

            user_tz = user_config.timezone

            parsed = self.llm_parser.parse_message(message, timezone_str=user_tz)
            if not parsed:
                raise ExpenseParsingException(message, 0.0)

            if parsed.get('intent') == 'query':
                query_result = self.budget_query_service.execute_query(
                    parsed.get('query_type', ''),
                    parsed.get('query_target'),
                    categories,
                    accounts,
                )
                return MessageResult(intent='query', query_result=query_result)

            if parsed.get('intent') == 'shared_expense':
                expense_result = self._process_shared_expense(
                    parsed, message, categories, user_config, ynab_repository, telegram_user_id, user_tz,
                )
                return MessageResult(intent='shared_expense', expense_result=expense_result)

            # Intent is "expense" — delegate to existing pipeline
            expense_result = self._process_parsed_expense(
                parsed, message, categories, user_config, ynab_repository, telegram_user_id, user_tz,
            )
            return MessageResult(intent='expense', expense_result=expense_result)

        except (UserNotConfiguredException, ExpenseParsingException, YNABApiException, OAuthException) as e:
            logger.error(f"Expected error processing message: {e}")
            error_msg = getattr(e, 'user_message', str(e))
            return MessageResult(intent='expense', expense_result=ExpenseResult.error_result(error_msg))
        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")
            return MessageResult(
                intent='expense',
                expense_result=ExpenseResult.error_result("Error interno procesando el mensaje. Intenta de nuevo."),
            )

    def _process_parsed_expense(self, parsed, message, categories, user_config, ynab_repository, telegram_user_id, user_tz: str = DEFAULT_TIMEZONE) -> ExpenseResult:
        """Process an already-parsed expense dict through the existing pipeline."""
        expense = self._build_expense_from_parsed(parsed, message, categories, user_tz=user_tz)
        if not expense:
            raise ExpenseParsingException(message, 0.0)

        expense = self._enhance_with_learning(expense, categories, telegram_user_id)
        expense.category_explanation = self._build_category_explanation(expense)

        if not expense.account_id:
            expense.account_id = user_config.default_account_id
            expense.account_name = user_config.default_account_name

        transaction_id = ynab_repository.create_transaction(
            expense, user_config.budget_id, expense.account_id
        )
        if not transaction_id:
            raise YNABApiException("Failed to create transaction")

        self.learning_repository.record_successful_transaction(telegram_user_id, expense)
        self.learning_repository.add_recent_transaction(telegram_user_id, expense, transaction_id)

        logger.info(f"Successfully processed expense: {expense.payee} ${expense.amount}")
        return ExpenseResult.success_result(expense, transaction_id)

    def _process_shared_expense(self, parsed, message, categories, user_config, ynab_repository, telegram_user_id, user_tz: str = DEFAULT_TIMEZONE) -> ExpenseResult:
        """Process a shared_expense intent through the split pipeline."""
        if self.split_config_repository is None:
            return ExpenseResult.error_result(
                "No tienes configuración de gastos compartidos. Usa /splitwise para configurar."
            )

        person = parsed.get('person', '').strip()
        split_group = self.split_config_repository.find_split_group_by_alias(telegram_user_id, person)
        if not split_group:
            return ExpenseResult.error_result(
                f"No encontré un grupo para '{person}'. Usa /splitwise para agregar aliases."
            )

        proportion = self._parse_proportion(parsed.get('proportion'))
        payer = parsed.get('payer', 'user')

        expense = self._build_expense_from_parsed(parsed, message, categories, user_tz=user_tz)
        if not expense:
            raise ExpenseParsingException(message, 0.0)

        expense.is_split = True
        expense.split_person = person
        expense.split_proportion = proportion
        expense.split_category_id = split_group.category_id
        expense.split_category_name = split_group.category_name
        expense.payer = payer

        if payer == 'other':
            # When the other person paid, use the shared tracking account
            shared_account = self.split_config_repository.get_shared_account(telegram_user_id)
            if not shared_account:
                return ExpenseResult.error_result(
                    "No tienes una cuenta compartida configurada. Usa /splitwise para configurarla."
                )
            expense.account_id = shared_account.account_id
            expense.account_name = shared_account.account_name
        else:
            expense = self._enhance_with_learning(expense, categories, telegram_user_id)
            expense.category_explanation = self._build_category_explanation(expense)

            if not expense.account_id:
                expense.account_id = user_config.default_account_id
                expense.account_name = user_config.default_account_name

        transaction_id = ynab_repository.create_transaction(
            expense, user_config.budget_id, expense.account_id
        )
        if not transaction_id:
            raise YNABApiException("Failed to create transaction")

        self.learning_repository.record_successful_transaction(telegram_user_id, expense)
        self.learning_repository.add_recent_transaction(telegram_user_id, expense, transaction_id)

        logger.info(f"Successfully processed shared expense: {expense.payee} ${expense.amount} with {person} (payer={payer})")
        return ExpenseResult.success_result(expense, transaction_id)

    @staticmethod
    def _parse_proportion(value) -> Decimal:
        """Parse a proportion string like '1/2', '1/3' into a Decimal. Defaults to 0.5."""
        if value is None:
            return Decimal('0.5')
        try:
            value = str(value).strip()
            if '/' in value:
                parts = value.split('/')
                return Decimal(parts[0]) / Decimal(parts[1])
            return Decimal(value)
        except Exception:
            return Decimal('0.5')

    def _build_expense_from_parsed(self, result: dict, message: str, categories, parser_source: str = 'llm', user_tz: str = DEFAULT_TIMEZONE) -> Optional[Expense]:
        """Build an Expense domain object from a parsed LLM result dict."""
        try:
            if result.get('confidence', 0) < 0.3:
                logger.warning(f"Low confidence parse result for: '{message}'")
                return None

            category_name = result.get('category')
            category_id = None
            if category_name:
                category_id = self._find_category_id_by_name(category_name, categories)
                if not category_id:
                    logger.warning(f"Could not find category ID for name: '{category_name}'")

            payee = _CONTROL_CHARS_PATTERN.sub('', str(result.get('payee', '')))[:_MAX_PAYEE_LENGTH]
            memo = _CONTROL_CHARS_PATTERN.sub('', str(result.get('memo', message)))[:_MAX_MESSAGE_LENGTH]

            # Match payee against existing YNAB payees
            payee_id = None
            payee_match = self._match_payee(payee)
            if payee_match:
                payee_id, canonical_name = payee_match
                logger.info(f"Matched payee '{payee}' -> '{canonical_name}' ({payee_id})")
                payee = canonical_name

            account_name_raw = result.get('account')
            account_id = self._find_account_id_by_name(account_name_raw)

            expense = Expense(
                amount=Decimal(str(result['amount'])),
                payee=payee,
                memo=memo,
                category_id=category_id,
                payee_id=payee_id,
                account_id=account_id,
                account_name=account_name_raw if account_id else None,
                confidence=result.get('confidence', 0.0),
                parser_source=parser_source,
            )

            date_str = result.get('date')
            if date_str:
                try:
                    expense.date = datetime.strptime(date_str, "%Y-%m-%d")
                except (ValueError, TypeError):
                    expense.date = user_now(user_tz)
            else:
                expense.date = user_now(user_tz)

            if category_name:
                expense.category_name = category_name

            if not expense.is_valid():
                logger.error(f"Invalid expense data: {expense}")
                return None

            return expense

        except Exception as e:
            logger.error(f"Error building expense from parsed data: {e}")
            return None

    def process_receipt_image(self, telegram_user_id: int, image_base64: str, caption: str = None) -> ExpenseResult:
        """Process a receipt image using GPT Vision and create a YNAB transaction."""
        try:
            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user_config or not user_config.is_configured():
                missing = "budget_id and account_id" if not user_config else "budget configuration"
                raise UserNotConfiguredException(telegram_user_id, missing)

            ynab_repository = self.ynab_factory.get_repository(user_config)
            categories = ynab_repository.get_categories(user_config.budget_id)
            accounts = ynab_repository.get_accounts(user_config.budget_id)
            payees = ynab_repository.get_payees(user_config.budget_id)
            self._update_llm_parser_data(categories, accounts, payees)

            user_tz = user_config.timezone

            parsed = self.llm_parser.parse_receipt_image(image_base64, caption, timezone_str=user_tz)
            if not parsed:
                return ExpenseResult.error_result("No se pudo analizar el recibo. Asegúrate de que la imagen sea legible.")

            expense = self._build_expense_from_parsed(parsed, caption or "Recibo", categories, parser_source='receipt', user_tz=user_tz)
            if not expense:
                return ExpenseResult.error_result("No se pudo extraer información válida del recibo.")

            expense = self._enhance_with_learning(expense, categories, telegram_user_id)
            expense.category_explanation = self._build_category_explanation(expense)

            if not expense.account_id:
                expense.account_id = user_config.default_account_id
                expense.account_name = user_config.default_account_name

            transaction_id = ynab_repository.create_transaction(
                expense, user_config.budget_id, expense.account_id
            )
            if not transaction_id:
                raise YNABApiException("Failed to create transaction")

            self.learning_repository.record_successful_transaction(telegram_user_id, expense)
            self.learning_repository.add_recent_transaction(telegram_user_id, expense, transaction_id)

            logger.info(f"Successfully processed receipt: {expense.payee} ${expense.amount}")
            return ExpenseResult.success_result(expense, transaction_id)

        except (UserNotConfiguredException, ExpenseParsingException, YNABApiException, OAuthException, ImageProcessingException) as e:
            logger.error(f"Expected error processing receipt: {e}")
            error_msg = getattr(e, 'user_message', str(e))
            return ExpenseResult.error_result(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error processing receipt: {e}")
            return ExpenseResult.error_result("Error interno procesando el recibo. Intenta de nuevo.")

    def process_expense_message(self, telegram_user_id: int, message: str) -> ExpenseResult:
        """Main business logic for processing expense messages"""
        try:
            # 0. Validate input length
            if len(message) > _MAX_MESSAGE_LENGTH:
                return ExpenseResult.error_result(
                    f"El mensaje es demasiado largo (máximo {_MAX_MESSAGE_LENGTH} caracteres)."
                )

            # 1. Get user configuration
            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user_config or not user_config.is_configured():
                missing = "budget_id and account_id" if not user_config else "budget configuration"
                raise UserNotConfiguredException(telegram_user_id, missing)

            # 2. Get per-user YNAB repository
            ynab_repository = self.ynab_factory.get_repository(user_config)

            # 3. Load YNAB data for parsing
            categories = ynab_repository.get_categories(user_config.budget_id)
            accounts = ynab_repository.get_accounts(user_config.budget_id)
            payees = ynab_repository.get_payees(user_config.budget_id)

            # 4. Update LLM parser with current YNAB data
            self._update_llm_parser_data(categories, accounts, payees)

            user_tz = user_config.timezone

            # 5. Parse expense message
            expense = self._parse_expense_message(message, categories, user_tz=user_tz)
            if not expense:
                raise ExpenseParsingException(message, 0.0)

            # 6. Enhance with learning predictions
            expense = self._enhance_with_learning(expense, categories, telegram_user_id)
            expense.category_explanation = self._build_category_explanation(expense)

            # 7. Set default account if not specified
            if not expense.account_id:
                expense.account_id = user_config.default_account_id
                expense.account_name = user_config.default_account_name

            # 8. Create transaction in YNAB
            transaction_id = ynab_repository.create_transaction(
                expense, user_config.budget_id, expense.account_id
            )

            if not transaction_id:
                raise YNABApiException("Failed to create transaction")

            # 8. Learn from successful transaction
            self.learning_repository.record_successful_transaction(telegram_user_id, expense)
            self.learning_repository.add_recent_transaction(telegram_user_id, expense, transaction_id)

            logger.info(f"Successfully processed expense: {expense.payee} ${expense.amount}")
            return ExpenseResult.success_result(expense, transaction_id)

        except (UserNotConfiguredException, ExpenseParsingException, YNABApiException, OAuthException) as e:
            logger.error(f"Expected error processing expense: {e}")
            error_msg = getattr(e, 'user_message', str(e))
            return ExpenseResult.error_result(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error processing expense: {e}")
            return ExpenseResult.error_result("Error interno procesando el gasto. Intenta de nuevo.")

    @staticmethod
    def _normalize_payee_name(name: str) -> str:
        """Normalize a payee name by stripping accents, punctuation, and lowercasing."""
        # Strip accents: NFD decompose, remove combining chars, encode ascii
        nfkd = unicodedata.normalize('NFD', name)
        ascii_only = nfkd.encode('ascii', 'ignore').decode('ascii')
        # Remove punctuation and extra whitespace, lowercase
        clean = _SPECIAL_CHARS_PATTERN.sub('', ascii_only).strip().lower()
        return clean

    def _update_llm_parser_data(self, categories: List[YNABCategory], accounts: List, payees: List[YNABPayee] = None):
        """Update LLM parser with current YNAB categories, accounts, and payees"""
        try:
            # Filter active categories once, reuse across parser and lookup maps
            active_categories = [cat for cat in categories if not cat.deleted and not cat.hidden]

            # Convert categories to format expected by LLM parser
            category_list = [
                {
                    'id': cat.id,
                    'full_name': cat.full_name,
                    'name': cat.name,
                    'group_name': cat.group_name
                }
                for cat in active_categories
            ]

            # Build category lookup maps for O(1) matching
            self._category_by_name: Dict[str, str] = {}
            self._category_by_full_name: Dict[str, str] = {}
            self._category_by_name_lower: Dict[str, str] = {}
            self._category_by_clean_lower: Dict[str, str] = {}
            for cat in active_categories:
                self._category_by_name[cat.name] = cat.id
                self._category_by_full_name[cat.full_name] = cat.id
                self._category_by_name_lower[cat.name.lower()] = cat.id
                clean = _SPECIAL_CHARS_PATTERN.sub('', cat.name).strip().lower()
                if clean:
                    self._category_by_clean_lower[clean] = cat.id

            # Build account lookup maps for O(1) matching
            active_accounts = [acc for acc in accounts if not acc.deleted and not acc.closed]
            self._account_by_name: Dict[str, str] = {}
            self._account_by_name_lower: Dict[str, str] = {}
            for acc in active_accounts:
                self._account_by_name[acc.name] = acc.id
                self._account_by_name_lower[acc.name.lower()] = acc.id

            # Build payee lookup maps for O(1) matching
            if payees:
                self._payee_by_name = {}
                self._payee_by_name_lower = {}
                self._payee_by_name_normalized = {}
                for payee in payees:
                    if payee.deleted:
                        continue
                    entry = (payee.id, payee.name)
                    self._payee_by_name[payee.name] = entry
                    self._payee_by_name_lower[payee.name.lower()] = entry
                    normalized = self._normalize_payee_name(payee.name)
                    if normalized:
                        self._payee_by_name_normalized[normalized] = entry

            # Convert accounts to format expected by LLM parser
            account_names = [acc.name for acc in active_accounts]

            self.llm_parser.update_categories(category_list)
            self.llm_parser.update_accounts(account_names)

            payee_count = len(self._payee_by_name) if payees else 0
            logger.info(f"Updated LLM parser with {len(category_list)} categories, {len(account_names)} accounts, and {payee_count} payees")

        except Exception as e:
            logger.error(f"Failed to update LLM parser data: {e}")

    def _parse_expense_message(self, message: str, categories: List[YNABCategory], user_tz: str = DEFAULT_TIMEZONE) -> Optional[Expense]:
        """Parse expense message using LLM parser"""
        try:
            result = self.llm_parser.parse_expense(message, timezone_str=user_tz)
            if not result:
                return None
            return self._build_expense_from_parsed(result, message, categories, parser_source='llm', user_tz=user_tz)
        except Exception as e:
            logger.error(f"Error parsing expense message: {e}")
            return None

    def _match_payee(self, payee_name: str) -> Optional[Tuple[str, str]]:
        """Match payee name against existing YNAB payees. Returns (payee_id, canonical_name) or None."""
        if not payee_name or not self._payee_by_name:
            return None

        payee_name = payee_name.strip()
        if not payee_name:
            return None

        # Exact match
        if payee_name in self._payee_by_name:
            return self._payee_by_name[payee_name]

        # Case-insensitive match
        payee_lower = payee_name.lower()
        if payee_lower in self._payee_by_name_lower:
            return self._payee_by_name_lower[payee_lower]

        # Normalized match (no accents/punctuation)
        payee_normalized = self._normalize_payee_name(payee_name)
        if payee_normalized and payee_normalized in self._payee_by_name_normalized:
            return self._payee_by_name_normalized[payee_normalized]

        # Containment match (linear scan, last resort)
        for name_lower, entry in self._payee_by_name_lower.items():
            if payee_lower in name_lower or name_lower in payee_lower:
                logger.debug(f"Partial payee match: '{payee_name}' -> '{entry[1]}'")
                return entry

        return None

    def _find_account_id_by_name(self, account_name: str) -> Optional[str]:
        """Find account ID by name using pre-built lookup maps"""
        if not account_name:
            return None

        account_name = account_name.strip()
        
        # Handle string "null" or "none" from LLM
        if account_name.lower() in ('null', 'none'):
            return None

        # Exact match
        if account_name in self._account_by_name:
            return self._account_by_name[account_name]

        # Case-insensitive match
        account_name_lower = account_name.lower()
        if account_name_lower in self._account_by_name_lower:
            return self._account_by_name_lower[account_name_lower]

        # Partial match (fallback to linear scan)
        for name, account_id in self._account_by_name_lower.items():
            if account_name_lower in name or name in account_name_lower:
                logger.debug(f"Partial account match: '{account_name}' -> '{name}'")
                return account_id

        logger.warning(f"No account match found for: '{account_name}'")
        return None

    def _find_category_id_by_name(self, category_name: str, categories: List[YNABCategory]) -> Optional[str]:
        """Find category ID by name using pre-built lookup maps (O(1) per attempt)"""
        if not category_name:
            return None

        category_name = category_name.strip()

        # Exact match on name
        if category_name in self._category_by_name:
            return self._category_by_name[category_name]

        # Exact match on full_name
        if category_name in self._category_by_full_name:
            return self._category_by_full_name[category_name]

        # Case-insensitive match
        category_name_lower = category_name.lower()
        if category_name_lower in self._category_by_name_lower:
            return self._category_by_name_lower[category_name_lower]

        # Partial match (fallback to linear scan, only when dict lookups fail)
        for cat in categories:
            cat_lower = cat.name.lower()
            if category_name_lower in cat_lower or cat_lower in category_name_lower:
                logger.debug(f"Partial category match: '{category_name}' -> '{cat.name}' ({cat.id})")
                return cat.id

        # Match without emojis/special characters
        category_name_clean = _SPECIAL_CHARS_PATTERN.sub('', category_name).strip().lower()
        if category_name_clean and category_name_clean in self._category_by_clean_lower:
            return self._category_by_clean_lower[category_name_clean]

        logger.warning(f"No category match found for: '{category_name}'")
        return None

    def _enhance_with_learning(self, expense: Expense, categories: List[YNABCategory], telegram_user_id: int) -> Expense:
        """Enhance expense with learning predictions if confidence is low"""
        # Try to get learning prediction
        category_list = [{'id': cat.id, 'name': cat.name} for cat in categories]
        prediction = self.learning_repository.predict_category(telegram_user_id, expense.payee, category_list)

        if prediction:
            predicted_category_id, learning_confidence, mapping_count = prediction

            # Use learning prediction if it's more confident
            if learning_confidence > expense.confidence:
                logger.info(f"Using learning prediction for {expense.payee}: {predicted_category_id} (confidence: {learning_confidence:.2f}, count: {mapping_count})")
                expense.category_id = predicted_category_id
                expense.confidence = learning_confidence
                expense.category_explanation = f"aprendido de tus ultimas {mapping_count} compras en {expense.payee}"

                # Update category name
                category = next((cat for cat in categories if cat.id == predicted_category_id), None)
                if category:
                    expense.category_name = category.name

        return expense

    def _build_category_explanation(self, expense: Expense) -> str:
        """Build a Spanish explanation of why this category was chosen"""
        if expense.category_explanation:
            return expense.category_explanation

        conf_pct = int(expense.confidence * 100)
        
        if expense.parser_source == 'receipt':
            return f"detectado del recibo, confianza {conf_pct}%"
        
        if expense.parser_source == 'llm':
            if expense.confidence > 0.7:
                return f"sugerido por IA, confianza {conf_pct}%"
            else:
                return f"sugerido por IA, confianza {conf_pct}% - considera verificar"
        
        return f"confianza {conf_pct}%"

    def _is_within_time_window(self, transaction: dict, user_config) -> bool:
        """Return True if the transaction is within the allowed edit/undo time window.

        The window passes when EITHER:
        - The transaction was created within the last 5 minutes (UTC), OR
        - The transaction date falls on today in the user's timezone.

        Both checks use the 'timestamp' key returned by get_recent_transactions.
        """
        timestamp_str = transaction.get('timestamp')
        if not timestamp_str:
            return False

        try:
            txn_dt = datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            return False

        # 5-minute check (compare naive UTC datetimes)
        now_utc = datetime.utcnow()
        txn_naive = txn_dt.replace(tzinfo=None) if txn_dt.tzinfo else txn_dt
        within_5_min = (now_utc - txn_naive) <= timedelta(minutes=5)

        # Same-day check in user's timezone
        is_today = False
        try:
            now_user = user_now(user_config.timezone)
            txn_date_user = (
                txn_dt.date() if not txn_dt.tzinfo
                else txn_dt.astimezone(ZoneInfo(user_config.timezone)).date()
            )
            is_today = txn_date_user == now_user.date()
        except (ValueError, TypeError):
            pass

        return within_5_min or is_today

    def _find_account_id_from_accounts_list(self, account_name: str, accounts: list) -> Optional[str]:
        """Find account ID by name from a list of account objects (3-step fuzzy match).

        Used by edit_last_transaction to match user input against live YNAB accounts.
        Steps: exact -> case-insensitive -> partial (substring in either direction).
        Returns account id string or None if no match found.
        """
        if not account_name or not accounts:
            return None

        input_stripped = account_name.strip()
        input_lower = input_stripped.lower()

        # Step 1: Exact match
        for account in accounts:
            if account.name == input_stripped:
                return account.id

        # Step 2: Case-insensitive match
        for account in accounts:
            if account.name.lower() == input_lower:
                return account.id

        # Step 3: Partial match (substring in either direction)
        for account in accounts:
            account_name_lower = account.name.lower()
            if input_lower in account_name_lower or account_name_lower in input_lower:
                logger.debug(f"Partial account match: '{account_name}' -> '{account.name}'")
                return account.id

        return None

    def edit_last_transaction(
        self,
        telegram_user_id: int,
        transaction_index: int = 0,
        new_amount: Optional[Decimal] = None,
        new_payee: Optional[str] = None,
        new_category: Optional[str] = None,
        new_account: Optional[str] = None,
    ) -> Optional[Dict]:
        """Edit fields of a recent transaction: amount, payee, category, and/or account.

        Enforces the same time window as undo_last_transaction. Category edits
        trigger learning updates (same as the old correct_recent_transaction).

        Args:
            telegram_user_id: Telegram user ID.
            transaction_index: 0-based index into recent transactions (0 = most recent).
            new_amount: New amount as a positive Decimal (will be negated to milliunits).
            new_payee: New payee name string.
            new_category: New category name (fuzzy matched).
            new_account: New account name (fuzzy matched).

        Returns:
            dict with old/new field values on success,
            dict with 'error' key on validation failure,
            None on unexpected failure or user not configured.
        """
        try:
            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user_config or not user_config.is_configured():
                return None

            # Fetch enough recent transactions to cover the requested index
            fetch_count = max(transaction_index + 1, 20)
            recent_transactions = self.learning_repository.get_recent_transactions(
                telegram_user_id, fetch_count
            )

            # Bounds check
            if transaction_index >= len(recent_transactions):
                return {"error": "index_out_of_range"}

            transaction = recent_transactions[transaction_index]
            ynab_transaction_id = transaction.get('ynab_transaction_id')
            if not ynab_transaction_id:
                return {"error": "no_ynab_transaction_id"}

            # Validate time window
            if not self._is_within_time_window(transaction, user_config):
                return {"error": "time_window_exceeded"}

            # Create YNAB repository
            ynab_repository = self.ynab_factory.get_repository(user_config)
            budget_id = user_config.budget_id

            # Build fields dict for YNAB update
            fields: Dict = {}
            changes: Dict = {}
            payee = transaction.get('payee', '')
            old_category_id = transaction.get('category_id')
            resolved_category_id = None
            resolved_category_name = None

            if new_amount is not None:
                amount_milliunits = int(new_amount * -1000)
                old_amount = transaction.get('amount', 0)
                fields['amount'] = amount_milliunits
                changes['amount'] = {'old': old_amount, 'new': float(new_amount)}

            if new_payee is not None:
                old_payee = payee
                fields['payee_name'] = new_payee
                # Attempt payee ID matching (uses pre-built dicts from last parse; best effort)
                payee_match = self._match_payee(new_payee)
                if payee_match:
                    payee_id, canonical_name = payee_match
                    fields['payee_id'] = payee_id
                changes['payee'] = {'old': old_payee, 'new': new_payee}

            if new_category is not None:
                categories = ynab_repository.get_categories(budget_id)
                self._update_llm_parser_data(categories, [], [])
                resolved_category_id = self._find_category_id_by_name(new_category, categories)
                if not resolved_category_id:
                    return {"error": "category_not_found", "message": f"No encontré una categoría que coincida con '{new_category}'."}
                # Look up the canonical category name
                resolved_category_name = new_category
                for cat in categories:
                    if cat.id == resolved_category_id:
                        resolved_category_name = cat.name
                        break
                old_category_name = transaction.get('category_name', old_category_id or '')
                fields['category_id'] = resolved_category_id
                changes['category'] = {'old': old_category_name, 'new': resolved_category_name}

            if new_account is not None:
                accounts = ynab_repository.get_accounts(budget_id)
                resolved_account_id = self._find_account_id_from_accounts_list(new_account, accounts)
                if not resolved_account_id:
                    return {"error": "account_not_found", "message": f"No encontré una cuenta que coincida con '{new_account}'."}
                fields['account_id'] = resolved_account_id
                changes['account'] = {'new': new_account}

            # Perform the YNAB update
            updated = ynab_repository.update_transaction(budget_id, ynab_transaction_id, fields)
            if not updated:
                return {"error": "ynab_update_failed"}

            # Learning update for category edits
            if resolved_category_id and old_category_id and payee:
                self.learning_repository.record_user_correction(
                    telegram_user_id, payee, old_category_id, resolved_category_id, resolved_category_name
                )
                logger.info(
                    f"Recorded category correction: {payee} {old_category_id} -> {resolved_category_id}"
                )

            logger.info(f"Edited transaction {ynab_transaction_id}: fields={list(fields.keys())}")
            return {
                'payee': payee,
                'changes': changes,
                'ynab_transaction_id': ynab_transaction_id,
            }

        except Exception as e:
            logger.error(f"Error editing transaction: {e}")
            return None

    def undo_last_transaction(self, telegram_user_id: int) -> Optional[Dict]:
        """Delete the most recent transaction if within the allowed time window.

        Time window: created within the last 5 minutes, OR it is the most recent
        transaction created today (in the user's timezone).

        Returns:
          - dict with 'payee', 'amount', 'category_name' on success
          - dict with 'error' key on validation failure
          - None on unexpected failure or user not configured
        """
        try:
            user_config = self.user_repository.find_by_telegram_id(telegram_user_id)
            if not user_config or not user_config.is_configured():
                return None

            recent_transactions = self.learning_repository.get_recent_transactions(telegram_user_id, 1)
            if not recent_transactions:
                return {"error": "no_recent_transactions"}

            transaction = recent_transactions[0]
            ynab_transaction_id = transaction.get('ynab_transaction_id')
            if not ynab_transaction_id:
                return {"error": "no_ynab_transaction_id"}

            # Validate time window
            if not self._is_within_time_window(transaction, user_config):
                return {"error": "time_window_exceeded"}

            # Delete from YNAB
            ynab_repository = self.ynab_factory.get_repository(user_config)
            deleted = ynab_repository.delete_transaction(user_config.budget_id, ynab_transaction_id)
            if not deleted:
                return {"error": "ynab_delete_failed"}

            # Update learning: decrement payee-category association
            payee = transaction.get('payee', '')
            category_id = transaction.get('category_id', '')
            if payee and category_id:
                self.learning_repository.decrement_learning(telegram_user_id, payee, category_id)

            # Remove from local recent transactions
            self.learning_repository.delete_recent_transaction(telegram_user_id, ynab_transaction_id)

            logger.info(f"Undid transaction: {payee} {ynab_transaction_id}")
            return {
                'payee': payee,
                'amount': transaction.get('amount', 0),
                'category_name': transaction.get('category_name', ''),
            }

        except Exception as e:
            logger.error(f"Error undoing transaction: {e}")
            return None

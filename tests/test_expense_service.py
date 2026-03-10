"""Tests for ExpenseService."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock

from application.services.expense_service import ExpenseService, _SPECIAL_CHARS_PATTERN
from domain.models.expense import Expense
from domain.models.user import UserConfiguration, UserStatus, YNABCategory

TELEGRAM_ID = 123456789


@pytest.fixture
def service(mock_user_repository, mock_ynab_repository, mock_learning_repository, mock_llm_parser, authorized_user):
    mock_user_repository.find_by_telegram_id.return_value = authorized_user
    return ExpenseService(
        user_repository=mock_user_repository,
        ynab_repository=mock_ynab_repository,
        learning_repository=mock_learning_repository,
        llm_parser=mock_llm_parser,
    )


# ---------------------------------------------------------------------------
# _SPECIAL_CHARS_PATTERN
# ---------------------------------------------------------------------------

class TestSpecialCharsPattern:

    def test_removes_emojis(self):
        assert _SPECIAL_CHARS_PATTERN.sub('', '🛒 Groceries') == ' Groceries'

    def test_keeps_word_chars(self):
        assert _SPECIAL_CHARS_PATTERN.sub('', 'Hello World 123') == 'Hello World 123'

    def test_removes_arrows(self):
        assert _SPECIAL_CHARS_PATTERN.sub('', 'Essentials → Food') == 'Essentials  Food'


# ---------------------------------------------------------------------------
# process_expense_message - happy path
# ---------------------------------------------------------------------------

class TestProcessExpenseMessage:

    def test_success(self, service):
        result = service.process_expense_message(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        assert result.success is True
        assert result.transaction_id == 'txn-id-123'

    def test_calls_ynab_to_get_data(self, service, mock_ynab_repository, authorized_user):
        service.process_expense_message(TELEGRAM_ID, 'test')
        mock_ynab_repository.get_categories.assert_called_with(authorized_user.budget_id)
        mock_ynab_repository.get_accounts.assert_called_with(authorized_user.budget_id)

    def test_calls_llm_parser(self, service, mock_llm_parser):
        service.process_expense_message(TELEGRAM_ID, 'test message')
        mock_llm_parser.parse_expense.assert_called_with('test message')

    def test_records_learning(self, service, mock_learning_repository):
        service.process_expense_message(TELEGRAM_ID, 'test')
        mock_learning_repository.record_successful_transaction.assert_called_once()
        # Verify telegram_id is passed
        call_args = mock_learning_repository.record_successful_transaction.call_args
        assert call_args[0][0] == TELEGRAM_ID
        mock_learning_repository.add_recent_transaction.assert_called_once()
        call_args = mock_learning_repository.add_recent_transaction.call_args
        assert call_args[0][0] == TELEGRAM_ID

    def test_creates_transaction(self, service, mock_ynab_repository):
        service.process_expense_message(TELEGRAM_ID, 'test')
        mock_ynab_repository.create_transaction.assert_called_once()


# ---------------------------------------------------------------------------
# process_expense_message - error paths
# ---------------------------------------------------------------------------

class TestProcessExpenseErrors:

    def test_message_too_long(self, service):
        long_message = 'x' * 501
        result = service.process_expense_message(TELEGRAM_ID, long_message)
        assert not result.success
        assert 'largo' in result.error_message.lower()

    def test_message_at_limit(self, service):
        """Message exactly at limit should be processed normally"""
        result = service.process_expense_message(TELEGRAM_ID, 'x' * 500)
        assert result is not None

    def test_user_not_found(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.process_expense_message(999, 'test')
        assert not result.success
        assert 'not configured' in result.error_message.lower() or 'not configured' in result.error_message

    def test_user_not_configured(self, service, mock_user_repository):
        user = UserConfiguration(telegram_id=999, status=UserStatus.AUTHORIZED)
        mock_user_repository.find_by_telegram_id.return_value = user
        result = service.process_expense_message(999, 'test')
        assert not result.success

    def test_parse_failure(self, service, mock_llm_parser):
        mock_llm_parser.parse_expense.return_value = None
        result = service.process_expense_message(TELEGRAM_ID, 'nonsense')
        assert not result.success

    def test_low_confidence_parse(self, service, mock_llm_parser):
        mock_llm_parser.parse_expense.return_value = {
            'amount': 100, 'category': 'X', 'payee': 'Y',
            'memo': 'z', 'confidence': 0.1,
        }
        result = service.process_expense_message(TELEGRAM_ID, 'unclear')
        assert not result.success

    def test_ynab_transaction_failure(self, service, mock_ynab_repository):
        mock_ynab_repository.create_transaction.return_value = None
        result = service.process_expense_message(TELEGRAM_ID, 'test')
        assert not result.success


# ---------------------------------------------------------------------------
# _update_llm_parser_data and category lookup maps
# ---------------------------------------------------------------------------

class TestCategoryLookupMaps:

    def test_builds_maps(self, service, sample_categories, sample_accounts):
        service._update_llm_parser_data(sample_categories, sample_accounts)
        assert 'Groceries' in service._category_by_name
        assert 'Hidden' not in service._category_by_name
        assert 'Deleted' not in service._category_by_name

    def test_case_insensitive_map(self, service, sample_categories, sample_accounts):
        service._update_llm_parser_data(sample_categories, sample_accounts)
        assert 'groceries' in service._category_by_name_lower
        assert 'restaurants' in service._category_by_name_lower

    def test_full_name_map(self, service, sample_categories, sample_accounts):
        service._update_llm_parser_data(sample_categories, sample_accounts)
        assert 'Essentials -> Groceries' in service._category_by_full_name


# ---------------------------------------------------------------------------
# _find_category_id_by_name
# ---------------------------------------------------------------------------

class TestFindCategoryByName:

    @pytest.fixture(autouse=True)
    def setup_maps(self, service, sample_categories, sample_accounts):
        service._update_llm_parser_data(sample_categories, sample_accounts)
        self.categories = [c for c in sample_categories if not c.deleted and not c.hidden]

    def test_exact_name_match(self, service):
        assert service._find_category_id_by_name('Groceries', self.categories) == 'cat-1'

    def test_exact_full_name_match(self, service):
        assert service._find_category_id_by_name('Essentials -> Restaurants', self.categories) == 'cat-2'

    def test_case_insensitive_match(self, service):
        assert service._find_category_id_by_name('groceries', self.categories) == 'cat-1'
        assert service._find_category_id_by_name('TRANSPORT', self.categories) == 'cat-3'

    def test_partial_match(self, service):
        assert service._find_category_id_by_name('Grocer', self.categories) == 'cat-1'

    def test_partial_match_reverse(self, service):
        assert service._find_category_id_by_name('Restaurants & Bar', self.categories) == 'cat-2'

    def test_clean_text_match(self, service):
        cat_with_emoji = YNABCategory(
            id='cat-emoji', name='🛒 Groceries', group_name='G',
            full_name='G -> 🛒 Groceries',
        )
        categories = self.categories + [cat_with_emoji]
        service._category_by_clean_lower['groceries'] = 'cat-emoji'
        assert service._find_category_id_by_name('Groceries', categories) == 'cat-1'

    def test_no_match(self, service):
        assert service._find_category_id_by_name('NonexistentCategory', self.categories) is None

    def test_empty_name(self, service):
        assert service._find_category_id_by_name('', self.categories) is None

    def test_none_name(self, service):
        assert service._find_category_id_by_name(None, self.categories) is None

    def test_whitespace_name_matches_via_partial(self, service):
        result = service._find_category_id_by_name('   ', self.categories)
        assert result is not None


# ---------------------------------------------------------------------------
# Account lookup maps
# ---------------------------------------------------------------------------

class TestAccountLookupMaps:

    def test_builds_maps(self, service, sample_categories, sample_accounts):
        service._update_llm_parser_data(sample_categories, sample_accounts)
        assert 'Nu Card' in service._account_by_name
        assert 'Bancolombia' in service._account_by_name
        # Closed/deleted accounts should be excluded
        assert 'Old' not in service._account_by_name
        assert 'Gone' not in service._account_by_name

    def test_case_insensitive_map(self, service, sample_categories, sample_accounts):
        service._update_llm_parser_data(sample_categories, sample_accounts)
        assert 'nu card' in service._account_by_name_lower
        assert 'bancolombia' in service._account_by_name_lower


# ---------------------------------------------------------------------------
# _find_account_id_by_name
# ---------------------------------------------------------------------------

class TestFindAccountByName:

    @pytest.fixture(autouse=True)
    def setup_maps(self, service, sample_categories, sample_accounts):
        service._update_llm_parser_data(sample_categories, sample_accounts)

    def test_exact_match(self, service):
        assert service._find_account_id_by_name('Nu Card') == 'acc-1'

    def test_case_insensitive_match(self, service):
        assert service._find_account_id_by_name('nu card') == 'acc-1'
        assert service._find_account_id_by_name('BANCOLOMBIA') == 'acc-2'

    def test_partial_match(self, service):
        assert service._find_account_id_by_name('Nu') == 'acc-1'

    def test_partial_match_reverse(self, service):
        """Longer input containing the account name should match"""
        assert service._find_account_id_by_name('nu card débito') == 'acc-1'

    def test_whitespace_stripped(self, service):
        assert service._find_account_id_by_name('  Nu Card  ') == 'acc-1'

    def test_no_match(self, service):
        assert service._find_account_id_by_name('Nequi') is None

    def test_none_returns_none(self, service):
        assert service._find_account_id_by_name(None) is None

    def test_empty_returns_none(self, service):
        assert service._find_account_id_by_name('') is None


# ---------------------------------------------------------------------------
# _enhance_with_learning
# ---------------------------------------------------------------------------

class TestEnhanceWithLearning:

    def test_high_confidence_not_overridden(self, service, mock_learning_repository, sample_categories):
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.9,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-1'
        mock_learning_repository.predict_category.assert_not_called()

    def test_low_confidence_enhanced(self, service, mock_learning_repository, sample_categories):
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.8)
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.3,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-2'
        assert result.confidence == 0.8

    def test_learning_prediction_lower_confidence_not_used(self, service, mock_learning_repository, sample_categories):
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.2)
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.5,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-1'

    def test_no_prediction_available(self, service, mock_learning_repository, sample_categories):
        mock_learning_repository.predict_category.return_value = None
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.5,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-1'


# ---------------------------------------------------------------------------
# correct_recent_transaction
# ---------------------------------------------------------------------------

class TestCorrectRecentTransaction:

    def test_success(self, service, mock_user_repository, mock_learning_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [
            {'payee': 'McDonalds', 'category_id': 'cat-old', 'amount': 25000},
        ]
        result = service.correct_recent_transaction(TELEGRAM_ID, 0, 'cat-new')
        assert result is True
        mock_learning_repository.record_user_correction.assert_called_once()
        # Verify telegram_id is passed
        call_args = mock_learning_repository.record_user_correction.call_args
        assert call_args[0][0] == TELEGRAM_ID

    def test_user_not_found(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        assert not service.correct_recent_transaction(999, 0, 'cat-new')

    def test_index_out_of_range(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.return_value = []
        assert not service.correct_recent_transaction(TELEGRAM_ID, 5, 'cat-new')

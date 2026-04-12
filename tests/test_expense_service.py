"""Tests for ExpenseService."""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from application.services.expense_service import ExpenseService, _SPECIAL_CHARS_PATTERN
from application.services.budget_query_service import BudgetQueryService
from domain.models.expense import Expense
from domain.models.user import UserConfiguration, UserStatus, YNABCategory, YNABPayee
from domain.time_utils import DEFAULT_TIMEZONE

TELEGRAM_ID = 123456789

_PAYEE_UUID_1 = '550e8400-e29b-41d4-a716-446655440001'
_PAYEE_UUID_2 = '550e8400-e29b-41d4-a716-446655440002'
_PAYEE_UUID_3 = '550e8400-e29b-41d4-a716-446655440003'


@pytest.fixture
def sample_payees():
    return [
        YNABPayee(id=_PAYEE_UUID_1, name='Carulla', deleted=False),
        YNABPayee(id=_PAYEE_UUID_2, name='Café Juan Valdez', deleted=False),
        YNABPayee(id=_PAYEE_UUID_3, name='Uber Eats', deleted=False),
        YNABPayee(id='550e8400-e29b-41d4-a716-446655440099', name='OldPayee', deleted=True),
    ]


@pytest.fixture
def mock_budget_query_service():
    return MagicMock(spec=BudgetQueryService)


@pytest.fixture
def service(mock_user_repository, mock_ynab_factory, mock_learning_repository, mock_llm_parser, mock_budget_query_service, authorized_user):
    authorized_user.ynab_access_token = 'test-token'
    mock_user_repository.find_by_telegram_id.return_value = authorized_user
    return ExpenseService(
        user_repository=mock_user_repository,
        ynab_factory=mock_ynab_factory,
        learning_repository=mock_learning_repository,
        llm_parser=mock_llm_parser,
        budget_query_service=mock_budget_query_service,
    )


@pytest.fixture
def service_with_split(mock_user_repository, mock_ynab_factory, mock_learning_repository, mock_llm_parser, mock_budget_query_service, mock_split_config_repository, authorized_user):
    authorized_user.ynab_access_token = 'test-token'
    mock_user_repository.find_by_telegram_id.return_value = authorized_user
    return ExpenseService(
        user_repository=mock_user_repository,
        ynab_factory=mock_ynab_factory,
        learning_repository=mock_learning_repository,
        llm_parser=mock_llm_parser,
        budget_query_service=mock_budget_query_service,
        split_config_repository=mock_split_config_repository,
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
        mock_llm_parser.parse_expense.assert_called_with(
            'test message',
            timezone_str=DEFAULT_TIMEZONE,
            learning_hints=None,
        )

    def test_records_learning(self, service, mock_learning_repository):
        service.process_expense_message(TELEGRAM_ID, 'test')
        mock_learning_repository.record_successful_transaction.assert_called_once()
        # Verify telegram_id is passed
        call_args = mock_learning_repository.record_successful_transaction.call_args
        assert call_args[0][0] == TELEGRAM_ID
        mock_learning_repository.add_recent_transaction.assert_called_once()
        call_args = mock_learning_repository.add_recent_transaction.call_args
        assert call_args[0][0] == TELEGRAM_ID
        # Verify transaction_id is passed as third argument
        assert call_args[0][2] == 'txn-id-123'

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
        assert 'configurado' in result.error_message.lower()

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
# process_receipt_image
# ---------------------------------------------------------------------------

class TestProcessReceiptImage:

    def test_success(self, service, mock_llm_parser, mock_ynab_repository):
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 45000.0, 'category': 'Restaurants',
            'payee': 'El Corral', 'account': 'Nu Card',
            'memo': 'test', 'confidence': 0.95,
        }
        result = service.process_receipt_image(TELEGRAM_ID, 'base64_data', 'almuerzo')
        assert result.success is True
        assert result.expense.parser_source == 'receipt'
        assert result.expense.amount == Decimal('45000')
        mock_ynab_repository.create_transaction.assert_called_once()

    def test_with_caption(self, service, mock_llm_parser):
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 1000.0, 'category': 'X', 'payee': 'Y', 'memo': 'z', 'confidence': 0.9,
        }
        service.process_receipt_image(TELEGRAM_ID, 'data', 'almuerzo con amigos')
        mock_llm_parser.parse_receipt_image.assert_called_with(
            'data',
            'almuerzo con amigos',
            timezone_str=DEFAULT_TIMEZONE,
            learning_hints=None,
        )

    def test_parse_failure(self, service, mock_llm_parser):
        mock_llm_parser.parse_receipt_image.return_value = None
        result = service.process_receipt_image(TELEGRAM_ID, 'data')
        assert not result.success
        assert 'legible' in result.error_message

    def test_user_not_configured(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.process_receipt_image(999, 'data')
        assert not result.success
        assert 'configurado' in result.error_message.lower()


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

    def test_high_confidence_overridden_if_learning_higher(self, service, mock_learning_repository, sample_categories):
        # Even if LLM is high (0.8), if learning is higher (1.0), it should override
        mock_learning_repository.predict_category.return_value = ('cat-2', 1.0, 5)
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.8,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-2'
        assert result.confidence == 1.0
        assert "aprendido de tus ultimas 5 compras" in result.category_explanation

    def test_low_confidence_defers_to_llm(self, service, mock_learning_repository, sample_categories):
        # Confidence 0.8 < 0.95 threshold — learning should NOT override LLM
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.8, 3)
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.3,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-1'
        assert result.category_explanation is None

    def test_learning_does_not_override_when_category_differs_low_confidence(self, service, mock_learning_repository, sample_categories):
        # Confidence 0.2 < 0.95 threshold — learning should NOT override LLM even if category differs
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.2, 1)
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.5,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-1'
        assert result.category_explanation is None

    def test_equal_confidence_learning_wins_regression(self, service, mock_learning_repository, sample_categories):
        # Regression: when LLM returns confidence 1.0 and learning also has 1.0 but a different
        # category, the old `learning_confidence > expense.confidence` condition (1.0 > 1.0 == False)
        # silently ignored the user correction. Learning must now win.
        mock_learning_repository.predict_category.return_value = ('cat-2', 1.0, 4)
        expense = Expense(
            amount=Decimal('1000'), payee='Mercadona', memo='x',
            category_id='cat-1', confidence=1.0,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-2'
        assert result.confidence == 1.0
        assert "aprendido de tus ultimas 4 compras" in result.category_explanation

    def test_learning_no_op_when_same_category(self, service, mock_learning_repository, sample_categories):
        # When learning agrees with LLM, nothing changes
        mock_learning_repository.predict_category.return_value = ('cat-1', 0.9, 3)
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.8,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-1'
        assert result.category_explanation is None

    def test_no_prediction_available(self, service, mock_learning_repository, sample_categories):
        mock_learning_repository.predict_category.return_value = None
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.5,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-1'

    def test_multi_category_payee_defers_to_llm(self, service, mock_learning_repository, sample_categories):
        # Confidence 0.6 — payee has been used with multiple categories, trust LLM
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.6, 4)
        expense = Expense(
            amount=Decimal('1000'), payee='Mercadona', memo='x',
            category_id='cat-1', confidence=0.85,
        )

        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)

        assert result.category_id == 'cat-1'
        assert result.confidence == 0.85
        assert result.category_explanation is None

    def test_single_category_payee_overrides_llm(self, service, mock_learning_repository, sample_categories):
        # Confidence 1.0 — single-category payee, learning should override LLM
        mock_learning_repository.predict_category.return_value = ('cat-2', 1.0, 7)
        expense = Expense(
            amount=Decimal('1000'), payee='Carrefour', memo='x',
            category_id='cat-1', confidence=0.75,
        )

        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)

        assert result.category_id == 'cat-2'
        assert result.confidence == 1.0
        assert "aprendido de tus ultimas 7 compras en Carrefour" in result.category_explanation

    def test_threshold_boundary_below(self, service, mock_learning_repository, sample_categories):
        # Confidence 0.94 — just below the 0.95 threshold, LLM category must be preserved
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.94, 6)
        expense = Expense(
            amount=Decimal('1000'), payee='MediaMarkt', memo='x',
            category_id='cat-1', confidence=0.80,
        )

        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)

        assert result.category_id == 'cat-1'
        assert result.category_explanation is None

    def test_threshold_boundary_at(self, service, mock_learning_repository, sample_categories):
        # Confidence 0.95 — exactly at threshold, learning must override
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.95, 8)
        expense = Expense(
            amount=Decimal('1000'), payee='Zara', memo='x',
            category_id='cat-1', confidence=0.80,
        )

        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)

        assert result.category_id == 'cat-2'
        assert result.confidence == 0.95
        assert "aprendido de tus ultimas 8 compras en Zara" in result.category_explanation


class TestBuildLearningHints:

    def test_returns_none_when_no_distribution(self, service, mock_learning_repository):
        mock_learning_repository.get_payee_category_distribution.return_value = {}
        assert service._build_learning_hints(TELEGRAM_ID) is None

    def test_formats_distribution(self, service, mock_learning_repository):
        mock_learning_repository.get_payee_category_distribution.return_value = {
            'movistar': [
                {'category_name': 'Internet', 'count': 7, 'percentage': 0.7},
                {'category_name': 'Telefono', 'count': 3, 'percentage': 0.3},
            ],
        }

        hints = service._build_learning_hints(TELEGRAM_ID)

        assert hints == "- movistar: Internet (70%), Telefono (30%)"

    def test_caps_output_to_20_payees(self, service, mock_learning_repository):
        mock_learning_repository.get_payee_category_distribution.return_value = {
            f'payee-{i}': [{'category_name': 'Cat', 'count': i + 1, 'percentage': 1.0}]
            for i in range(25)
        }

        hints = service._build_learning_hints(TELEGRAM_ID)

        assert hints is not None
        assert len(hints.splitlines()) == 20


class TestBuildCategoryExplanation:

    def test_uses_existing_explanation(self, service):
        expense = Expense(amount=Decimal('1'), payee='T', memo='m')
        expense.category_explanation = "Existing"
        assert service._build_category_explanation(expense) == "Existing"

    def test_receipt_source(self, service):
        expense = Expense(amount=Decimal('1'), payee='T', memo='m', parser_source='receipt', confidence=0.95)
        assert service._build_category_explanation(expense) == "detectado del recibo, confianza 95%"

    def test_llm_high_confidence(self, service):
        expense = Expense(amount=Decimal('1'), payee='T', memo='m', parser_source='llm', confidence=0.85)
        assert service._build_category_explanation(expense) == "sugerido por IA, confianza 85%"

    def test_llm_low_confidence(self, service):
        expense = Expense(amount=Decimal('1'), payee='T', memo='m', parser_source='llm', confidence=0.6)
        assert service._build_category_explanation(expense) == "sugerido por IA, confianza 60% - considera verificar"

    def test_fallback(self, service):
        expense = Expense(amount=Decimal('1'), payee='T', memo='m', parser_source='unknown', confidence=0.5)
        assert service._build_category_explanation(expense) == "confianza 50%"


# ---------------------------------------------------------------------------
# undo_last_transaction
# ---------------------------------------------------------------------------

class TestUndoLastTransaction:
    """Tests for ExpenseService.undo_last_transaction()."""

    # Helper: build a recent-transaction dict that is within the 5-minute window
    def _recent_txn(self, minutes_ago=1, has_ynab_id=True, is_today=True):
        now = datetime.now(timezone.utc)
        timestamp = (now - timedelta(minutes=minutes_ago)).isoformat()
        return {
            'payee': 'McDonalds',
            'amount': -25000,
            'category_name': 'Restaurants',
            'category_id': 'cat-2',
            'ynab_transaction_id': 'txn-undo-1' if has_ynab_id else None,
            'timestamp': timestamp,
        }

    def test_success_deletes_and_returns_details(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.delete_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.undo_last_transaction(TELEGRAM_ID)

        assert result is not None
        assert 'error' not in result
        assert result['payee'] == 'McDonalds'
        assert result['amount'] == -25000
        assert result['category_name'] == 'Restaurants'
        mock_ynab_repository.delete_transaction.assert_called_once_with(
            authorized_user.budget_id, 'txn-undo-1'
        )

    def test_success_decrements_learning(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.delete_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        service.undo_last_transaction(TELEGRAM_ID)

        mock_learning_repository.decrement_learning.assert_called_once_with(
            TELEGRAM_ID, 'McDonalds', 'cat-2'
        )

    def test_success_removes_from_recent_transactions(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.delete_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        service.undo_last_transaction(TELEGRAM_ID)

        mock_learning_repository.delete_recent_transaction.assert_called_once_with(
            TELEGRAM_ID, 'txn-undo-1'
        )

    def test_no_recent_transactions_returns_error(
        self, service, mock_user_repository, mock_learning_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = []

        result = service.undo_last_transaction(TELEGRAM_ID)

        assert result is not None
        assert result.get('error') == 'no_recent_transactions'

    def test_missing_ynab_transaction_id_returns_error(
        self, service, mock_user_repository, mock_learning_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [
            self._recent_txn(has_ynab_id=False)
        ]

        result = service.undo_last_transaction(TELEGRAM_ID)

        assert result is not None
        assert result.get('error') == 'no_ynab_transaction_id'

    def test_transaction_too_old_returns_time_window_error(
        self, service, mock_user_repository, mock_learning_repository, authorized_user,
    ):
        """Transaction older than 5 minutes and from a past day should fail."""
        # 10 minutes ago yesterday - outside both windows
        past = (datetime.now(timezone.utc) - timedelta(days=1, minutes=10)).isoformat()
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [{
            'payee': 'McDonalds',
            'amount': -25000,
            'category_name': 'Restaurants',
            'category_id': 'cat-2',
            'ynab_transaction_id': 'txn-old-1',
            'timestamp': past,
        }]

        result = service.undo_last_transaction(TELEGRAM_ID)

        assert result is not None
        assert result.get('error') == 'time_window_exceeded'

    def test_transaction_today_but_older_than_5_min_is_allowed(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        """Transaction from today (but > 5 min ago) should still be undoable."""
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        # 30 minutes ago, but still today in user's timezone
        user_tz = ZoneInfo(authorized_user.timezone)
        now_user = datetime.now(tz=user_tz)
        thirty_min_ago = now_user - timedelta(minutes=30)
        # timestamp in user timezone (so same-day check passes)
        timestamp = thirty_min_ago.isoformat()

        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.delete_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [{
            'payee': 'Carulla',
            'amount': -50000,
            'category_name': 'Groceries',
            'category_id': 'cat-1',
            'ynab_transaction_id': 'txn-today-1',
            'timestamp': timestamp,
        }]

        result = service.undo_last_transaction(TELEGRAM_ID)

        assert result is not None
        assert 'error' not in result
        assert result['payee'] == 'Carulla'

    def test_postgres_datetime_timestamp_is_allowed(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.delete_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [{
            'payee': 'Carulla',
            'amount': -50000,
            'category_name': 'Groceries',
            'category_id': 'cat-1',
            'ynab_transaction_id': 'txn-pg-1',
            'timestamp': datetime.now(timezone.utc) - timedelta(minutes=1),
        }]

        result = service.undo_last_transaction(TELEGRAM_ID)

        assert result is not None
        assert 'error' not in result
        assert result['payee'] == 'Carulla'

    def test_ynab_delete_fails_returns_error(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.delete_transaction.return_value = False
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.undo_last_transaction(TELEGRAM_ID)

        assert result is not None
        assert result.get('error') == 'ynab_delete_failed'
        # Learning and cleanup should NOT be called when YNAB delete fails
        mock_learning_repository.decrement_learning.assert_not_called()
        mock_learning_repository.delete_recent_transaction.assert_not_called()

    def test_user_not_configured_returns_none(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None

        result = service.undo_last_transaction(TELEGRAM_ID)

        assert result is None


# ---------------------------------------------------------------------------
# _find_account_id_from_accounts_list
# ---------------------------------------------------------------------------

class TestFindAccountIdFromAccountsList:
    """Unit tests for the accounts-list-based fuzzy matcher."""

    def _make_accounts(self):
        from domain.models.user import YNABAccount
        return [
            YNABAccount(id='acc-1', name='Nu Card', type='creditCard', balance=0),
            YNABAccount(id='acc-2', name='Bancolombia Ahorros', type='checking', balance=0),
            YNABAccount(id='acc-3', name='Efectivo', type='cash', balance=0),
        ]

    def test_exact_match(self, service):
        accounts = self._make_accounts()
        result = service._find_account_id_from_accounts_list('Nu Card', accounts)
        assert result == 'acc-1'

    def test_case_insensitive_match(self, service):
        accounts = self._make_accounts()
        result = service._find_account_id_from_accounts_list('nu card', accounts)
        assert result == 'acc-1'

    def test_partial_match_input_in_account_name(self, service):
        accounts = self._make_accounts()
        result = service._find_account_id_from_accounts_list('Bancolombia', accounts)
        assert result == 'acc-2'

    def test_partial_match_account_name_in_input(self, service):
        accounts = self._make_accounts()
        result = service._find_account_id_from_accounts_list('mi cuenta Efectivo aqui', accounts)
        assert result == 'acc-3'

    def test_no_match_returns_none(self, service):
        accounts = self._make_accounts()
        result = service._find_account_id_from_accounts_list('Davivienda', accounts)
        assert result is None

    def test_empty_input_returns_none(self, service):
        accounts = self._make_accounts()
        assert service._find_account_id_from_accounts_list('', accounts) is None

    def test_empty_accounts_returns_none(self, service):
        assert service._find_account_id_from_accounts_list('Nu Card', []) is None


# ---------------------------------------------------------------------------
# edit_last_transaction
# ---------------------------------------------------------------------------

class TestEditLastTransaction:
    """Tests for ExpenseService.edit_last_transaction()."""

    def _recent_txn(self, minutes_ago=1, has_ynab_id=True):
        now = datetime.now(timezone.utc)
        timestamp = (now - timedelta(minutes=minutes_ago)).isoformat()
        return {
            'payee': 'McDonalds',
            'amount': -25000,
            'category_name': 'Restaurants',
            'category_id': 'cat-2',
            'ynab_transaction_id': 'txn-edit-1' if has_ynab_id else None,
            'timestamp': timestamp,
        }

    # --- amount edit ---

    def test_edit_amount_only(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, new_amount=Decimal('30'))

        assert result is not None
        assert 'error' not in result
        assert 'amount' in result['changes']
        assert result['changes']['amount']['new'] == 30.0
        mock_ynab_repository.update_transaction.assert_called_once_with(
            authorized_user.budget_id, 'txn-edit-1', {'amount': -30000}
        )
        mock_learning_repository.record_user_correction.assert_not_called()
        mock_learning_repository.update_recent_transaction.assert_called_once_with(
            TELEGRAM_ID,
            'txn-edit-1',
            payee=None,
            amount=-30.0,
            category_id=None,
            category_name=None,
        )

    # --- payee edit ---

    def test_edit_payee_only(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, new_payee="Burger King")

        assert result is not None
        assert 'error' not in result
        assert result['changes']['payee']['new'] == 'Burger King'
        mock_ynab_repository.update_transaction.assert_called_once()
        fields_used = mock_ynab_repository.update_transaction.call_args[0][2]
        assert fields_used['payee_name'] == 'Burger King'
        mock_learning_repository.record_user_correction.assert_not_called()

    # --- category edit (with fuzzy match + learning update) ---

    def test_edit_category_only_with_learning(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, new_category='Groceries')

        assert result is not None
        assert 'error' not in result
        assert result['changes']['category']['new'] == 'Groceries'
        fields_used = mock_ynab_repository.update_transaction.call_args[0][2]
        assert fields_used['category_id'] == 'cat-1'
        # Learning should be updated
        mock_learning_repository.record_user_correction.assert_called_once()
        call_args = mock_learning_repository.record_user_correction.call_args[0]
        assert call_args[0] == TELEGRAM_ID
        assert call_args[1] == 'McDonalds'
        assert call_args[2] == 'cat-2'   # old category
        assert call_args[3] == 'cat-1'   # new category id
        mock_learning_repository.update_recent_transaction.assert_called_once_with(
            TELEGRAM_ID,
            'txn-edit-1',
            payee=None,
            amount=None,
            category_id='cat-1',
            category_name='Groceries',
        )

    def test_edit_category_fuzzy_match(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        """Partial category name should still resolve."""
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = True
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, new_category='Restau')  # partial

        assert result is not None
        assert 'error' not in result
        assert 'category' in result['changes']

    def test_edit_category_not_found_returns_error(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, new_category='NonExistentXYZ')

        assert result is not None
        assert result.get('error') == 'category_not_found'
        assert 'NonExistentXYZ' in result.get('message', '')
        mock_ynab_repository.update_transaction.assert_not_called()

    # --- account edit ---

    def test_edit_account_only(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user, sample_accounts,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = True
        mock_ynab_repository.get_accounts.return_value = sample_accounts
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, new_account='Bancolombia')

        assert result is not None
        assert 'error' not in result
        assert 'account' in result['changes']
        fields_used = mock_ynab_repository.update_transaction.call_args[0][2]
        assert fields_used['account_id'] == 'acc-2'
        mock_learning_repository.record_user_correction.assert_not_called()

    def test_edit_account_not_found_returns_error(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user, sample_accounts,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.get_accounts.return_value = sample_accounts
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, new_account='CuentaInexistente')

        assert result is not None
        assert result.get('error') == 'account_not_found'
        assert 'CuentaInexistente' in result.get('message', '')
        mock_ynab_repository.update_transaction.assert_not_called()

    # --- multiple fields ---

    def test_edit_multiple_fields(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user, sample_accounts,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = True
        mock_ynab_repository.get_accounts.return_value = sample_accounts
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(
            TELEGRAM_ID,
            new_amount=Decimal('50'),
            new_payee='Burger King',
            new_category='Groceries',
            new_account='Nu Card',
        )

        assert result is not None
        assert 'error' not in result
        fields_used = mock_ynab_repository.update_transaction.call_args[0][2]
        assert 'amount' in fields_used
        assert 'payee_name' in fields_used
        assert 'category_id' in fields_used
        assert 'account_id' in fields_used
        mock_learning_repository.update_recent_transaction.assert_called_once_with(
            TELEGRAM_ID,
            'txn-edit-1',
            payee='Burger King',
            amount=-50.0,
            category_id='cat-1',
            category_name='Groceries',
        )

    def test_undo_returns_updated_cached_fields_after_edit(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = True
        mock_ynab_repository.delete_transaction.return_value = True
        original = self._recent_txn()
        updated = {
            **original,
            'amount': -30000,
            'category_id': 'cat-1',
            'category_name': 'Groceries',
        }
        mock_learning_repository.get_recent_transactions.side_effect = [[original], [updated]]

        edit_result = service.edit_last_transaction(TELEGRAM_ID, new_amount=Decimal('30'), new_category='Groceries')
        undo_result = service.undo_last_transaction(TELEGRAM_ID)

        assert edit_result is not None
        assert undo_result is not None
        assert undo_result['amount'] == -30000
        assert undo_result['category_name'] == 'Groceries'

    # --- transaction_index ---

    def test_edit_with_transaction_index(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = True
        txn0 = self._recent_txn()
        txn1 = {**self._recent_txn(), 'ynab_transaction_id': 'txn-edit-2', 'payee': 'Carulla'}
        mock_learning_repository.get_recent_transactions.return_value = [txn0, txn1]

        result = service.edit_last_transaction(TELEGRAM_ID, transaction_index=1, new_amount=Decimal('10'))

        assert result is not None
        assert 'error' not in result
        # Should have targeted the second transaction
        mock_ynab_repository.update_transaction.assert_called_once_with(
            authorized_user.budget_id, 'txn-edit-2', {'amount': -10000}
        )

    def test_transaction_index_out_of_range(
        self, service, mock_user_repository, mock_learning_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, transaction_index=5, new_amount=Decimal('10'))

        assert result is not None
        assert result.get('error') == 'index_out_of_range'

    # --- time window ---

    def test_transaction_too_old_returns_time_window_error(
        self, service, mock_user_repository, mock_learning_repository, authorized_user,
    ):
        past = (datetime.now(timezone.utc) - timedelta(days=1, minutes=10)).isoformat()
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [{
            'payee': 'McDonalds',
            'amount': -25000,
            'category_name': 'Restaurants',
            'category_id': 'cat-2',
            'ynab_transaction_id': 'txn-old',
            'timestamp': past,
        }]

        result = service.edit_last_transaction(TELEGRAM_ID, new_amount=Decimal('10'))

        assert result is not None
        assert result.get('error') == 'time_window_exceeded'

    # --- no recent transactions ---

    def test_no_recent_transactions(
        self, service, mock_user_repository, mock_learning_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = []

        result = service.edit_last_transaction(TELEGRAM_ID, new_amount=Decimal('10'))

        assert result is not None
        assert result.get('error') == 'index_out_of_range'

    # --- YNAB update fails ---

    def test_ynab_update_fails_returns_error(
        self, service, mock_user_repository, mock_learning_repository,
        mock_ynab_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.update_transaction.return_value = False
        mock_learning_repository.get_recent_transactions.return_value = [self._recent_txn()]

        result = service.edit_last_transaction(TELEGRAM_ID, new_amount=Decimal('10'))

        assert result is not None
        assert result.get('error') == 'ynab_update_failed'
        mock_learning_repository.record_user_correction.assert_not_called()

    # --- user not configured ---

    def test_user_not_configured_returns_none(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None

        result = service.edit_last_transaction(TELEGRAM_ID, new_amount=Decimal('10'))

        assert result is None

    # --- missing ynab_transaction_id ---

    def test_missing_ynab_transaction_id_returns_error(
        self, service, mock_user_repository, mock_learning_repository, authorized_user,
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [
            self._recent_txn(has_ynab_id=False)
        ]

        result = service.edit_last_transaction(TELEGRAM_ID, new_amount=Decimal('10'))

        assert result is not None
        assert result.get('error') == 'no_ynab_transaction_id'


# ---------------------------------------------------------------------------
# process_message - routing
# ---------------------------------------------------------------------------

class TestProcessMessage:

    def test_routes_expense(self, service, mock_llm_parser):
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': '25 lucas almuerzo',
            'confidence': 0.85,
        }
        result = service.process_message(TELEGRAM_ID, '25 lucas almuerzo')
        assert result.intent == 'expense'
        assert result.expense_result is not None
        assert result.expense_result.success is True

    def test_routes_query(self, service, mock_llm_parser, mock_budget_query_service):
        from domain.models.budget_query import BudgetQueryResult
        mock_llm_parser.parse_message.return_value = {
            'intent': 'query',
            'query_type': 'category_balance',
            'query_target': 'Groceries',
            'confidence': 0.9,
        }
        mock_budget_query_service.execute_query.return_value = BudgetQueryResult.success_result(
            'category_balance', {'name': 'Groceries', 'balance': 300000},
        )
        result = service.process_message(TELEGRAM_ID, '¿Cuánto me queda en Groceries?')
        assert result.intent == 'query'
        assert result.query_result is not None
        assert result.query_result.success is True
        mock_budget_query_service.execute_query.assert_called_once()

    def test_parse_failure(self, service, mock_llm_parser):
        mock_llm_parser.parse_message.return_value = None
        result = service.process_message(TELEGRAM_ID, 'nonsense')
        assert result.intent == 'expense'
        assert result.expense_result.success is False

    def test_message_too_long(self, service):
        result = service.process_message(TELEGRAM_ID, 'x' * 501)
        assert result.intent == 'expense'
        assert result.expense_result.success is False
        assert 'largo' in result.expense_result.error_message.lower()

    def test_user_not_configured(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.process_message(999, 'test')
        assert result.intent == 'expense'
        assert result.expense_result.success is False

    def test_routes_shared_expense(self, service_with_split, mock_llm_parser, mock_ynab_repository):
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo mitad con Juan',
            'confidence': 0.85,
            'person': 'Juan',
            'proportion': '1/2',
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'almuerzo mitad 50k con Juan')
        assert result.intent == 'shared_expense'
        assert result.expense_result.success is True
        assert result.expense_result.expense.is_split is True
        assert result.expense_result.expense.split_person == 'Juan'
        assert result.expense_result.expense.split_category_id == 'cat-123'
        assert result.expense_result.expense.split_category_name == 'Gastos Compartidos'

    def test_passes_learning_hints_to_parse_message(self, service, mock_llm_parser, mock_learning_repository):
        mock_learning_repository.get_payee_category_distribution.return_value = {
            'movistar': [{'category_name': 'Internet', 'count': 2, 'percentage': 1.0}],
        }
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': '25 lucas almuerzo',
            'confidence': 0.85,
        }

        service.process_message(TELEGRAM_ID, '25 lucas almuerzo')

        mock_llm_parser.parse_message.assert_called_with(
            '25 lucas almuerzo',
            timezone_str=DEFAULT_TIMEZONE,
            learning_hints='- movistar: Internet (100%)',
        )

    def test_shared_expense_custom_proportion(self, service_with_split, mock_llm_parser):
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 90000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.85,
            'person': 'Juan',
            'proportion': '1/3',
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'test')
        assert result.expense_result.success is True
        assert result.expense_result.expense.split_proportion == Decimal('1') / Decimal('3')

    def test_shared_expense_person_not_found(self, service_with_split, mock_llm_parser, mock_split_config_repository):
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.85,
            'person': 'Pedro',
            'proportion': None,
        }
        mock_split_config_repository.find_split_group_by_alias.return_value = None
        result = service_with_split.process_message(TELEGRAM_ID, 'test')
        assert result.intent == 'shared_expense'
        assert result.expense_result.success is False
        assert 'Pedro' in result.expense_result.error_message

    def test_shared_expense_no_split_config(self, service, mock_llm_parser):
        """Service without split_config_repository returns error."""
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.85,
            'person': 'Juan',
            'proportion': None,
        }
        result = service.process_message(TELEGRAM_ID, 'test')
        assert result.intent == 'shared_expense'
        assert result.expense_result.success is False
        assert '/splitwise' in result.expense_result.error_message

    def test_other_paid_uses_shared_account(self, service_with_split, mock_llm_parser, mock_ynab_repository, mock_split_config_repository, sample_shared_account):
        """When payer='other', the shared account must be used for the transaction."""
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Groceries',
            'payee': 'Carulla',
            'account': None,
            'memo': 'Eli gastó 50k en carulla conmigo',
            'confidence': 0.9,
            'person': 'Eli',
            'proportion': '1/2',
            'payer': 'other',
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'Eli gastó 50k en carulla conmigo')
        assert result.intent == 'shared_expense'
        assert result.expense_result.success is True
        expense = result.expense_result.expense
        assert expense.payer == 'other'
        assert expense.account_id == sample_shared_account.account_id
        assert expense.account_name == sample_shared_account.account_name

    def test_other_paid_no_shared_account_returns_error(self, service_with_split, mock_llm_parser, mock_split_config_repository):
        """When payer='other' and no shared account configured, return an error."""
        mock_split_config_repository.get_shared_account.return_value = None
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Groceries',
            'payee': 'Carulla',
            'account': None,
            'memo': 'Eli gastó 50k en carulla conmigo',
            'confidence': 0.9,
            'person': 'Eli',
            'proportion': '1/2',
            'payer': 'other',
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'Eli gastó 50k en carulla conmigo')
        assert result.expense_result.success is False
        assert 'compartida' in result.expense_result.error_message

    def test_user_paid_split_uses_default_account(self, service_with_split, mock_llm_parser, mock_ynab_repository, authorized_user):
        """When payer='user' (default), fall back to default account as before."""
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo mitad con Juan',
            'confidence': 0.85,
            'person': 'Juan',
            'proportion': '1/2',
            'payer': 'user',
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'almuerzo mitad con Juan')
        assert result.expense_result.success is True
        expense = result.expense_result.expense
        assert expense.payer == 'user'
        assert expense.account_id == authorized_user.default_account_id

    def test_shared_expense_split_amount_sets_fixed_amount(self, service_with_split, mock_llm_parser):
        """When LLM returns split_amount, expense.split_fixed_amount is set to that value."""
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 60000.0,
            'category': 'Restaurants',
            'payee': 'El Corral',
            'account': None,
            'memo': 'almuerzo, 36700 son por Juan',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': None,
            'payer': 'user',
            'split_amount': 36700,
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'almuerzo 60k, 36700 son por Juan')
        assert result.expense_result.success is True
        expense = result.expense_result.expense
        assert expense.split_fixed_amount == Decimal('36700')

    def test_shared_expense_split_amount_null_leaves_fixed_amount_none(self, service_with_split, mock_llm_parser):
        """When split_amount is null in LLM response, split_fixed_amount remains None."""
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': 'Crepes',
            'account': None,
            'memo': 'almuerzo mitad con Juan',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': '1/2',
            'payer': 'user',
            'split_amount': None,
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'almuerzo mitad con Juan')
        assert result.expense_result.success is True
        assert result.expense_result.expense.split_fixed_amount is None

    def test_shared_expense_missing_split_amount_leaves_fixed_amount_none(self, service_with_split, mock_llm_parser):
        """When split_amount is absent from LLM response, split_fixed_amount remains None."""
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': 'Crepes',
            'account': None,
            'memo': 'almuerzo mitad con Juan',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': '1/2',
            'payer': 'user',
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'almuerzo mitad con Juan')
        assert result.expense_result.success is True
        assert result.expense_result.expense.split_fixed_amount is None


# ---------------------------------------------------------------------------
# _parse_proportion
# ---------------------------------------------------------------------------

class TestParseProportion:

    def test_none_defaults_to_half(self):
        assert ExpenseService._parse_proportion(None) == Decimal('0.5')

    def test_fraction_half(self):
        assert ExpenseService._parse_proportion('1/2') == Decimal('0.5')

    def test_fraction_third(self):
        result = ExpenseService._parse_proportion('1/3')
        assert abs(result - Decimal('0.333333')) < Decimal('0.001')

    def test_decimal_string(self):
        assert ExpenseService._parse_proportion('0.25') == Decimal('0.25')

    def test_invalid_falls_back(self):
        assert ExpenseService._parse_proportion('abc') == Decimal('0.5')

    def test_empty_string_falls_back(self):
        assert ExpenseService._parse_proportion('') == Decimal('0.5')


# ---------------------------------------------------------------------------
# Date propagation from parsed result to Expense
# ---------------------------------------------------------------------------

class TestDatePropagation:

    def test_valid_date_string_sets_expense_date(self, service, mock_llm_parser):
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'ayer almuerzo',
            'date': '2026-03-17',
            'confidence': 0.85,
        }
        result = service.process_message(TELEGRAM_ID, 'ayer almuerzo 25 lucas')
        assert result.expense_result.success is True
        assert result.expense_result.expense.date == datetime(2026, 3, 17)

    def test_null_date_uses_user_timezone(self, service, mock_llm_parser):
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo',
            'date': None,
            'confidence': 0.85,
        }
        result = service.process_message(TELEGRAM_ID, 'almuerzo 25 lucas')
        assert result.expense_result.success is True
        # date should be timezone-aware and approximately now
        expense_date = result.expense_result.expense.date
        assert expense_date is not None
        assert expense_date.tzinfo is not None

    def test_invalid_date_string_uses_user_timezone(self, service, mock_llm_parser):
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo',
            'date': 'invalid-date',
            'confidence': 0.85,
        }
        result = service.process_message(TELEGRAM_ID, 'almuerzo 25 lucas')
        assert result.expense_result.success is True
        expense_date = result.expense_result.expense.date
        assert expense_date is not None
        assert expense_date.tzinfo is not None

    def test_date_propagated_for_shared_expense(self, service_with_split, mock_llm_parser):
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'ayer almuerzo con Juan',
            'date': '2026-03-15',
            'confidence': 0.85,
            'person': 'Juan',
            'proportion': '1/2',
            'payer': 'user',
        }
        result = service_with_split.process_message(TELEGRAM_ID, 'ayer almuerzo mitad con Juan')
        assert result.expense_result.success is True
        assert result.expense_result.expense.date == datetime(2026, 3, 15)

    def test_missing_date_key_uses_user_timezone(self, service, mock_llm_parser):
        """When the parsed result doesn't have a 'date' key at all."""
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo',
            'confidence': 0.85,
        }
        result = service.process_message(TELEGRAM_ID, 'almuerzo 25 lucas')
        assert result.expense_result.success is True
        expense_date = result.expense_result.expense.date
        assert expense_date is not None
        assert expense_date.tzinfo is not None


# ---------------------------------------------------------------------------
# Timezone wiring
# ---------------------------------------------------------------------------

class TestTimezoneWiring:

    def test_process_message_passes_timezone_to_parser(self, service, mock_llm_parser, authorized_user):
        authorized_user.timezone = 'America/Bogota'
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo',
            'confidence': 0.85,
        }
        service.process_message(TELEGRAM_ID, 'almuerzo 25 lucas')
        mock_llm_parser.parse_message.assert_called_with(
            'almuerzo 25 lucas',
            timezone_str='America/Bogota',
            learning_hints=None,
        )

    def test_build_expense_uses_user_timezone_for_default_date(self, service, mock_llm_parser, authorized_user):
        authorized_user.timezone = 'America/Bogota'
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo',
            'date': None,
            'confidence': 0.85,
        }
        result = service.process_message(TELEGRAM_ID, 'almuerzo 25 lucas')
        assert result.expense_result.success is True
        expense_date = result.expense_result.expense.date
        assert expense_date is not None
        assert expense_date.tzinfo is not None
        # The timezone name should contain Bogota
        assert 'Bogota' in str(expense_date.tzinfo) or expense_date.utcoffset() is not None

    def test_process_expense_message_passes_timezone_to_parser(self, service, mock_llm_parser, authorized_user):
        authorized_user.timezone = 'US/Eastern'
        service.process_expense_message(TELEGRAM_ID, 'test message')
        mock_llm_parser.parse_expense.assert_called_with(
            'test message',
            timezone_str='US/Eastern',
            learning_hints=None,
        )

    def test_process_receipt_image_passes_timezone_to_parser(self, service, mock_llm_parser, authorized_user):
        authorized_user.timezone = 'Europe/Madrid'
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 1000.0, 'category': 'X', 'payee': 'Y', 'memo': 'z', 'confidence': 0.9,
        }
        service.process_receipt_image(TELEGRAM_ID, 'data', 'caption')
        mock_llm_parser.parse_receipt_image.assert_called_with(
            'data',
            'caption',
            timezone_str='Europe/Madrid',
            learning_hints=None,
        )


# ---------------------------------------------------------------------------
# _normalize_payee_name
# ---------------------------------------------------------------------------

class TestNormalizePayeeName:

    def test_strips_accents(self):
        assert ExpenseService._normalize_payee_name('Café') == 'cafe'

    def test_lowercases(self):
        assert ExpenseService._normalize_payee_name('CARULLA') == 'carulla'

    def test_removes_punctuation(self):
        result = ExpenseService._normalize_payee_name("McDonald's")
        assert "'" not in result
        assert 'mcdonalds' in result

    def test_strips_whitespace(self):
        assert ExpenseService._normalize_payee_name('  Rappi  ') == 'rappi'

    def test_multiple_accents(self):
        result = ExpenseService._normalize_payee_name('Café Ñoño')
        assert result == 'cafe nono'

    def test_empty_string(self):
        assert ExpenseService._normalize_payee_name('') == ''


# ---------------------------------------------------------------------------
# _match_payee - individual tiers
# ---------------------------------------------------------------------------

class TestMatchPayee:

    @pytest.fixture(autouse=True)
    def setup_payee_maps(self, service, sample_categories, sample_accounts, sample_payees):
        service._update_llm_parser_data(sample_categories, sample_accounts, sample_payees)

    def test_exact_match(self, service):
        result = service._match_payee('Carulla')
        assert result is not None
        assert result[0] == _PAYEE_UUID_1
        assert result[1] == 'Carulla'

    def test_case_insensitive_match(self, service):
        result = service._match_payee('carulla')
        assert result is not None
        assert result[0] == _PAYEE_UUID_1

    def test_case_insensitive_match_uppercase(self, service):
        result = service._match_payee('CARULLA')
        assert result is not None
        assert result[0] == _PAYEE_UUID_1

    def test_normalized_match_strips_accent(self, service):
        # 'cafe' should match 'Café Juan Valdez' via normalized map
        result = service._match_payee('Cafe Juan Valdez')
        assert result is not None
        assert result[0] == _PAYEE_UUID_2

    def test_containment_match_input_shorter(self, service):
        # 'uber eats delivery' contains 'uber eats' (name_lower in payee_lower)
        result = service._match_payee('uber eats delivery')
        assert result is not None
        assert result[0] == _PAYEE_UUID_3

    def test_containment_match_input_is_prefix(self, service):
        # 'Uber' is contained in 'uber eats' (payee_lower in name_lower)
        result = service._match_payee('Uber')
        assert result is not None
        assert result[0] == _PAYEE_UUID_3

    def test_no_match_returns_none(self, service):
        result = service._match_payee('NewUnknownPlace')
        assert result is None

    def test_deleted_payee_not_matched(self, service):
        # 'OldPayee' was added with deleted=True, so it must not appear
        result = service._match_payee('OldPayee')
        assert result is None

    def test_none_input_returns_none(self, service):
        result = service._match_payee(None)
        assert result is None

    def test_empty_string_returns_none(self, service):
        result = service._match_payee('')
        assert result is None

    def test_whitespace_only_returns_none(self, service):
        result = service._match_payee('   ')
        assert result is None


# ---------------------------------------------------------------------------
# _match_payee with empty maps
# ---------------------------------------------------------------------------

class TestMatchPayeeEmptyMaps:

    def test_returns_none_when_maps_not_populated(self, service):
        # Service has empty payee maps by default (no _update_llm_parser_data call)
        result = service._match_payee('Carulla')
        assert result is None

    def test_returns_none_when_payees_param_is_none(self, service, sample_categories, sample_accounts):
        # Called with payees=None: maps stay empty
        service._update_llm_parser_data(sample_categories, sample_accounts, None)
        result = service._match_payee('Carulla')
        assert result is None


# ---------------------------------------------------------------------------
# Payee matching integrates into expense building flow
# ---------------------------------------------------------------------------

class TestPayeeMatchingInExpenseFlow:

    def test_matched_payee_sets_payee_id_and_canonical_name(self, service, sample_categories, sample_accounts, sample_payees, mock_ynab_repository):
        mock_ynab_repository.get_payees.return_value = sample_payees
        service._update_llm_parser_data(sample_categories, sample_accounts, sample_payees)

        # Build an expense whose payee matches 'Carulla' exactly
        parsed = {
            'amount': 25000.0,
            'category': 'Groceries',
            'payee': 'Carulla',
            'account': None,
            'memo': 'mercado',
            'confidence': 0.9,
        }
        active_categories = [c for c in sample_categories if not c.deleted and not c.hidden]
        expense = service._build_expense_from_parsed(parsed, 'mercado', active_categories)

        assert expense is not None
        assert expense.payee_id == _PAYEE_UUID_1
        assert expense.payee == 'Carulla'

    def test_unmatched_payee_leaves_payee_id_none(self, service, sample_categories, sample_accounts, sample_payees):
        service._update_llm_parser_data(sample_categories, sample_accounts, sample_payees)

        parsed = {
            'amount': 10000.0,
            'category': 'Groceries',
            'payee': 'TotallyNewStore',
            'account': None,
            'memo': 'compra',
            'confidence': 0.9,
        }
        active_categories = [c for c in sample_categories if not c.deleted and not c.hidden]
        expense = service._build_expense_from_parsed(parsed, 'compra', active_categories)

        assert expense is not None
        assert expense.payee_id is None
        assert expense.payee == 'TotallyNewStore'

    def test_normalized_payee_match_updates_canonical_name(self, service, sample_categories, sample_accounts, sample_payees):
        service._update_llm_parser_data(sample_categories, sample_accounts, sample_payees)

        # 'Cafe Juan Valdez' (no accent) should normalize-match 'Café Juan Valdez'
        parsed = {
            'amount': 8000.0,
            'category': 'Restaurants',
            'payee': 'Cafe Juan Valdez',
            'account': None,
            'memo': 'tinto',
            'confidence': 0.85,
        }
        active_categories = [c for c in sample_categories if not c.deleted and not c.hidden]
        expense = service._build_expense_from_parsed(parsed, 'tinto', active_categories)

        assert expense is not None
        assert expense.payee_id == _PAYEE_UUID_2
        # canonical name replaces the LLM-returned name
        assert expense.payee == 'Café Juan Valdez'

    def test_process_message_includes_payee_id_in_transaction(self, service, mock_ynab_repository, mock_llm_parser, sample_payees):
        mock_ynab_repository.get_payees.return_value = sample_payees
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Groceries',
            'payee': 'Carulla',
            'account': None,
            'memo': 'mercado',
            'confidence': 0.9,
        }
        result = service.process_message(TELEGRAM_ID, 'mercado carulla 25k')
        assert result.expense_result.success is True
        assert result.expense_result.expense.payee_id == _PAYEE_UUID_1


# ---------------------------------------------------------------------------
# _update_llm_parser_data with payees
# ---------------------------------------------------------------------------

class TestUpdateLlmParserDataWithPayees:

    def test_builds_payee_maps_from_active_payees(self, service, sample_categories, sample_accounts, sample_payees):
        service._update_llm_parser_data(sample_categories, sample_accounts, sample_payees)
        # Active payees should be in all three maps
        assert 'Carulla' in service._payee_by_name
        assert 'carulla' in service._payee_by_name_lower
        assert 'carulla' in service._payee_by_name_normalized

    def test_deleted_payees_excluded_from_maps(self, service, sample_categories, sample_accounts, sample_payees):
        service._update_llm_parser_data(sample_categories, sample_accounts, sample_payees)
        assert 'OldPayee' not in service._payee_by_name
        assert 'oldpayee' not in service._payee_by_name_lower

    def test_normalized_map_strips_accents(self, service, sample_categories, sample_accounts, sample_payees):
        service._update_llm_parser_data(sample_categories, sample_accounts, sample_payees)
        # 'Café Juan Valdez' normalizes to 'cafe juan valdez'
        assert 'cafe juan valdez' in service._payee_by_name_normalized

    def test_no_payees_param_leaves_maps_unchanged(self, service, sample_categories, sample_accounts):
        # Pre-populate maps, then call without payees — maps must not be cleared
        service._payee_by_name = {'Pre': ('id-pre', 'Pre')}
        service._update_llm_parser_data(sample_categories, sample_accounts, None)
        assert 'Pre' in service._payee_by_name

    def test_payee_map_entry_tuple_is_id_and_name(self, service, sample_categories, sample_accounts, sample_payees):
        service._update_llm_parser_data(sample_categories, sample_accounts, sample_payees)
        entry = service._payee_by_name['Carulla']
        assert entry == (_PAYEE_UUID_1, 'Carulla')


# ---------------------------------------------------------------------------
# Error results use user_message (Spanish), not raw str(e)
# ---------------------------------------------------------------------------

class TestErrorResultsUseUserMessage:
    """Verify all three methods return user_message (Spanish) in error results."""

    def test_process_message_ynab_exception_returns_spanish_user_message(
        self, service, mock_user_repository, authorized_user, mock_llm_parser
    ):
        from domain.exceptions import YNABApiException
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.side_effect = YNABApiException(
            "Internal server error", status_code=500
        )
        result = service.process_message(TELEGRAM_ID, 'test')
        assert result.expense_result.success is False
        assert 'YNAB API error' not in result.expense_result.error_message
        assert 'YNAB' in result.expense_result.error_message or 'problema' in result.expense_result.error_message

    def test_process_message_user_not_configured_returns_spanish_user_message(
        self, service, mock_user_repository
    ):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.process_message(TELEGRAM_ID, 'test')
        assert result.expense_result.success is False
        assert 'not configured' not in result.expense_result.error_message
        assert 'configurado' in result.expense_result.error_message.lower()

    def test_process_message_oauth_exception_returns_spanish_user_message(
        self, service, mock_user_repository, authorized_user, mock_llm_parser
    ):
        from domain.exceptions import OAuthException
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.side_effect = OAuthException("token invalid")
        result = service.process_message(TELEGRAM_ID, 'test')
        assert result.expense_result.success is False
        assert 'autenticación' in result.expense_result.error_message.lower() or 'connect' in result.expense_result.error_message.lower()

    def test_process_expense_message_ynab_exception_returns_spanish_user_message(
        self, service, mock_ynab_repository
    ):
        mock_ynab_repository.create_transaction.return_value = None
        result = service.process_expense_message(TELEGRAM_ID, 'test')
        assert result.success is False
        assert 'Failed to create transaction' not in result.error_message
        assert 'YNAB' in result.error_message or 'problema' in result.error_message

    def test_process_expense_message_user_not_configured_returns_spanish_user_message(
        self, service, mock_user_repository
    ):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.process_expense_message(999, 'test')
        assert result.success is False
        assert 'not configured' not in result.error_message
        assert 'configurado' in result.error_message.lower()

    def test_process_receipt_image_ynab_exception_returns_spanish_user_message(
        self, service, mock_ynab_repository, mock_llm_parser
    ):
        mock_ynab_repository.create_transaction.return_value = None
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 45000.0, 'category': 'Restaurants',
            'payee': 'El Corral', 'account': None,
            'memo': 'test', 'confidence': 0.95,
        }
        result = service.process_receipt_image(TELEGRAM_ID, 'base64_data')
        assert result.success is False
        assert 'Failed to create transaction' not in result.error_message
        assert 'YNAB' in result.error_message or 'problema' in result.error_message

    def test_process_receipt_image_user_not_configured_returns_spanish_user_message(
        self, service, mock_user_repository
    ):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.process_receipt_image(999, 'data')
        assert result.success is False
        assert 'not configured' not in result.error_message
        assert 'configurado' in result.error_message.lower()

    def test_logger_still_logs_technical_message(self, service, mock_user_repository):
        """logger.error must contain the technical str(e), not just the user_message."""
        import logging

        class _Capture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        capture = _Capture()
        target_logger = logging.getLogger('application.services.expense_service')
        target_logger.addHandler(capture)
        try:
            mock_user_repository.find_by_telegram_id.return_value = None
            service.process_expense_message(999, 'test')
        finally:
            target_logger.removeHandler(capture)

        assert any('not configured' in r.getMessage().lower() for r in capture.records)


# ---------------------------------------------------------------------------
# prepare_expense / commit_expense (two-phase pipeline)
# ---------------------------------------------------------------------------

class TestPrepareExpense:
    """Tests for the prepare phase: no YNAB transaction is created."""

    def test_returns_dict_with_required_keys(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.prepare_expense(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        from domain.models.expense import PreparedExpense
        assert isinstance(result, PreparedExpense)

    def test_no_ynab_transaction_created(self, service, mock_user_repository, mock_ynab_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service.prepare_expense(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        mock_ynab_repository.create_transaction.assert_not_called()

    def test_no_learning_recorded(self, service, mock_user_repository, mock_learning_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service.prepare_expense(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        mock_learning_repository.record_successful_transaction.assert_not_called()
        mock_learning_repository.add_recent_transaction.assert_not_called()

    def test_expense_result_has_no_transaction_id(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.prepare_expense(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        assert result.expense_result.transaction_id is None

    def test_expense_object_is_valid(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.prepare_expense(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        expense = result.expense
        assert expense.payee is not None
        assert expense.amount is not None

    def test_intent_is_expense(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.prepare_expense(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        assert result.intent == 'expense'

    def test_budget_id_matches_user_config(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.prepare_expense(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        assert result.budget_id == authorized_user.budget_id

    def test_raises_on_user_not_configured(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        from domain.exceptions import UserNotConfiguredException
        with pytest.raises(UserNotConfiguredException):
            service.prepare_expense(999, 'test message')

    def test_raises_on_parse_failure(self, service, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = None
        from domain.exceptions import ExpenseParsingException
        with pytest.raises(ExpenseParsingException):
            service.prepare_expense(TELEGRAM_ID, 'nonsense')

    def test_raises_on_message_too_long(self, service, mock_user_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        from domain.exceptions import ExpenseParsingException
        with pytest.raises(ExpenseParsingException):
            service.prepare_expense(TELEGRAM_ID, 'x' * 501)

    def test_default_account_applied_when_missing(self, service, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        # Parser returns no account
        mock_llm_parser.parse_message.return_value = {
            'intent': 'expense',
            'amount': 15000.0,
            'category': 'Groceries',
            'payee': 'Carulla',
            'account': None,
            'memo': 'test',
            'confidence': 0.9,
        }
        result = service.prepare_expense(TELEGRAM_ID, 'Carulla 15k')
        assert result.account_id == authorized_user.default_account_id

    def test_passes_learning_hints_to_parse_message(self, service, mock_user_repository, mock_learning_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_payee_category_distribution.return_value = {
            'movistar': [{'category_name': 'Internet', 'count': 2, 'percentage': 1.0}],
        }

        service.prepare_expense(TELEGRAM_ID, 'Movistar 50k')

        mock_learning_repository.get_payee_category_distribution.assert_called_with(TELEGRAM_ID)
        assert mock_learning_repository.get_payee_category_distribution.call_count == 1


class TestCommitExpense:
    """Tests for the commit phase: YNAB transaction creation + learning."""

    def test_creates_ynab_transaction(self, service, mock_user_repository, mock_ynab_repository, authorized_user, sample_expense):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service.commit_expense(TELEGRAM_ID, sample_expense, authorized_user.budget_id, authorized_user.default_account_id)
        mock_ynab_repository.create_transaction.assert_called_once_with(
            sample_expense, authorized_user.budget_id, authorized_user.default_account_id
        )

    def test_returns_expense_result_with_transaction_id(self, service, mock_user_repository, authorized_user, sample_expense):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.commit_expense(TELEGRAM_ID, sample_expense, authorized_user.budget_id, authorized_user.default_account_id)
        assert result.success is True
        assert result.transaction_id == 'txn-id-123'

    def test_records_successful_transaction(self, service, mock_user_repository, mock_learning_repository, authorized_user, sample_expense):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service.commit_expense(TELEGRAM_ID, sample_expense, authorized_user.budget_id, authorized_user.default_account_id)
        mock_learning_repository.record_successful_transaction.assert_called_once_with(TELEGRAM_ID, sample_expense)

    def test_adds_to_recent_transactions(self, service, mock_user_repository, mock_learning_repository, authorized_user, sample_expense):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service.commit_expense(TELEGRAM_ID, sample_expense, authorized_user.budget_id, authorized_user.default_account_id)
        mock_learning_repository.add_recent_transaction.assert_called_once_with(TELEGRAM_ID, sample_expense, 'txn-id-123')

    def test_creates_fresh_repository_from_factory(self, service, mock_user_repository, mock_ynab_factory, authorized_user, sample_expense):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service.commit_expense(TELEGRAM_ID, sample_expense, authorized_user.budget_id, authorized_user.default_account_id)
        # factory.get_repository must be called (fresh repo per commit)
        mock_ynab_factory.get_repository.assert_called_with(authorized_user)

    def test_raises_on_ynab_failure(self, service, mock_user_repository, mock_ynab_repository, authorized_user, sample_expense):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.create_transaction.return_value = None
        from domain.exceptions import YNABApiException
        with pytest.raises(YNABApiException):
            service.commit_expense(TELEGRAM_ID, sample_expense, authorized_user.budget_id, authorized_user.default_account_id)

    def test_raises_on_user_not_configured(self, service, mock_user_repository, sample_expense):
        mock_user_repository.find_by_telegram_id.return_value = None
        from domain.exceptions import UserNotConfiguredException
        with pytest.raises(UserNotConfiguredException):
            service.commit_expense(999, sample_expense, 'budget-x', 'account-x')


class TestPrepareAndCommitRoundTrip:
    """Integration-style tests: prepare + commit produce same end state as process_message."""

    def test_prepare_then_commit_creates_transaction(
        self, service, mock_user_repository, mock_ynab_repository, mock_learning_repository, authorized_user
    ):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        prep = service.prepare_expense(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        mock_ynab_repository.create_transaction.assert_not_called()

        result = service.commit_expense(TELEGRAM_ID, prep.expense, prep.budget_id, prep.account_id)
        mock_ynab_repository.create_transaction.assert_called_once()
        assert result.success is True
        assert result.transaction_id == 'txn-id-123'
        mock_learning_repository.record_successful_transaction.assert_called_once()
        mock_learning_repository.add_recent_transaction.assert_called_once()

    def test_process_message_still_works_end_to_end(self, service, mock_user_repository, authorized_user):
        """Backward compatibility: process_message must still return a successful MessageResult."""
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service.process_message(TELEGRAM_ID, 'Almuerzo McDonald 25 lucas')
        assert result.expense_result.success is True
        assert result.expense_result.transaction_id == 'txn-id-123'


class TestPrepareReceipt:
    """Tests for prepare_receipt (parse phase for receipt images)."""

    def test_returns_dict_with_required_keys(self, service, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 45000.0, 'category': 'Restaurants',
            'payee': 'El Corral', 'memo': 'almuerzo', 'confidence': 0.95,
        }
        result = service.prepare_receipt(TELEGRAM_ID, 'base64_data', 'almuerzo')
        from domain.models.expense import PreparedExpense
        assert isinstance(result, PreparedExpense)

    def test_no_ynab_transaction_created(self, service, mock_user_repository, mock_ynab_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 45000.0, 'category': 'Restaurants',
            'payee': 'El Corral', 'memo': 'almuerzo', 'confidence': 0.95,
        }
        service.prepare_receipt(TELEGRAM_ID, 'base64_data', 'almuerzo')
        mock_ynab_repository.create_transaction.assert_not_called()

    def test_expense_result_has_no_transaction_id(self, service, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 45000.0, 'category': 'Restaurants',
            'payee': 'El Corral', 'memo': 'almuerzo', 'confidence': 0.95,
        }
        result = service.prepare_receipt(TELEGRAM_ID, 'base64_data')
        assert result.expense_result.transaction_id is None

    def test_parser_source_is_receipt(self, service, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 45000.0, 'category': 'Restaurants',
            'payee': 'El Corral', 'memo': 'almuerzo', 'confidence': 0.95,
        }
        result = service.prepare_receipt(TELEGRAM_ID, 'base64_data')
        assert result.expense.parser_source == 'receipt'

    def test_raises_on_parse_failure(self, service, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_receipt_image.return_value = None
        from domain.exceptions import ImageProcessingException
        with pytest.raises(ImageProcessingException):
            service.prepare_receipt(TELEGRAM_ID, 'bad_data')

    def test_raises_on_user_not_configured(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        from domain.exceptions import UserNotConfiguredException
        with pytest.raises(UserNotConfiguredException):
            service.prepare_receipt(999, 'data')

    def test_passes_learning_hints_to_receipt_parser(self, service, mock_user_repository, mock_llm_parser, mock_learning_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_payee_category_distribution.return_value = {
            'exito': [{'category_name': 'Groceries', 'count': 2, 'percentage': 1.0}],
        }
        mock_llm_parser.parse_receipt_image.return_value = {
            'amount': 45000.0, 'category': 'Restaurants',
            'payee': 'El Corral', 'memo': 'almuerzo', 'confidence': 0.95,
        }

        service.prepare_receipt(TELEGRAM_ID, 'base64_data')

        mock_llm_parser.parse_receipt_image.assert_called_with(
            'base64_data',
            None,
            timezone_str=DEFAULT_TIMEZONE,
            learning_hints='- exito: Groceries (100%)',
        )


class TestPrepareSharedExpense:
    """Tests for prepare_shared_expense (parse phase for shared expenses)."""

    def test_returns_dict_with_required_keys(self, service_with_split, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0, 'category': 'Groceries',
            'payee': 'Carulla', 'memo': 'mercado', 'confidence': 0.9,
            'person': 'Juan', 'proportion': '1/2', 'payer': 'user',
        }
        result = service_with_split.prepare_shared_expense(TELEGRAM_ID, 'mercado con Juan 50k')
        from domain.models.expense import PreparedExpense
        assert isinstance(result, PreparedExpense)

    def test_intent_is_shared_expense(self, service_with_split, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0, 'category': 'Groceries',
            'payee': 'Carulla', 'memo': 'mercado', 'confidence': 0.9,
            'person': 'Juan', 'proportion': '1/2', 'payer': 'user',
        }
        result = service_with_split.prepare_shared_expense(TELEGRAM_ID, 'mercado con Juan 50k')
        assert result.intent == 'shared_expense'

    def test_expense_is_marked_as_split(self, service_with_split, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0, 'category': 'Groceries',
            'payee': 'Carulla', 'memo': 'mercado', 'confidence': 0.9,
            'person': 'Juan', 'proportion': '1/2', 'payer': 'user',
        }
        result = service_with_split.prepare_shared_expense(TELEGRAM_ID, 'mercado con Juan 50k')
        assert result.expense.is_split is True

    def test_no_ynab_transaction_created(self, service_with_split, mock_user_repository, mock_ynab_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0, 'category': 'Groceries',
            'payee': 'Carulla', 'memo': 'mercado', 'confidence': 0.9,
            'person': 'Juan', 'proportion': '1/2', 'payer': 'user',
        }
        service_with_split.prepare_shared_expense(TELEGRAM_ID, 'mercado con Juan 50k')
        mock_ynab_repository.create_transaction.assert_not_called()

    def test_expense_result_has_no_transaction_id(self, service_with_split, mock_user_repository, mock_llm_parser, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0, 'category': 'Groceries',
            'payee': 'Carulla', 'memo': 'mercado', 'confidence': 0.9,
            'person': 'Juan', 'proportion': '1/2', 'payer': 'user',
        }
        result = service_with_split.prepare_shared_expense(TELEGRAM_ID, 'mercado con Juan 50k')
        assert result.expense_result.transaction_id is None

    def test_raises_on_user_not_configured(self, service_with_split, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        from domain.exceptions import UserNotConfiguredException
        with pytest.raises(UserNotConfiguredException):
            service_with_split.prepare_shared_expense(999, 'test')

    def test_raises_when_no_split_config_repository(self, service, mock_user_repository, mock_llm_parser, authorized_user):
        """Service without split_config_repository raises ExpenseParsingException."""
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0, 'category': 'Groceries',
            'payee': 'Carulla', 'memo': 'mercado', 'confidence': 0.9,
            'person': 'Juan', 'proportion': '1/2', 'payer': 'user',
        }
        from domain.exceptions import ExpenseParsingException
        with pytest.raises(ExpenseParsingException):
            service.prepare_shared_expense(TELEGRAM_ID, 'mercado con Juan 50k')

    def test_split_amount_propagates_to_expense(self, service_with_split, mock_user_repository, mock_llm_parser, authorized_user):
        """split_amount from LLM response is set as split_fixed_amount on the returned expense."""
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 60000.0, 'category': 'Restaurants',
            'payee': 'El Corral', 'memo': '36700 son por Juan', 'confidence': 0.9,
            'person': 'Juan', 'proportion': None, 'payer': 'user',
            'split_amount': 36700,
        }
        result = service_with_split.prepare_shared_expense(TELEGRAM_ID, '60k almuerzo, 36700 son por Juan')
        assert result.expense.split_fixed_amount == Decimal('36700')

    def test_split_amount_null_leaves_fixed_amount_none_in_prepare(self, service_with_split, mock_user_repository, mock_llm_parser, authorized_user):
        """split_amount: null in LLM response leaves split_fixed_amount as None."""
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_llm_parser.parse_message.return_value = {
            'intent': 'shared_expense',
            'amount': 50000.0, 'category': 'Groceries',
            'payee': 'Carulla', 'memo': 'mercado', 'confidence': 0.9,
            'person': 'Juan', 'proportion': '1/2', 'payer': 'user',
            'split_amount': None,
        }
        result = service_with_split.prepare_shared_expense(TELEGRAM_ID, 'mercado con Juan 50k')
        assert result.expense.split_fixed_amount is None


# ---------------------------------------------------------------------------
# commit_shared_expense
# ---------------------------------------------------------------------------

class TestCommitSharedExpense:
    """Tests for the commit phase of shared expenses."""

    @pytest.fixture
    def prepared_shared(self, sample_expense, authorized_user):
        """Simulate the PreparedExpense returned by prepare_shared_expense."""
        sample_expense.is_split = True
        sample_expense.split_person = 'Juan'
        from domain.models.expense import PreparedExpense
        return PreparedExpense(
            expense=sample_expense,
            budget_id=authorized_user.budget_id,
            account_id=authorized_user.default_account_id,
            user_config=authorized_user,
            expense_result=None,
            intent='shared_expense',
        )

    def test_creates_ynab_transaction(self, service_with_split, mock_user_repository, mock_ynab_repository, authorized_user, prepared_shared):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service_with_split.commit_shared_expense(TELEGRAM_ID, prepared_shared)
        mock_ynab_repository.create_transaction.assert_called_once_with(
            prepared_shared.expense, authorized_user.budget_id, authorized_user.default_account_id
        )

    def test_returns_expense_result_with_transaction_id(self, service_with_split, mock_user_repository, authorized_user, prepared_shared):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        result = service_with_split.commit_shared_expense(TELEGRAM_ID, prepared_shared)
        assert result.success is True
        assert result.transaction_id == 'txn-id-123'

    def test_records_successful_transaction(self, service_with_split, mock_user_repository, mock_learning_repository, authorized_user, prepared_shared):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service_with_split.commit_shared_expense(TELEGRAM_ID, prepared_shared)
        mock_learning_repository.record_successful_transaction.assert_called_once_with(TELEGRAM_ID, prepared_shared.expense)

    def test_adds_to_recent_transactions(self, service_with_split, mock_user_repository, mock_learning_repository, authorized_user, prepared_shared):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service_with_split.commit_shared_expense(TELEGRAM_ID, prepared_shared)
        mock_learning_repository.add_recent_transaction.assert_called_once_with(TELEGRAM_ID, prepared_shared.expense, 'txn-id-123')

    def test_creates_fresh_repository_from_factory(self, service_with_split, mock_user_repository, mock_ynab_factory, authorized_user, prepared_shared):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        service_with_split.commit_shared_expense(TELEGRAM_ID, prepared_shared)
        mock_ynab_factory.get_repository.assert_called_with(authorized_user)

    def test_raises_on_ynab_failure(self, service_with_split, mock_user_repository, mock_ynab_repository, authorized_user, prepared_shared):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_ynab_repository.create_transaction.return_value = None
        from domain.exceptions import YNABApiException
        with pytest.raises(YNABApiException):
            service_with_split.commit_shared_expense(TELEGRAM_ID, prepared_shared)

    def test_raises_on_user_not_configured(self, service_with_split, mock_user_repository, prepared_shared):
        mock_user_repository.find_by_telegram_id.return_value = None
        from domain.exceptions import UserNotConfiguredException
        with pytest.raises(UserNotConfiguredException):
            service_with_split.commit_shared_expense(999, prepared_shared)

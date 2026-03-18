"""Tests for ExpenseService."""
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from application.services.expense_service import ExpenseService, _SPECIAL_CHARS_PATTERN
from application.services.budget_query_service import BudgetQueryService
from domain.models.expense import Expense
from domain.models.user import UserConfiguration, UserStatus, YNABCategory, YNABPayee

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
        mock_llm_parser.parse_receipt_image.assert_called_with('data', 'almuerzo con amigos')

    def test_parse_failure(self, service, mock_llm_parser):
        mock_llm_parser.parse_receipt_image.return_value = None
        result = service.process_receipt_image(TELEGRAM_ID, 'data')
        assert not result.success
        assert 'legible' in result.error_message

    def test_user_not_configured(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        result = service.process_receipt_image(999, 'data')
        assert not result.success
        assert 'not configured' in result.error_message.lower() or 'not configured' in result.error_message


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

    def test_low_confidence_enhanced(self, service, mock_learning_repository, sample_categories):
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.8, 3)
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.3,
        )
        result = service._enhance_with_learning(expense, sample_categories, TELEGRAM_ID)
        assert result.category_id == 'cat-2'
        assert result.confidence == 0.8
        assert "aprendido de tus ultimas 3 compras" in result.category_explanation

    def test_learning_prediction_lower_confidence_not_used(self, service, mock_learning_repository, sample_categories):
        mock_learning_repository.predict_category.return_value = ('cat-2', 0.2, 1)
        expense = Expense(
            amount=Decimal('1000'), payee='Test', memo='x',
            category_id='cat-1', confidence=0.5,
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
# correct_recent_transaction
# ---------------------------------------------------------------------------

class TestCorrectRecentTransaction:

    def test_success(self, service, mock_user_repository, mock_learning_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [
            {'payee': 'McDonalds', 'category_id': 'cat-old', 'category_name': 'Comida rápida', 'amount': 25000},
        ]
        result = service.correct_recent_transaction(TELEGRAM_ID, 0, 'cat-new')
        assert result == {'payee': 'McDonalds', 'old_category_name': 'Comida rápida'}
        mock_learning_repository.record_user_correction.assert_called_once()
        # Verify telegram_id is passed
        call_args = mock_learning_repository.record_user_correction.call_args
        assert call_args[0][0] == TELEGRAM_ID

    def test_success_falls_back_to_id_when_no_category_name(self, service, mock_user_repository, mock_learning_repository, authorized_user):
        mock_user_repository.find_by_telegram_id.return_value = authorized_user
        mock_learning_repository.get_recent_transactions.return_value = [
            {'payee': 'McDonalds', 'category_id': 'cat-old', 'amount': 25000},
        ]
        result = service.correct_recent_transaction(TELEGRAM_ID, 0, 'cat-new')
        assert result == {'payee': 'McDonalds', 'old_category_name': 'cat-old'}

    def test_user_not_found(self, service, mock_user_repository):
        mock_user_repository.find_by_telegram_id.return_value = None
        assert service.correct_recent_transaction(999, 0, 'cat-new') is None

    def test_index_out_of_range(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.return_value = []
        assert service.correct_recent_transaction(TELEGRAM_ID, 5, 'cat-new') is None


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
        mock_ynab_repository.create_transaction.assert_called_once()

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

    def test_null_date_uses_default_now(self, service, mock_llm_parser):
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
        # date should be approximately now (within 5 seconds)
        delta = abs((result.expense_result.expense.date - datetime.now()).total_seconds())
        assert delta < 5

    def test_invalid_date_string_uses_default_now(self, service, mock_llm_parser):
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
        delta = abs((result.expense_result.expense.date - datetime.now()).total_seconds())
        assert delta < 5

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

    def test_missing_date_key_uses_default_now(self, service, mock_llm_parser):
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
        delta = abs((result.expense_result.expense.date - datetime.now()).total_seconds())
        assert delta < 5


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

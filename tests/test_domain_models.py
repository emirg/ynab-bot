"""Tests for domain models: Expense, ExpenseResult, UserConfiguration, YNAB models, BudgetQuery."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from domain.models.expense import Expense, ExpenseResult, _UUID_PATTERN
from domain.models.budget_query import BudgetQueryResult, MessageResult
from domain.models.user import (
    UserConfiguration, UserStatus,
    YNABBudget, YNABAccount, YNABCategory,
)
from domain.models.onboarding import OnboardingStep


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------

class TestExpense:

    def test_is_valid_basic(self, sample_expense):
        assert sample_expense.is_valid()

    def test_is_valid_minimal(self, minimal_expense):
        assert minimal_expense.is_valid()

    def test_invalid_zero_amount(self):
        e = Expense(amount=Decimal('0'), payee='Test', memo='x')
        assert not e.is_valid()

    def test_invalid_negative_amount(self):
        e = Expense(amount=Decimal('-100'), payee='Test', memo='x')
        assert not e.is_valid()

    def test_invalid_empty_payee(self):
        e = Expense(amount=Decimal('1000'), payee='', memo='x')
        assert not e.is_valid()

    def test_invalid_whitespace_payee(self):
        e = Expense(amount=Decimal('1000'), payee='   ', memo='x')
        assert not e.is_valid()

    def test_invalid_negative_confidence(self):
        e = Expense(amount=Decimal('1000'), payee='Test', memo='x', confidence=-0.1)
        assert not e.is_valid()

    def test_to_ynab_format_with_valid_category(self, sample_expense):
        result = sample_expense.to_ynab_format('budget-1', 'default-acc')
        txn = result['transaction']
        assert txn['amount'] == -25000000  # 25000 * -1000
        assert txn['payee_name'] == "McDonald's"
        assert txn['account_id'] == '660e8400-e29b-41d4-a716-446655440000'
        assert txn['category_id'] == '550e8400-e29b-41d4-a716-446655440000'
        assert txn['date'] == '2026-03-09'
        assert txn['cleared'] == 'uncleared'

    def test_to_ynab_format_uses_default_account(self, minimal_expense):
        result = minimal_expense.to_ynab_format('budget-1', 'default-acc')
        assert result['transaction']['account_id'] == 'default-acc'

    def test_to_ynab_format_invalid_uuid_omits_category(self):
        e = Expense(
            amount=Decimal('5000'), payee='Test', memo='x',
            category_id='not-a-uuid',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert 'category_id' not in result['transaction']

    def test_to_ynab_format_empty_category(self):
        e = Expense(amount=Decimal('5000'), payee='Test', memo='x', category_id='')
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert 'category_id' not in result['transaction']

    def test_to_ynab_format_whitespace_category(self):
        e = Expense(amount=Decimal('5000'), payee='Test', memo='x', category_id='   ')
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert 'category_id' not in result['transaction']

    def test_default_date_is_set(self):
        e = Expense(amount=Decimal('1'), payee='T', memo='m')
        assert isinstance(e.date, datetime)

    def test_default_confidence_is_zero(self):
        e = Expense(amount=Decimal('1'), payee='T', memo='m')
        assert e.confidence == 0.0

    def test_default_parser_source(self):
        e = Expense(amount=Decimal('1'), payee='T', memo='m')
        assert e.parser_source == 'unknown'


class TestUUIDPattern:

    @pytest.mark.parametrize('uuid', [
        '550e8400-e29b-41d4-a716-446655440000',
        'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE',
        '00000000-0000-0000-0000-000000000000',
    ])
    def test_valid_uuids(self, uuid):
        assert _UUID_PATTERN.match(uuid)

    @pytest.mark.parametrize('invalid', [
        'not-a-uuid',
        '550e8400e29b41d4a716446655440000',
        '550e8400-e29b-41d4-a716',
        '',
        'Groceries',
    ])
    def test_invalid_uuids(self, invalid):
        assert not _UUID_PATTERN.match(invalid)


class TestExpenseResult:

    def test_success_result(self, sample_expense):
        result = ExpenseResult.success_result(sample_expense, 'txn-1')
        assert result.success is True
        assert result.expense == sample_expense
        assert result.transaction_id == 'txn-1'
        assert result.error_message is None

    def test_error_result(self):
        result = ExpenseResult.error_result('Something failed')
        assert result.success is False
        assert result.error_message == 'Something failed'
        assert result.expense is None


# ---------------------------------------------------------------------------
# UserConfiguration
# ---------------------------------------------------------------------------

class TestUserConfiguration:

    def test_is_configured_requires_both(self, authorized_user):
        assert authorized_user.is_configured()

    def test_not_configured_missing_budget(self):
        u = UserConfiguration(telegram_id=1, default_account_id='acc-1')
        assert not u.is_configured()

    def test_not_configured_missing_account(self):
        u = UserConfiguration(telegram_id=1, budget_id='budget-1')
        assert not u.is_configured()

    def test_status_checks(self, authorized_user, pending_user, blocked_user):
        assert authorized_user.is_authorized()
        assert not authorized_user.is_pending()
        assert not authorized_user.is_blocked()

        assert pending_user.is_pending()
        assert not pending_user.is_authorized()

        assert blocked_user.is_blocked()
        assert not blocked_user.is_authorized()

    def test_authorize(self, pending_user):
        pending_user.authorize(approved_by=999)
        assert pending_user.is_authorized()
        assert pending_user.approved_by == 999
        assert pending_user.approved_at is not None

    def test_block(self, authorized_user):
        authorized_user.block()
        assert authorized_user.is_blocked()

    def test_update_budget(self, authorized_user):
        old_updated = authorized_user.updated_at
        authorized_user.update_budget('new-budget')
        assert authorized_user.budget_id == 'new-budget'

    def test_update_default_account(self, authorized_user):
        authorized_user.update_default_account('new-acc', 'New Account')
        assert authorized_user.default_account_id == 'new-acc'
        assert authorized_user.default_account_name == 'New Account'

    def test_update_profile(self, authorized_user):
        authorized_user.update_profile(username='new', first_name='New', last_name='Name')
        assert authorized_user.username == 'new'
        assert authorized_user.first_name == 'New'
        assert authorized_user.last_name == 'Name'

    def test_update_profile_partial(self, authorized_user):
        old_first = authorized_user.first_name
        authorized_user.update_profile(last_name='Changed')
        assert authorized_user.first_name == old_first
        assert authorized_user.last_name == 'Changed'

    def test_get_display_name_full(self, authorized_user):
        assert authorized_user.get_display_name() == 'Test User'

    def test_get_display_name_first_only(self):
        u = UserConfiguration(telegram_id=1, first_name='Alice')
        assert u.get_display_name() == 'Alice'

    def test_get_display_name_username(self):
        u = UserConfiguration(telegram_id=1, username='alice')
        assert u.get_display_name() == '@alice'

    def test_get_display_name_fallback(self):
        u = UserConfiguration(telegram_id=42)
        assert u.get_display_name() == 'User 42'

    def test_default_status_is_pending(self):
        u = UserConfiguration(telegram_id=1)
        assert u.status == UserStatus.PENDING

    def test_has_ynab_token_false_by_default(self):
        u = UserConfiguration(telegram_id=1)
        assert not u.has_ynab_token()

    def test_has_ynab_token_true(self):
        u = UserConfiguration(telegram_id=1, ynab_access_token='tok')
        assert u.has_ynab_token()

    def test_is_token_expired_none_expires(self):
        u = UserConfiguration(telegram_id=1, ynab_access_token='tok')
        assert u.is_token_expired()

    def test_is_token_expired_future(self):
        u = UserConfiguration(
            telegram_id=1,
            ynab_access_token='tok',
            ynab_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        assert not u.is_token_expired()

    def test_is_token_expired_within_buffer(self):
        u = UserConfiguration(
            telegram_id=1,
            ynab_access_token='tok',
            ynab_token_expires_at=datetime.now() + timedelta(minutes=3),
        )
        assert u.is_token_expired()

    def test_update_ynab_tokens(self):
        u = UserConfiguration(telegram_id=1)
        u.update_ynab_tokens('access', 'refresh', 7200)
        assert u.ynab_access_token == 'access'
        assert u.ynab_refresh_token == 'refresh'
        assert u.ynab_token_expires_at is not None
        assert u.ynab_token_expires_at > datetime.now()

    def test_clear_ynab_tokens(self):
        u = UserConfiguration(telegram_id=1, ynab_access_token='tok', ynab_refresh_token='ref')
        u.clear_ynab_tokens()
        assert u.ynab_access_token is None
        assert u.ynab_refresh_token is None
        assert u.ynab_token_expires_at is None


# ---------------------------------------------------------------------------
# YNAB domain models
# ---------------------------------------------------------------------------

class TestYNABBudget:

    def test_from_api_response(self):
        data = {'id': 'b1', 'name': 'Budget', 'currency_format': {'iso_code': 'COP'}}
        budget = YNABBudget.from_api_response(data)
        assert budget.id == 'b1'
        assert budget.name == 'Budget'

    def test_from_api_response_missing_currency(self):
        data = {'id': 'b1', 'name': 'Budget'}
        budget = YNABBudget.from_api_response(data)
        assert budget.currency_format == {}


class TestYNABAccount:

    def test_from_api_response(self):
        data = {
            'id': 'a1', 'name': 'Nu', 'type': 'creditCard',
            'balance': 500000, 'cleared_balance': 400000,
            'uncleared_balance': 100000, 'closed': False, 'deleted': False,
        }
        account = YNABAccount.from_api_response(data)
        assert account.id == 'a1'
        assert account.balance == 500000
        assert not account.closed

    def test_from_api_response_defaults(self):
        data = {'id': 'a2', 'name': 'Cash', 'type': 'cash'}
        account = YNABAccount.from_api_response(data)
        assert account.balance == 0
        assert not account.closed
        assert not account.deleted


class TestYNABCategory:

    def test_from_api_response(self):
        data = {
            'id': 'c1', 'name': 'Groceries', 'budgeted': 500000,
            'activity': -200000, 'balance': 300000,
        }
        cat = YNABCategory.from_api_response(data, 'Essentials')
        assert cat.id == 'c1'
        assert cat.full_name == 'Essentials \u2192 Groceries'
        assert cat.group_name == 'Essentials'

    def test_from_api_response_defaults(self):
        data = {'id': 'c2', 'name': 'Fun'}
        cat = YNABCategory.from_api_response(data, 'Optional')
        assert cat.budgeted == 0
        assert not cat.deleted
        assert not cat.hidden


# ---------------------------------------------------------------------------
# BudgetQueryResult
# ---------------------------------------------------------------------------

class TestBudgetQueryResult:

    def test_success_result(self):
        data = {'name': 'Groceries', 'balance': 300000}
        r = BudgetQueryResult.success_result('category_balance', data)
        assert r.success is True
        assert r.query_type == 'category_balance'
        assert r.data == data
        assert r.error_message is None

    def test_error_result(self):
        r = BudgetQueryResult.error_result('category_balance', 'No encontrada')
        assert r.success is False
        assert r.query_type == 'category_balance'
        assert r.error_message == 'No encontrada'
        assert r.data is None

    def test_default_values(self):
        r = BudgetQueryResult(success=True, query_type='budget_summary')
        assert r.data is None
        assert r.error_message is None


# ---------------------------------------------------------------------------
# MessageResult
# ---------------------------------------------------------------------------

class TestMessageResult:

    def test_expense_intent(self, sample_expense):
        expense_result = ExpenseResult.success_result(sample_expense, 'txn-1')
        r = MessageResult(intent='expense', expense_result=expense_result)
        assert r.intent == 'expense'
        assert r.expense_result is expense_result
        assert r.query_result is None

    def test_query_intent(self):
        query_result = BudgetQueryResult.success_result(
            'account_balance', {'name': 'Nu Card', 'balance': 500000}
        )
        r = MessageResult(intent='query', query_result=query_result)
        assert r.intent == 'query'
        assert r.query_result is query_result
        assert r.expense_result is None

    def test_default_values(self):
        r = MessageResult(intent='expense')
        assert r.expense_result is None
        assert r.query_result is None


# ---------------------------------------------------------------------------
# OnboardingStep
# ---------------------------------------------------------------------------

class TestOnboardingStep:

    def test_enum_values(self):
        assert OnboardingStep.NEEDS_YNAB_CONNECTION.value == "needs_ynab_connection"
        assert OnboardingStep.NEEDS_BUDGET.value == "needs_budget"
        assert OnboardingStep.NEEDS_ACCOUNT.value == "needs_account"
        assert OnboardingStep.COMPLETE.value == "complete"

    def test_enum_members(self):
        assert len(OnboardingStep) == 4
        assert OnboardingStep("needs_ynab_connection") == OnboardingStep.NEEDS_YNAB_CONNECTION

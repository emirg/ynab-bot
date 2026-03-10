"""Tests for Telegram response formatters."""
import pytest
from decimal import Decimal

from presentation.telegram.formatters import (
    ExpenseResponseFormatter,
    ConfigResponseFormatter,
    LearningResponseFormatter,
    GeneralResponseFormatter,
)
from domain.models.expense import Expense, ExpenseResult
from domain.models.user import YNABBudget, YNABAccount


# ---------------------------------------------------------------------------
# ExpenseResponseFormatter
# ---------------------------------------------------------------------------

class TestExpenseResponseFormatter:

    def test_format_success(self, sample_expense):
        result = ExpenseResult.success_result(sample_expense, 'txn-1')
        msg = ExpenseResponseFormatter.format_success(result)
        assert 'registrado exitosamente' in msg
        assert "McDonald's" in msg
        assert '$25,000' in msg
        assert 'LLM' in msg

    def test_format_success_high_confidence(self, sample_expense):
        sample_expense.confidence = 0.95
        result = ExpenseResult.success_result(sample_expense)
        msg = ExpenseResponseFormatter.format_success(result)
        assert '🔥' in msg

    def test_format_success_medium_confidence(self, sample_expense):
        sample_expense.confidence = 0.6
        result = ExpenseResult.success_result(sample_expense)
        msg = ExpenseResponseFormatter.format_success(result)
        assert '✅' in msg

    def test_format_success_low_confidence(self, sample_expense):
        sample_expense.confidence = 0.3
        result = ExpenseResult.success_result(sample_expense)
        msg = ExpenseResponseFormatter.format_success(result)
        assert '⚠️' in msg

    def test_format_success_no_category(self, minimal_expense):
        result = ExpenseResult.success_result(minimal_expense)
        msg = ExpenseResponseFormatter.format_success(result)
        assert 'Sin categoría' in msg

    def test_format_success_no_account(self, minimal_expense):
        result = ExpenseResult.success_result(minimal_expense)
        msg = ExpenseResponseFormatter.format_success(result)
        assert 'Cuenta por defecto' in msg

    def test_format_success_error_result_returns_error(self):
        result = ExpenseResult.error_result('fail')
        msg = ExpenseResponseFormatter.format_success(result)
        assert 'Error' in msg

    def test_format_error_not_configured(self):
        result = ExpenseResult.error_result('User not configured')
        msg = ExpenseResponseFormatter.format_error(result)
        assert 'no configurado' in msg.lower()
        assert '/config' in msg

    def test_format_error_parse(self):
        result = ExpenseResult.error_result('Could not parse expense')
        msg = ExpenseResponseFormatter.format_error(result)
        assert 'formato del gasto' in msg.lower()

    def test_format_error_ynab(self):
        result = ExpenseResult.error_result('YNAB API timeout')
        msg = ExpenseResponseFormatter.format_error(result)
        assert 'YNAB' in msg

    def test_format_error_generic(self):
        result = ExpenseResult.error_result('Something unknown')
        msg = ExpenseResponseFormatter.format_error(result)
        assert 'Something unknown' in msg

    def test_format_error_success_result(self):
        result = ExpenseResult(success=True)
        msg = ExpenseResponseFormatter.format_error(result)
        assert 'exitosamente' in msg.lower()


# ---------------------------------------------------------------------------
# ConfigResponseFormatter
# ---------------------------------------------------------------------------

class TestConfigResponseFormatter:

    def test_format_budgets_list(self, sample_budgets):
        msg = ConfigResponseFormatter.format_budgets_list(sample_budgets)
        assert 'My Budget' in msg
        assert 'Savings' in msg

    def test_format_budgets_empty(self):
        msg = ConfigResponseFormatter.format_budgets_list([])
        assert 'No se encontraron' in msg

    def test_format_accounts_list(self, sample_accounts):
        active = [a for a in sample_accounts if not a.closed and not a.deleted]
        msg = ConfigResponseFormatter.format_accounts_list(active)
        assert 'Nu Card' in msg
        assert 'Bancolombia' in msg

    def test_format_accounts_empty(self):
        msg = ConfigResponseFormatter.format_accounts_list([])
        assert 'No se encontraron' in msg

    def test_format_accounts_balance_emojis(self):
        pos = YNABAccount(id='1', name='Pos', type='checking', balance=1000)
        neg = YNABAccount(id='2', name='Neg', type='checking', balance=-1000)
        zero = YNABAccount(id='3', name='Zero', type='checking', balance=0)
        msg = ConfigResponseFormatter.format_accounts_list([pos, neg, zero])
        assert '💰' in msg
        assert '💸' in msg
        assert '➖' in msg

    def test_format_user_status_configured(self):
        status = {
            'configured': True,
            'budget_id': 'b1',
            'budget_name': 'My Budget',
            'default_account_id': 'a1',
            'default_account_name': 'Nu Card',
            'message': 'Usuario completamente configurado',
            'created_at': '2026-01-01T00:00:00',
        }
        msg = ConfigResponseFormatter.format_user_status(status)
        assert '✅' in msg
        assert 'My Budget' in msg
        assert 'Nu Card' in msg

    def test_format_user_status_not_configured(self):
        status = {
            'configured': False,
            'budget_id': None,
            'default_account_id': None,
            'message': 'Falta configurar presupuesto y cuenta',
        }
        msg = ConfigResponseFormatter.format_user_status(status)
        assert '⚠️' in msg
        assert '/budgets' in msg
        assert '/accounts' in msg

    def test_format_user_status_partial(self):
        status = {
            'configured': False,
            'budget_id': 'b1',
            'budget_name': 'Budget',
            'default_account_id': None,
            'message': 'Falta configurar cuenta por defecto',
        }
        msg = ConfigResponseFormatter.format_user_status(status)
        assert '/accounts' in msg


# ---------------------------------------------------------------------------
# LearningResponseFormatter
# ---------------------------------------------------------------------------

class TestLearningResponseFormatter:

    def test_format_stats_passthrough(self):
        msg = LearningResponseFormatter.format_stats_response('hello')
        assert msg == 'hello'

    def test_format_recent_passthrough(self):
        msg = LearningResponseFormatter.format_recent_transactions_response('test')
        assert msg == 'test'

    def test_format_correction_success(self):
        msg = LearningResponseFormatter.format_correction_success('McDonalds', 'Old', 'New')
        assert 'Corrección registrada' in msg
        assert 'McDonalds' in msg
        assert 'Old' in msg
        assert 'New' in msg

    def test_format_correction_error(self):
        msg = LearningResponseFormatter.format_correction_error('something failed')
        assert 'something failed' in msg
        assert '❌' in msg


# ---------------------------------------------------------------------------
# GeneralResponseFormatter
# ---------------------------------------------------------------------------

class TestGeneralResponseFormatter:

    def test_welcome_message(self):
        msg = GeneralResponseFormatter.format_welcome_message()
        assert '/start' in msg
        assert '/help' in msg
        assert '/config' in msg

    def test_help_message(self):
        msg = GeneralResponseFormatter.format_help_message()
        assert '$40000' in msg or '40000' in msg
        assert '/corregir' in msg
        assert 'lucas' in msg

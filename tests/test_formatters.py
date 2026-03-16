"""Tests for Telegram response formatters."""
import pytest
from decimal import Decimal

from presentation.telegram.formatters import (
    ExpenseResponseFormatter,
    BudgetQueryFormatter,
    ConfigResponseFormatter,
    LearningResponseFormatter,
    GeneralResponseFormatter,
    SplitConfigResponseFormatter,
)
from domain.models.expense import Expense, ExpenseResult
from domain.models.budget_query import BudgetQueryResult
from domain.models.user import YNABBudget, YNABAccount
from domain.models.onboarding import OnboardingStep


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
        assert 'Razon' in msg
        assert 'sugerido por IA' in msg

    def test_format_success_no_explanation(self, sample_expense):
        sample_expense.category_explanation = None
        result = ExpenseResult.success_result(sample_expense)
        msg = ExpenseResponseFormatter.format_success(result)
        assert '*Razon:* desconocido' in msg

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

    def test_format_success_split_expense(self):
        expense = Expense(
            amount=Decimal('50000'), payee="McDonald's", memo='almuerzo mitad',
            category_name='Restaurants', account_name='Nu Card',
            confidence=0.85, category_explanation='sugerido por IA, confianza 85%',
            is_split=True, split_person='Juan',
            split_proportion=Decimal('0.5'),
            split_category_name='Gastos Compartidos',
        )
        result = ExpenseResult.success_result(expense, 'txn-1')
        msg = ExpenseResponseFormatter.format_success(result)
        assert 'Gasto compartido registrado' in msg
        assert 'Juan' in msg
        assert '$50,000' in msg
        assert '$25,000' in msg
        assert 'Restaurants' in msg
        assert 'Gastos Compartidos' in msg
        assert 'Tu parte (50%)' in msg
        assert 'Splitwise (50%)' in msg

    def test_format_success_other_paid_expense(self):
        expense = Expense(
            amount=Decimal('50000'), payee='Carulla', memo='Eli gastó 50k en carulla conmigo',
            category_name='Groceries', account_name='Nu Savings',
            confidence=0.9,
            is_split=True, split_person='Eli',
            split_proportion=Decimal('0.5'),
            split_category_name='Gastos con Eli',
            payer='other',
        )
        result = ExpenseResult.success_result(expense, 'txn-2')
        msg = ExpenseResponseFormatter.format_success(result)
        assert 'pagado por Eli' in msg
        assert 'Eli' in msg
        assert '$50,000' in msg
        assert '$25,000' in msg
        assert 'Tu deuda (50%)' in msg
        assert 'Groceries' in msg
        assert 'Nu Savings' in msg

    def test_format_success_other_paid_no_category(self):
        expense = Expense(
            amount=Decimal('30000'), payee='Test', memo='test',
            account_name='Nu Savings',
            is_split=True, split_person='Maria',
            split_proportion=Decimal('0.5'),
            payer='other',
        )
        result = ExpenseResult.success_result(expense, 'txn-3')
        msg = ExpenseResponseFormatter.format_success(result)
        assert 'Maria' in msg
        assert 'Sin categoría' in msg

    def test_format_success_other_paid_does_not_show_splitwise_line(self):
        """Other-paid format should NOT show the 'Splitwise (x%)' line."""
        expense = Expense(
            amount=Decimal('50000'), payee='Test', memo='test',
            is_split=True, split_person='Eli',
            split_proportion=Decimal('0.5'),
            payer='other',
        )
        result = ExpenseResult.success_result(expense, 'txn-4')
        msg = ExpenseResponseFormatter.format_success(result)
        assert 'Splitwise' not in msg

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
        assert 'recibos/tickets' in msg.lower()

    def test_help_message(self):
        msg = GeneralResponseFormatter.format_help_message()
        assert 'Guía de uso' in msg
        assert '/connect' in msg
        assert '/config' in msg
        assert 'Aprendizaje' in msg
        assert '/corregir' in msg

    def test_format_onboarding_welcome(self):
        # NEEDS_YNAB_CONNECTION
        msg = GeneralResponseFormatter.format_onboarding_welcome("Emir", OnboardingStep.NEEDS_YNAB_CONNECTION)
        assert '¡Hola Emir!' in msg
        assert '/connect' in msg
        
        # NEEDS_BUDGET
        msg = GeneralResponseFormatter.format_onboarding_welcome("Emir", OnboardingStep.NEEDS_BUDGET)
        assert 'YNAB conectado' in msg
        assert 'selecciona el presupuesto' in msg
        
        # NEEDS_ACCOUNT
        msg = GeneralResponseFormatter.format_onboarding_welcome("Emir", OnboardingStep.NEEDS_ACCOUNT)
        assert 'Presupuesto seleccionado' in msg
        assert 'elige la cuenta' in msg
        
        # COMPLETE
        msg = GeneralResponseFormatter.format_onboarding_welcome("Emir", OnboardingStep.COMPLETE)
        assert '¡Todo listo, Emir!' in msg
        assert 'almuerzo 25000' in msg

    def test_format_post_oauth_message(self):
        msg = GeneralResponseFormatter.format_post_oauth_message()
        assert 'exitosamente' in msg
        assert 'configurar tu presupuesto' in msg

    def test_format_onboarding_complete(self):
        msg = GeneralResponseFormatter.format_onboarding_complete()
        assert 'Configuración completada' in msg
        assert 'comida 35000' in msg


# ---------------------------------------------------------------------------
# BudgetQueryFormatter
# ---------------------------------------------------------------------------

class TestBudgetQueryFormatter:

    def test_category_balance(self):
        result = BudgetQueryResult.success_result('category_balance', {
            'name': 'Groceries',
            'group_name': 'Essentials',
            'budgeted': 500000,
            'activity': -200000,
            'balance': 300000,
        })
        msg = BudgetQueryFormatter.format_response(result)
        assert 'Groceries' in msg
        assert 'Essentials' in msg
        assert '$500' in msg
        assert '$200' in msg
        assert '$300' in msg
        assert '✅' in msg

    def test_category_balance_negative(self):
        result = BudgetQueryResult.success_result('category_balance', {
            'name': 'Fun',
            'group_name': 'Optional',
            'budgeted': 100000,
            'activity': -150000,
            'balance': -50000,
        })
        msg = BudgetQueryFormatter.format_response(result)
        assert '🔴' in msg

    def test_account_balance(self):
        result = BudgetQueryResult.success_result('account_balance', {
            'name': 'Nu Card',
            'type': 'creditCard',
            'balance': -500000,
            'cleared_balance': -400000,
            'uncleared_balance': -100000,
        })
        msg = BudgetQueryFormatter.format_response(result)
        assert 'Nu Card' in msg
        assert '💸' in msg  # negative balance
        assert '$-500' in msg

    def test_account_balance_positive(self):
        result = BudgetQueryResult.success_result('account_balance', {
            'name': 'Cash',
            'type': 'cash',
            'balance': 200000,
            'cleared_balance': 200000,
            'uncleared_balance': 0,
        })
        msg = BudgetQueryFormatter.format_response(result)
        assert '💰' in msg

    def test_budget_summary(self):
        result = BudgetQueryResult.success_result('budget_summary', {
            'total_budgeted': 1000000,
            'total_activity': -430000,
            'total_balance': 570000,
            'category_count': 5,
            'top_spending': [
                {'name': 'Groceries', 'activity': -200000, 'balance': 300000},
                {'name': 'Restaurants', 'activity': -150000, 'balance': 150000},
            ],
        })
        msg = BudgetQueryFormatter.format_response(result)
        assert 'Resumen' in msg
        assert '$1,000' in msg
        assert '$430' in msg
        assert '$570' in msg
        assert 'Groceries' in msg
        assert 'Restaurants' in msg

    def test_budget_summary_no_spending(self):
        result = BudgetQueryResult.success_result('budget_summary', {
            'total_budgeted': 1000000,
            'total_activity': 0,
            'total_balance': 1000000,
            'category_count': 3,
            'top_spending': [],
        })
        msg = BudgetQueryFormatter.format_response(result)
        assert 'Top gastos' not in msg

    def test_error(self):
        result = BudgetQueryResult.error_result('category_balance', 'No encontré la categoría')
        msg = BudgetQueryFormatter.format_response(result)
        assert '❌' in msg
        assert 'No encontré' in msg

    def test_format_response_dispatches(self):
        result = BudgetQueryResult.success_result('account_balance', {
            'name': 'X', 'type': 'cash', 'balance': 0,
            'cleared_balance': 0, 'uncleared_balance': 0,
        })
        msg = BudgetQueryFormatter.format_response(result)
        assert 'Saldo' in msg


# ---------------------------------------------------------------------------
# SplitConfigResponseFormatter
# ---------------------------------------------------------------------------

class TestSplitConfigResponseFormatter:

    def test_format_split_panel(self):
        msg = SplitConfigResponseFormatter.format_split_panel()
        assert 'Gastos Compartidos' in msg
        assert 'Splitwise' in msg
        assert 'Selecciona una opción' in msg

    def test_format_split_summary_full(self, sample_split_groups, sample_shared_account):
        summary = {
            'groups': sample_split_groups,
            'shared_account': sample_shared_account,
            'configured': True
        }
        msg = SplitConfigResponseFormatter.format_split_summary(summary)
        assert 'Gastos Compartidos' in msg
        assert 'Juan' in msg
        assert 'Juancho' in msg
        assert 'Gastos con Juan' in msg
        assert 'Juan' in msg
        assert 'Nu Savings' in msg
        assert '50/50' in msg

    def test_format_split_summary_empty(self):
        summary = {
            'groups': [],
            'shared_account': None,
            'configured': False
        }
        msg = SplitConfigResponseFormatter.format_split_summary(summary)
        assert 'Ninguno configurado' in msg
        assert 'No configurada' in msg
        assert 'Nota:' in msg

    def test_format_group_added(self):
        msg = SplitConfigResponseFormatter.format_group_added('Gastos Compartidos')
        assert 'Gastos Compartidos' in msg
        assert 'agregado' in msg

    def test_format_group_removed(self):
        msg = SplitConfigResponseFormatter.format_group_removed('Gastos Compartidos')
        assert 'Gastos Compartidos' in msg
        assert 'eliminado' in msg

    def test_format_alias_added(self):
        msg = SplitConfigResponseFormatter.format_alias_added('Juancho', 'Gastos Compartidos')
        assert 'Juancho' in msg
        assert 'Gastos Compartidos' in msg
        assert 'agregado' in msg

    def test_format_alias_removed(self):
        msg = SplitConfigResponseFormatter.format_alias_removed('Juancho', 'Gastos Compartidos')
        assert 'Juancho' in msg
        assert 'Gastos Compartidos' in msg
        assert 'eliminado' in msg

    def test_format_shared_account_set(self):
        msg = SplitConfigResponseFormatter.format_shared_account_set('Nu Savings')
        assert 'Nu Savings' in msg
        assert 'configurada' in msg

    def test_format_shared_account_removed(self):
        msg = SplitConfigResponseFormatter.format_shared_account_removed()
        assert 'eliminada' in msg
        assert 'cuenta por defecto' in msg

    def test_format_no_budget_configured(self):
        msg = SplitConfigResponseFormatter.format_no_budget_configured()
        assert 'Presupuesto no configurado' in msg
        assert '/config' in msg

    def test_format_ask_alias(self):
        msg = SplitConfigResponseFormatter.format_ask_alias('Gastos Compartidos')
        assert 'alias' in msg
        assert 'Gastos Compartidos' in msg
        
        msg_no_group = SplitConfigResponseFormatter.format_ask_alias()
        assert 'alias' in msg_no_group


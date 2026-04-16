"""Tests for BudgetQueryService."""
import pytest

from application.services.budget_query_service import BudgetQueryService
from domain.models.user import YNABCategory, YNABAccount


@pytest.fixture
def service():
    return BudgetQueryService()


@pytest.fixture
def categories():
    return [
        YNABCategory(
            id='c1', name='Groceries', group_name='Essentials',
            full_name='Essentials → Groceries',
            budgeted=500000, activity=-200000, balance=300000,
        ),
        YNABCategory(
            id='c2', name='🍔 Restaurants', group_name='Essentials',
            full_name='Essentials → 🍔 Restaurants',
            budgeted=300000, activity=-150000, balance=150000,
        ),
        YNABCategory(
            id='c3', name='Transport', group_name='Essentials',
            full_name='Essentials → Transport',
            budgeted=200000, activity=-80000, balance=120000,
        ),
        YNABCategory(
            id='c4', name='Hidden Cat', group_name='Other',
            full_name='Other → Hidden Cat',
            budgeted=100000, activity=-50000, balance=50000,
            hidden=True,
        ),
        YNABCategory(
            id='c5', name='Deleted Cat', group_name='Other',
            full_name='Other → Deleted Cat',
            budgeted=100000, activity=0, balance=100000,
            deleted=True,
        ),
    ]


@pytest.fixture
def accounts():
    return [
        YNABAccount(
            id='a1', name='Nu Card', type='creditCard',
            balance=-500000, cleared_balance=-400000, uncleared_balance=-100000,
        ),
        YNABAccount(
            id='a2', name='Efectivo', type='cash',
            balance=200000, cleared_balance=200000, uncleared_balance=0,
        ),
        YNABAccount(
            id='a3', name='Closed Account', type='checking',
            balance=0, closed=True,
        ),
    ]


class TestCategoryBalance:

    def test_exact_match(self, service, categories, accounts):
        result = service.execute_query('category_balance', 'Groceries', categories, accounts)
        assert result.success is True
        assert result.data['name'] == 'Groceries'
        assert result.data['budgeted'] == 500000
        assert result.data['activity'] == -200000
        assert result.data['balance'] == 300000

    def test_case_insensitive(self, service, categories, accounts):
        result = service.execute_query('category_balance', 'groceries', categories, accounts)
        assert result.success is True
        assert result.data['name'] == 'Groceries'

    def test_partial_match(self, service, categories, accounts):
        result = service.execute_query('category_balance', 'Grocer', categories, accounts)
        assert result.success is True
        assert result.data['name'] == 'Groceries'

    def test_full_name_match(self, service, categories, accounts):
        result = service.execute_query('category_balance', 'Essentials → Groceries', categories, accounts)
        assert result.success is True
        assert result.data['name'] == 'Groceries'

    def test_clean_match_without_emoji(self, service, categories, accounts):
        result = service.execute_query('category_balance', 'Restaurants', categories, accounts)
        assert result.success is True
        assert result.data['name'] == '🍔 Restaurants'

    def test_not_found(self, service, categories, accounts):
        result = service.execute_query('category_balance', 'Nonexistent', categories, accounts)
        assert result.success is False
        assert 'No encontré' in result.error_message

    def test_no_target(self, service, categories, accounts):
        result = service.execute_query('category_balance', None, categories, accounts)
        assert result.success is False

    def test_hidden_excluded(self, service, categories, accounts):
        result = service.execute_query('category_balance', 'Hidden Cat', categories, accounts)
        assert result.success is False

    def test_deleted_excluded(self, service, categories, accounts):
        result = service.execute_query('category_balance', 'Deleted Cat', categories, accounts)
        assert result.success is False


class TestAccountBalance:

    def test_exact_match(self, service, categories, accounts):
        result = service.execute_query('account_balance', 'Nu Card', categories, accounts)
        assert result.success is True
        assert result.data['name'] == 'Nu Card'
        assert result.data['balance'] == -500000
        assert result.data['cleared_balance'] == -400000
        assert result.data['uncleared_balance'] == -100000

    def test_case_insensitive(self, service, categories, accounts):
        result = service.execute_query('account_balance', 'nu card', categories, accounts)
        assert result.success is True
        assert result.data['name'] == 'Nu Card'

    def test_partial_match(self, service, categories, accounts):
        result = service.execute_query('account_balance', 'Nu', categories, accounts)
        assert result.success is True
        assert result.data['name'] == 'Nu Card'

    def test_not_found(self, service, categories, accounts):
        result = service.execute_query('account_balance', 'Nonexistent', categories, accounts)
        assert result.success is False
        assert 'No encontré' in result.error_message

    def test_no_target(self, service, categories, accounts):
        result = service.execute_query('account_balance', None, categories, accounts)
        assert result.success is False

    def test_closed_excluded(self, service, categories, accounts):
        result = service.execute_query('account_balance', 'Closed Account', categories, accounts)
        assert result.success is False


class TestBudgetSummary:

    def test_summary_totals(self, service, categories, accounts):
        result = service.execute_query('budget_summary', None, categories, accounts)
        assert result.success is True
        # Only active categories (c1, c2, c3 — hidden and deleted excluded)
        assert result.data['total_budgeted'] == 1000000
        assert result.data['total_activity'] == -430000
        assert result.data['total_spent'] == 430000
        assert result.data['total_balance'] == 570000
        assert result.data['category_count'] == 3

    def test_top_spending(self, service, categories, accounts):
        result = service.execute_query('budget_summary', None, categories, accounts)
        top = result.data['top_spending']
        assert len(top) == 3
        # Fallback mode still orders by the largest category activity
        assert top[0]['name'] == 'Groceries'
        assert top[0]['spent'] == 200000

    def test_budget_summary_uses_transactions_for_spending_totals_and_top_categories(self, service, categories, accounts):
        result = service.execute_query(
            'budget_summary',
            None,
            categories,
            accounts,
            transactions=[
                {
                    'amount': -250000,
                    'date': '2026-04-03',
                    'category_name': 'Split (Multiple Categories)',
                    'subtransactions': [
                        {'amount': -120000, 'category_name': 'Groceries'},
                        {'amount': -130000, 'category_name': '🍔 Restaurants'},
                    ],
                },
                {
                    'amount': -150000,
                    'date': '2026-04-10',
                    'category_name': 'Groceries',
                },
            ],
        )

        assert result.data['total_spent'] == 400000
        assert result.data['top_spending'][0] == {
            'name': 'Groceries',
            'spent': 270000,
            'balance': 300000,
        }


class TestInvalidQueryType:

    def test_unknown_type(self, service, categories, accounts):
        result = service.execute_query('unknown', None, categories, accounts)
        assert result.success is False
        assert 'no soportado' in result.error_message

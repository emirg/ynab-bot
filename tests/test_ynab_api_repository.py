"""Tests for YNABApiRepository with mocked HTTP."""
import time
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from infrastructure.repositories.ynab_api_repository import YNABApiRepository, _CACHE_TTL_SECONDS
from domain.models.expense import Expense
from domain.exceptions import YNABApiException


@pytest.fixture
def repo():
    return YNABApiRepository(access_token='test-token')


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.text = ''
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class TestCache:

    def test_get_cached_miss(self, repo):
        assert repo._get_cached('nonexistent') is None

    def test_set_and_get_cached(self, repo):
        repo._set_cached('key1', [1, 2, 3])
        assert repo._get_cached('key1') == [1, 2, 3]

    def test_cache_expires(self, repo):
        repo._cache['key1'] = (time.monotonic() - _CACHE_TTL_SECONDS - 1, 'stale')
        assert repo._get_cached('key1') is None


# ---------------------------------------------------------------------------
# get_budgets
# ---------------------------------------------------------------------------

class TestGetBudgets:

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_returns_budgets(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'budgets': [
                {'id': 'b1', 'name': 'My Budget', 'currency_format': {'iso_code': 'COP'}},
            ]}
        })
        budgets = repo.get_budgets()
        assert len(budgets) == 1
        assert budgets[0].id == 'b1'
        mock_get.assert_called_once()

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_raises_on_error(self, mock_get, repo):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError('timeout')
        with pytest.raises(YNABApiException):
            repo.get_budgets()


# ---------------------------------------------------------------------------
# get_accounts (with caching)
# ---------------------------------------------------------------------------

class TestGetAccounts:

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_returns_active_accounts(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'accounts': [
                {'id': 'a1', 'name': 'Nu', 'type': 'credit', 'deleted': False, 'closed': False},
                {'id': 'a2', 'name': 'Old', 'type': 'checking', 'deleted': False, 'closed': True},
                {'id': 'a3', 'name': 'Gone', 'type': 'checking', 'deleted': True, 'closed': False},
            ]}
        })
        accounts = repo.get_accounts('budget-1')
        assert len(accounts) == 1
        assert accounts[0].id == 'a1'

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_caches_result(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'accounts': [
                {'id': 'a1', 'name': 'Nu', 'type': 'credit'},
            ]}
        })
        repo.get_accounts('budget-1')
        repo.get_accounts('budget-1')  # second call should use cache
        assert mock_get.call_count == 1

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_raises_on_error(self, mock_get, repo):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError('timeout')
        with pytest.raises(YNABApiException):
            repo.get_accounts('budget-1')


# ---------------------------------------------------------------------------
# get_categories (with caching)
# ---------------------------------------------------------------------------

class TestGetCategories:

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_returns_non_deleted_categories(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'category_groups': [
                {
                    'name': 'Essentials',
                    'categories': [
                        {'id': 'c1', 'name': 'Groceries', 'deleted': False},
                        {'id': 'c2', 'name': 'Old', 'deleted': True},
                    ]
                }
            ]}
        })
        cats = repo.get_categories('budget-1')
        assert len(cats) == 1
        assert cats[0].name == 'Groceries'
        assert cats[0].group_name == 'Essentials'

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_caches_result(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'category_groups': [
                {'name': 'G', 'categories': [{'id': 'c1', 'name': 'C'}]}
            ]}
        })
        repo.get_categories('budget-1')
        repo.get_categories('budget-1')
        assert mock_get.call_count == 1

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_different_budgets_cached_separately(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'category_groups': [
                {'name': 'G', 'categories': [{'id': 'c1', 'name': 'C'}]}
            ]}
        })
        repo.get_categories('budget-1')
        repo.get_categories('budget-2')
        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# create_transaction
# ---------------------------------------------------------------------------

class TestCreateTransaction:

    @patch('infrastructure.repositories.ynab_api_repository.requests.post')
    def test_success(self, mock_post, repo):
        mock_post.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1'}}}, status_code=201
        )
        expense = Expense(
            amount=Decimal('25000'), payee='Test', memo='x',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            confidence=0.9,
        )
        txn_id = repo.create_transaction(expense, 'budget-1', 'acc-1')
        assert txn_id == 'txn-1'

    @patch('infrastructure.repositories.ynab_api_repository.requests.post')
    def test_http_error(self, mock_post, repo):
        resp = _mock_response({'error': 'bad'}, status_code=400)
        resp.status_code = 400
        mock_post.return_value = resp
        expense = Expense(
            amount=Decimal('25000'), payee='Test', memo='x', confidence=0.9,
        )
        with pytest.raises(YNABApiException):
            repo.create_transaction(expense, 'budget-1', 'acc-1')

    def test_invalid_expense_raises(self, repo):
        expense = Expense(amount=Decimal('0'), payee='', memo='x')
        with pytest.raises(YNABApiException, match='Invalid expense'):
            repo.create_transaction(expense, 'budget-1', 'acc-1')

    @patch('infrastructure.repositories.ynab_api_repository.requests.post')
    def test_network_error(self, mock_post, repo):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError('network')
        expense = Expense(
            amount=Decimal('25000'), payee='Test', memo='x', confidence=0.9,
        )
        with pytest.raises(YNABApiException):
            repo.create_transaction(expense, 'budget-1', 'acc-1')

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
# get_payees (with caching)
# ---------------------------------------------------------------------------

class TestGetPayees:

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_returns_non_deleted_payees(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'payees': [
                {'id': 'p1', 'name': 'Carulla', 'deleted': False},
                {'id': 'p2', 'name': 'OldStore', 'deleted': True},
                {'id': 'p3', 'name': 'Rappi', 'deleted': False},
            ]}
        })
        payees = repo.get_payees('budget-1')
        assert len(payees) == 2
        ids = {p.id for p in payees}
        assert 'p1' in ids
        assert 'p3' in ids
        assert 'p2' not in ids

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_returned_payees_have_correct_attributes(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'payees': [
                {'id': 'p1', 'name': 'Carulla', 'deleted': False},
            ]}
        })
        payees = repo.get_payees('budget-1')
        assert payees[0].name == 'Carulla'
        assert payees[0].deleted is False

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_caches_result(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'payees': [
                {'id': 'p1', 'name': 'Carulla', 'deleted': False},
            ]}
        })
        repo.get_payees('budget-1')
        repo.get_payees('budget-1')  # second call must use cache
        assert mock_get.call_count == 1

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_different_budgets_cached_separately(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'payees': [{'id': 'p1', 'name': 'X', 'deleted': False}]}
        })
        repo.get_payees('budget-1')
        repo.get_payees('budget-2')
        assert mock_get.call_count == 2

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_expired_cache_refetches(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'payees': [{'id': 'p1', 'name': 'X', 'deleted': False}]}
        })
        # Manually plant a stale cache entry
        repo._cache['payees:budget-1'] = (time.monotonic() - _CACHE_TTL_SECONDS - 1, [])
        repo.get_payees('budget-1')
        assert mock_get.call_count == 1

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_raises_on_network_error(self, mock_get, repo):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError('timeout')
        with pytest.raises(YNABApiException):
            repo.get_payees('budget-1')

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_empty_payee_list(self, mock_get, repo):
        mock_get.return_value = _mock_response({'data': {'payees': []}})
        payees = repo.get_payees('budget-1')
        assert payees == []

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_calls_correct_endpoint(self, mock_get, repo):
        mock_get.return_value = _mock_response({'data': {'payees': []}})
        repo.get_payees('my-budget-id')
        called_url = mock_get.call_args[0][0]
        assert 'my-budget-id' in called_url
        assert 'payees' in called_url


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


# ---------------------------------------------------------------------------
# get_transactions
# ---------------------------------------------------------------------------

class TestGetTransactions:

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_returns_non_deleted_transactions(self, mock_get, repo):
        mock_get.return_value = _mock_response({
            'data': {'transactions': [
                {'id': 't1', 'amount': -50000, 'category_name': 'Groceries', 'date': '2026-03-10', 'deleted': False, 'payee_name': 'Carulla'},
                {'id': 't2', 'amount': -20000, 'category_name': 'Transport', 'date': '2026-03-11', 'deleted': True, 'payee_name': 'Uber'},
                {'id': 't3', 'amount': -30000, 'category_name': 'Dining', 'date': '2026-03-12', 'deleted': False, 'payee_name': 'Subway'},
            ]}
        })
        result = repo.get_transactions('budget-1', '2026-03-10')
        assert len(result) == 2
        ids = {t['id'] for t in result}
        assert 't1' in ids
        assert 't3' in ids
        assert 't2' not in ids

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_passes_since_date_as_query_param(self, mock_get, repo):
        mock_get.return_value = _mock_response({'data': {'transactions': []}})
        repo.get_transactions('budget-1', '2026-03-03')
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params'] == {'since_date': '2026-03-03'}

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_uses_correct_endpoint(self, mock_get, repo):
        mock_get.return_value = _mock_response({'data': {'transactions': []}})
        repo.get_transactions('my-budget-id', '2026-03-03')
        called_url = mock_get.call_args[0][0]
        assert 'my-budget-id' in called_url
        assert 'transactions' in called_url

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_returns_empty_list_when_no_transactions(self, mock_get, repo):
        mock_get.return_value = _mock_response({'data': {'transactions': []}})
        result = repo.get_transactions('budget-1', '2026-03-03')
        assert result == []

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_raises_on_network_error(self, mock_get, repo):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError('timeout')
        with pytest.raises(YNABApiException):
            repo.get_transactions('budget-1', '2026-03-03')

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_no_caching_second_call_hits_api(self, mock_get, repo):
        mock_get.return_value = _mock_response({'data': {'transactions': []}})
        repo.get_transactions('budget-1', '2026-03-03')
        repo.get_transactions('budget-1', '2026-03-03')
        assert mock_get.call_count == 2

    @patch('infrastructure.repositories.ynab_api_repository.requests.get')
    def test_returns_full_transaction_dicts(self, mock_get, repo):
        txn = {'id': 't1', 'amount': -50000, 'category_name': 'Groceries', 'date': '2026-03-10', 'deleted': False, 'payee_name': 'Carulla'}
        mock_get.return_value = _mock_response({'data': {'transactions': [txn]}})
        result = repo.get_transactions('budget-1', '2026-03-10')
        assert result[0] == txn


# ---------------------------------------------------------------------------
# update_transaction_category
# ---------------------------------------------------------------------------

class TestUpdateTransactionCategory:

    @patch('infrastructure.repositories.ynab_api_repository.requests.put')
    def test_success(self, mock_put, repo):
        mock_put.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1', 'category_id': 'cat-new'}}},
            status_code=200,
        )
        result = repo.update_transaction_category('budget-1', 'txn-1', 'cat-new')
        assert result is True
        mock_put.assert_called_once()
        call_args = mock_put.call_args
        assert 'txn-1' in call_args[0][0]
        assert call_args[1]['json'] == {'transaction': {'category_id': 'cat-new'}}

    @patch('infrastructure.repositories.ynab_api_repository.requests.put')
    def test_http_error_returns_false(self, mock_put, repo):
        mock_put.return_value = _mock_response({'error': 'bad'}, status_code=400)
        result = repo.update_transaction_category('budget-1', 'txn-1', 'cat-new')
        assert result is False

    @patch('infrastructure.repositories.ynab_api_repository.requests.put')
    def test_network_error_returns_false(self, mock_put, repo):
        import requests as req
        mock_put.side_effect = req.exceptions.ConnectionError('timeout')
        result = repo.update_transaction_category('budget-1', 'txn-1', 'cat-new')
        assert result is False

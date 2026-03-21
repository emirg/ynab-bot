"""Tests for YNABApiRepository with mocked ResilientHTTPClient."""
import time
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from infrastructure.repositories.ynab_api_repository import YNABApiRepository, YNABRepositoryFactory, _CACHE_TTL_SECONDS
from infrastructure.http_client import ResilientHTTPClient
from domain.models.expense import Expense
from domain.exceptions import YNABApiException, OAuthException


def _make_client():
    """Return a MagicMock that acts as a ResilientHTTPClient."""
    return MagicMock(spec=ResilientHTTPClient)


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.text = ''
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def client():
    return _make_client()


@pytest.fixture
def repo(client):
    return YNABApiRepository(client)


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

    def test_returns_budgets(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'budgets': [
                {'id': 'b1', 'name': 'My Budget', 'currency_format': {'iso_code': 'COP'}},
            ]}
        })
        budgets = repo.get_budgets()
        assert len(budgets) == 1
        assert budgets[0].id == 'b1'
        client.get.assert_called_once_with('/budgets')

    def test_raises_on_error(self, repo, client):
        client.get.side_effect = YNABApiException("Network error", status_code=None)
        with pytest.raises(YNABApiException):
            repo.get_budgets()


# ---------------------------------------------------------------------------
# get_accounts (with caching)
# ---------------------------------------------------------------------------

class TestGetAccounts:

    def test_returns_active_accounts(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'accounts': [
                {'id': 'a1', 'name': 'Nu', 'type': 'credit', 'deleted': False, 'closed': False},
                {'id': 'a2', 'name': 'Old', 'type': 'checking', 'deleted': False, 'closed': True},
                {'id': 'a3', 'name': 'Gone', 'type': 'checking', 'deleted': True, 'closed': False},
            ]}
        })
        accounts = repo.get_accounts('budget-1')
        assert len(accounts) == 1
        assert accounts[0].id == 'a1'

    def test_caches_result(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'accounts': [
                {'id': 'a1', 'name': 'Nu', 'type': 'credit'},
            ]}
        })
        repo.get_accounts('budget-1')
        repo.get_accounts('budget-1')  # second call should use cache
        assert client.get.call_count == 1

    def test_raises_on_error(self, repo, client):
        client.get.side_effect = YNABApiException("Network error", status_code=None)
        with pytest.raises(YNABApiException):
            repo.get_accounts('budget-1')


# ---------------------------------------------------------------------------
# get_categories (with caching)
# ---------------------------------------------------------------------------

class TestGetCategories:

    def test_returns_non_deleted_categories(self, repo, client):
        client.get.return_value = _mock_response({
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

    def test_caches_result(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'category_groups': [
                {'name': 'G', 'categories': [{'id': 'c1', 'name': 'C'}]}
            ]}
        })
        repo.get_categories('budget-1')
        repo.get_categories('budget-1')
        assert client.get.call_count == 1

    def test_different_budgets_cached_separately(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'category_groups': [
                {'name': 'G', 'categories': [{'id': 'c1', 'name': 'C'}]}
            ]}
        })
        repo.get_categories('budget-1')
        repo.get_categories('budget-2')
        assert client.get.call_count == 2


# ---------------------------------------------------------------------------
# get_payees (with caching)
# ---------------------------------------------------------------------------

class TestGetPayees:

    def test_returns_non_deleted_payees(self, repo, client):
        client.get.return_value = _mock_response({
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

    def test_returned_payees_have_correct_attributes(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'payees': [
                {'id': 'p1', 'name': 'Carulla', 'deleted': False},
            ]}
        })
        payees = repo.get_payees('budget-1')
        assert payees[0].name == 'Carulla'
        assert payees[0].deleted is False

    def test_caches_result(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'payees': [
                {'id': 'p1', 'name': 'Carulla', 'deleted': False},
            ]}
        })
        repo.get_payees('budget-1')
        repo.get_payees('budget-1')  # second call must use cache
        assert client.get.call_count == 1

    def test_different_budgets_cached_separately(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'payees': [{'id': 'p1', 'name': 'X', 'deleted': False}]}
        })
        repo.get_payees('budget-1')
        repo.get_payees('budget-2')
        assert client.get.call_count == 2

    def test_expired_cache_refetches(self, repo, client):
        client.get.return_value = _mock_response({
            'data': {'payees': [{'id': 'p1', 'name': 'X', 'deleted': False}]}
        })
        # Manually plant a stale cache entry
        repo._cache['payees:budget-1'] = (time.monotonic() - _CACHE_TTL_SECONDS - 1, [])
        repo.get_payees('budget-1')
        assert client.get.call_count == 1

    def test_raises_on_network_error(self, repo, client):
        client.get.side_effect = YNABApiException("Network error", status_code=None)
        with pytest.raises(YNABApiException):
            repo.get_payees('budget-1')

    def test_empty_payee_list(self, repo, client):
        client.get.return_value = _mock_response({'data': {'payees': []}})
        payees = repo.get_payees('budget-1')
        assert payees == []

    def test_calls_correct_endpoint(self, repo, client):
        client.get.return_value = _mock_response({'data': {'payees': []}})
        repo.get_payees('my-budget-id')
        called_path = client.get.call_args[0][0]
        assert 'my-budget-id' in called_path
        assert 'payees' in called_path


# ---------------------------------------------------------------------------
# create_transaction
# ---------------------------------------------------------------------------

class TestCreateTransaction:

    def test_success(self, repo, client):
        client.post.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1'}}}, status_code=201
        )
        expense = Expense(
            amount=Decimal('25000'), payee='Test', memo='x',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            confidence=0.9,
        )
        txn_id = repo.create_transaction(expense, 'budget-1', 'acc-1')
        assert txn_id == 'txn-1'

    def test_http_error(self, repo, client):
        resp = _mock_response({'error': 'bad'}, status_code=400)
        resp.status_code = 400
        client.post.return_value = resp
        expense = Expense(
            amount=Decimal('25000'), payee='Test', memo='x', confidence=0.9,
        )
        with pytest.raises(YNABApiException):
            repo.create_transaction(expense, 'budget-1', 'acc-1')

    def test_invalid_expense_raises(self, repo):
        expense = Expense(amount=Decimal('0'), payee='', memo='x')
        with pytest.raises(YNABApiException, match='Invalid expense'):
            repo.create_transaction(expense, 'budget-1', 'acc-1')

    def test_network_error(self, repo, client):
        client.post.side_effect = YNABApiException("Network error after retries", status_code=None)
        expense = Expense(
            amount=Decimal('25000'), payee='Test', memo='x', confidence=0.9,
        )
        with pytest.raises(YNABApiException):
            repo.create_transaction(expense, 'budget-1', 'acc-1')


# ---------------------------------------------------------------------------
# get_transactions
# ---------------------------------------------------------------------------

class TestGetTransactions:

    def test_returns_non_deleted_transactions(self, repo, client):
        client.get.return_value = _mock_response({
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

    def test_passes_since_date_as_query_param(self, repo, client):
        client.get.return_value = _mock_response({'data': {'transactions': []}})
        repo.get_transactions('budget-1', '2026-03-03')
        call_kwargs = client.get.call_args[1]
        assert call_kwargs['params'] == {'since_date': '2026-03-03'}

    def test_uses_correct_endpoint(self, repo, client):
        client.get.return_value = _mock_response({'data': {'transactions': []}})
        repo.get_transactions('my-budget-id', '2026-03-03')
        called_path = client.get.call_args[0][0]
        assert 'my-budget-id' in called_path
        assert 'transactions' in called_path

    def test_returns_empty_list_when_no_transactions(self, repo, client):
        client.get.return_value = _mock_response({'data': {'transactions': []}})
        result = repo.get_transactions('budget-1', '2026-03-03')
        assert result == []

    def test_raises_on_network_error(self, repo, client):
        client.get.side_effect = YNABApiException("Network error after retries", status_code=None)
        with pytest.raises(YNABApiException):
            repo.get_transactions('budget-1', '2026-03-03')

    def test_no_caching_second_call_hits_api(self, repo, client):
        client.get.return_value = _mock_response({'data': {'transactions': []}})
        repo.get_transactions('budget-1', '2026-03-03')
        repo.get_transactions('budget-1', '2026-03-03')
        assert client.get.call_count == 2

    def test_returns_full_transaction_dicts(self, repo, client):
        txn = {'id': 't1', 'amount': -50000, 'category_name': 'Groceries', 'date': '2026-03-10', 'deleted': False, 'payee_name': 'Carulla'}
        client.get.return_value = _mock_response({'data': {'transactions': [txn]}})
        result = repo.get_transactions('budget-1', '2026-03-10')
        assert result[0] == txn


# ---------------------------------------------------------------------------
# delete_transaction
# ---------------------------------------------------------------------------

class TestDeleteTransaction:

    def test_success_200(self, repo, client):
        client.delete.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1', 'deleted': True}}},
            status_code=200,
        )
        result = repo.delete_transaction('budget-1', 'txn-1')
        assert result is True
        client.delete.assert_called_once_with('/budgets/budget-1/transactions/txn-1')

    def test_success_201(self, repo, client):
        client.delete.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1', 'deleted': True}}},
            status_code=201,
        )
        result = repo.delete_transaction('budget-1', 'txn-1')
        assert result is True

    def test_http_400_returns_false(self, repo, client):
        client.delete.return_value = _mock_response({'error': 'bad request'}, status_code=400)
        result = repo.delete_transaction('budget-1', 'txn-1')
        assert result is False

    def test_http_404_returns_false(self, repo, client):
        client.delete.return_value = _mock_response({'error': 'not found'}, status_code=404)
        result = repo.delete_transaction('budget-1', 'txn-1')
        assert result is False

    def test_ynab_api_exception_returns_false(self, repo, client):
        client.delete.side_effect = YNABApiException("Network error after retries", status_code=None)
        result = repo.delete_transaction('budget-1', 'txn-1')
        assert result is False

    def test_generic_exception_returns_false(self, repo, client):
        client.delete.side_effect = RuntimeError("Unexpected failure")
        result = repo.delete_transaction('budget-1', 'txn-1')
        assert result is False

    def test_uses_correct_endpoint(self, repo, client):
        client.delete.return_value = _mock_response({}, status_code=200)
        repo.delete_transaction('my-budget-id', 'my-txn-id')
        called_path = client.delete.call_args[0][0]
        assert 'my-budget-id' in called_path
        assert 'my-txn-id' in called_path
        assert 'transactions' in called_path


# ---------------------------------------------------------------------------
# update_transaction
# ---------------------------------------------------------------------------

class TestUpdateTransaction:

    def test_success_amount_only(self, repo, client):
        client.put.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1', 'amount': -30000000}}},
            status_code=200,
        )
        result = repo.update_transaction('budget-1', 'txn-1', {'amount': -30000000})
        assert result is True
        client.put.assert_called_once()
        call_args = client.put.call_args
        assert 'txn-1' in call_args[0][0]
        assert call_args[1]['json'] == {'transaction': {'amount': -30000000}}

    def test_success_payee_only(self, repo, client):
        client.put.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1', 'payee_name': "McDonald's"}}},
            status_code=200,
        )
        result = repo.update_transaction('budget-1', 'txn-1', {'payee_name': "McDonald's"})
        assert result is True
        call_args = client.put.call_args
        assert call_args[1]['json'] == {'transaction': {'payee_name': "McDonald's"}}

    def test_success_category_id_only(self, repo, client):
        client.put.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1', 'category_id': 'cat-new'}}},
            status_code=200,
        )
        result = repo.update_transaction('budget-1', 'txn-1', {'category_id': 'cat-new'})
        assert result is True
        call_args = client.put.call_args
        assert call_args[1]['json'] == {'transaction': {'category_id': 'cat-new'}}

    def test_success_account_id_only(self, repo, client):
        client.put.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1', 'account_id': 'acc-2'}}},
            status_code=200,
        )
        result = repo.update_transaction('budget-1', 'txn-1', {'account_id': 'acc-2'})
        assert result is True
        call_args = client.put.call_args
        assert call_args[1]['json'] == {'transaction': {'account_id': 'acc-2'}}

    def test_success_all_fields_combined(self, repo, client):
        fields = {
            'amount': -30000000,
            'payee_name': "McDonald's",
            'category_id': 'cat-new',
            'account_id': 'acc-2',
        }
        client.put.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1'}}},
            status_code=201,
        )
        result = repo.update_transaction('budget-1', 'txn-1', fields)
        assert result is True
        call_args = client.put.call_args
        assert call_args[1]['json'] == {'transaction': fields}

    def test_uses_correct_endpoint(self, repo, client):
        client.put.return_value = _mock_response({}, status_code=200)
        repo.update_transaction('my-budget-id', 'my-txn-id', {'amount': -10000})
        called_path = client.put.call_args[0][0]
        assert 'my-budget-id' in called_path
        assert 'my-txn-id' in called_path
        assert 'transactions' in called_path

    def test_http_400_returns_false(self, repo, client):
        client.put.return_value = _mock_response({'error': 'bad request'}, status_code=400)
        result = repo.update_transaction('budget-1', 'txn-1', {'amount': -10000})
        assert result is False

    def test_http_404_returns_false(self, repo, client):
        client.put.return_value = _mock_response({'error': 'not found'}, status_code=404)
        result = repo.update_transaction('budget-1', 'txn-1', {'category_id': 'cat-1'})
        assert result is False

    def test_ynab_api_exception_returns_false(self, repo, client):
        client.put.side_effect = YNABApiException("Network error after retries", status_code=None)
        result = repo.update_transaction('budget-1', 'txn-1', {'amount': -10000})
        assert result is False

    def test_generic_exception_returns_false(self, repo, client):
        client.put.side_effect = RuntimeError("Unexpected failure")
        result = repo.update_transaction('budget-1', 'txn-1', {'amount': -10000})
        assert result is False


# ---------------------------------------------------------------------------
# update_transaction_category
# ---------------------------------------------------------------------------

class TestUpdateTransactionCategory:

    def test_success(self, repo, client):
        client.put.return_value = _mock_response(
            {'data': {'transaction': {'id': 'txn-1', 'category_id': 'cat-new'}}},
            status_code=200,
        )
        result = repo.update_transaction_category('budget-1', 'txn-1', 'cat-new')
        assert result is True
        client.put.assert_called_once()
        call_args = client.put.call_args
        assert 'txn-1' in call_args[0][0]
        assert call_args[1]['json'] == {'transaction': {'category_id': 'cat-new'}}

    def test_http_error_returns_false(self, repo, client):
        client.put.return_value = _mock_response({'error': 'bad'}, status_code=400)
        result = repo.update_transaction_category('budget-1', 'txn-1', 'cat-new')
        assert result is False

    def test_network_error_returns_false(self, repo, client):
        client.put.side_effect = YNABApiException("Network error after retries", status_code=None)
        result = repo.update_transaction_category('budget-1', 'txn-1', 'cat-new')
        assert result is False


# ---------------------------------------------------------------------------
# YNABRepositoryFactory
# ---------------------------------------------------------------------------

class TestYNABRepositoryFactory:

    def test_raises_when_no_token(self):
        mock_oauth = MagicMock()
        factory = YNABRepositoryFactory(oauth_service=mock_oauth)
        mock_user_config = MagicMock()
        mock_user_config.has_ynab_token.return_value = False
        with pytest.raises(OAuthException):
            factory.get_repository(mock_user_config)

    def test_creates_repository_with_resilient_client(self):
        mock_oauth = MagicMock()
        mock_oauth.get_valid_access_token.return_value = "test-token-123"
        factory = YNABRepositoryFactory(oauth_service=mock_oauth)
        mock_user_config = MagicMock()
        mock_user_config.has_ynab_token.return_value = True

        repo = factory.get_repository(mock_user_config)

        assert isinstance(repo, YNABApiRepository)
        assert isinstance(repo.client, ResilientHTTPClient)

    def test_factory_injects_token_into_client(self):
        mock_oauth = MagicMock()
        mock_oauth.get_valid_access_token.return_value = "my-secret-token"
        factory = YNABRepositoryFactory(oauth_service=mock_oauth)
        mock_user_config = MagicMock()
        mock_user_config.has_ynab_token.return_value = True

        repo = factory.get_repository(mock_user_config)

        # Verify the client has the auth header set (via session headers)
        auth_header = repo.client._session.headers.get("Authorization")
        assert auth_header == "Bearer my-secret-token"

    def test_factory_sets_correct_base_url(self):
        mock_oauth = MagicMock()
        mock_oauth.get_valid_access_token.return_value = "test-token"
        factory = YNABRepositoryFactory(oauth_service=mock_oauth)
        mock_user_config = MagicMock()
        mock_user_config.has_ynab_token.return_value = True

        repo = factory.get_repository(mock_user_config)

        assert repo.client._base_url == "https://api.ynab.com/v1"

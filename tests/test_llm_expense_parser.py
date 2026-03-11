"""Tests for LLMExpenseParser.parse_message() intent classification."""
import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_openai_client():
    with patch('parsers.llm_expense_parser.OpenAI') as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.fixture
def parser(mock_openai_client):
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        from parsers.llm_expense_parser import LLMExpenseParser
        p = LLMExpenseParser(
            ynab_categories=[{'name': 'Groceries'}, {'name': 'Restaurants'}],
            ynab_accounts=['Nu Card', 'Efectivo'],
        )
        return p


def _mock_response(client, content: str):
    """Helper to set up a mock OpenAI response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    client.chat.completions.create.return_value = mock_resp


class TestParseMessageQuery:

    def test_category_balance_query(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'query',
            'query_type': 'category_balance',
            'query_target': 'Groceries',
            'confidence': 0.9,
        })
        _mock_response(mock_openai_client, response)

        result = parser.parse_message('¿Cuánto me queda en Groceries?')
        assert result['intent'] == 'query'
        assert result['query_type'] == 'category_balance'
        assert result['query_target'] == 'Groceries'
        assert result['confidence'] == 0.9

    def test_account_balance_query(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'query',
            'query_type': 'account_balance',
            'query_target': 'Nu Card',
            'confidence': 0.85,
        })
        _mock_response(mock_openai_client, response)

        result = parser.parse_message('¿Cuánto debo en mi Nu Card?')
        assert result['intent'] == 'query'
        assert result['query_type'] == 'account_balance'
        assert result['query_target'] == 'Nu Card'

    def test_budget_summary_query(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'query',
            'query_type': 'budget_summary',
            'query_target': None,
            'confidence': 0.8,
        })
        _mock_response(mock_openai_client, response)

        result = parser.parse_message('¿Cómo va mi presupuesto?')
        assert result['intent'] == 'query'
        assert result['query_type'] == 'budget_summary'


class TestParseMessageExpense:

    def test_expense_intent(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': '25 lucas almuerzo',
            'confidence': 0.85,
        })
        _mock_response(mock_openai_client, response)

        result = parser.parse_message('25 lucas almuerzo')
        assert result['intent'] == 'expense'
        assert result['amount'] == 25000.0
        assert result['category'] == 'Restaurants'


class TestParseMessageErrors:

    def test_invalid_json(self, parser, mock_openai_client):
        _mock_response(mock_openai_client, 'not json')
        assert parser.parse_message('test') is None

    def test_missing_intent(self, parser, mock_openai_client):
        _mock_response(mock_openai_client, json.dumps({'confidence': 0.9}))
        assert parser.parse_message('test') is None

    def test_missing_confidence(self, parser, mock_openai_client):
        _mock_response(mock_openai_client, json.dumps({'intent': 'query'}))
        assert parser.parse_message('test') is None

    def test_invalid_confidence(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'query', 'query_type': 'budget_summary',
            'query_target': None, 'confidence': 1.5,
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None

    def test_invalid_query_type(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'query', 'query_type': 'invalid',
            'query_target': None, 'confidence': 0.9,
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None

    def test_unknown_intent(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'unknown', 'confidence': 0.9,
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None

    def test_expense_missing_amount(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'expense', 'category': 'Groceries',
            'payee': 'Test', 'memo': 'test', 'confidence': 0.9,
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None

    def test_expense_invalid_amount(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'expense', 'amount': -100,
            'category': 'Groceries', 'payee': 'Test',
            'memo': 'test', 'confidence': 0.9,
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None

    def test_api_error(self, parser, mock_openai_client):
        mock_openai_client.chat.completions.create.side_effect = Exception('API error')
        assert parser.parse_message('test') is None

    def test_query_missing_query_type(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'query', 'query_target': 'Groceries',
            'confidence': 0.9,
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None


class TestParseExpenseUnchanged:
    """Verify parse_expense() still works independently."""

    def test_parse_expense_still_works(self, parser, mock_openai_client):
        response = json.dumps({
            'amount': 25000.0, 'category': 'Restaurants',
            'payee': "McDonald's", 'account': None,
            'memo': 'test', 'confidence': 0.85,
        })
        _mock_response(mock_openai_client, response)

        result = parser.parse_expense('25 lucas almuerzo')
        assert result is not None
        assert result['amount'] == 25000.0

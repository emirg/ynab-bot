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

    def test_markdown_json(self, parser, mock_openai_client):
        response = "```json\n{\"intent\": \"expense\", \"amount\": 100, \"category\": \"C\", \"payee\": \"P\", \"memo\": \"M\", \"confidence\": 0.9}\n```"
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('test')
        assert result is not None
        assert result['intent'] == 'expense'
        assert result['amount'] == 100.0

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


class TestParseMessageSharedExpense:

    def test_valid_shared_expense(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo mitad 50k con Juan',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': '1/2',
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('almuerzo mitad 50k con Juan')
        assert result['intent'] == 'shared_expense'
        assert result['amount'] == 50000.0
        assert result['person'] == 'Juan'
        assert result['proportion'] == '1/2'

    def test_missing_person_returns_none(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.9,
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None

    def test_empty_person_returns_none(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.9,
            'person': '  ',
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None

    def test_null_proportion_accepted(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': None,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('test')
        assert result is not None
        assert result['proportion'] is None

    def test_invalid_amount_returns_none(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': -100,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.9,
            'person': 'Juan',
        })
        _mock_response(mock_openai_client, response)
        assert parser.parse_message('test') is None

    def test_payer_other_is_preserved(self, parser, mock_openai_client):
        """When LLM returns payer='other', it must be preserved in the result."""
        response = json.dumps({
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
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('Eli gastó 50k en carulla conmigo')
        assert result is not None
        assert result['payer'] == 'other'
        assert result['person'] == 'Eli'

    def test_payer_user_is_preserved(self, parser, mock_openai_client):
        """When LLM returns payer='user', it must be preserved."""
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo a medias con Juan',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': '1/2',
            'payer': 'user',
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('almuerzo a medias con Juan')
        assert result is not None
        assert result['payer'] == 'user'

    def test_payer_defaults_to_user_when_missing(self, parser, mock_openai_client):
        """When LLM omits payer field, it should default to 'user'."""
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': None,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('test')
        assert result is not None
        assert result['payer'] == 'user'

    def test_payer_invalid_value_defaults_to_user(self, parser, mock_openai_client):
        """When LLM returns an invalid payer value, it should default to 'user'."""
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'test',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': None,
            'payer': 'someone_else',
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('test')
        assert result is not None
        assert result['payer'] == 'user'


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


class TestParseReceiptImage:

    def test_parse_receipt_image_success(self, parser, mock_openai_client):
        response = json.dumps({
            'amount': 45000.0,
            'category': 'Restaurants',
            'payee': 'El Corral',
            'account': 'Nu Card',
            'memo': '[10/03] Almuerzo combo hamburguesa',
            'confidence': 0.95,
            'required_fields_check': True  # Solo para que no falle validación si cambio algo
        })
        # Limpiar campos extras para coincidir con required_fields
        response_dict = json.loads(response)
        if 'required_fields_check' in response_dict: del response_dict['required_fields_check']
        
        _mock_response(mock_openai_client, json.dumps(response_dict))

        result = parser.parse_receipt_image('base64_string', 'almuerzo con amigos')
        
        assert result is not None
        assert result['amount'] == 45000.0
        assert result['payee'] == 'El Corral'
        assert result['confidence'] == 0.95
        
        # Verificar llamada a OpenAI
        call_args = mock_openai_client.chat.completions.create.call_args
        kwargs = call_args.kwargs
        assert kwargs['model'] == 'gpt-4o-mini'
        user_msg = kwargs['messages'][1]['content']
        assert any('base64_string' in item.get('image_url', {}).get('url', '') for item in user_msg if isinstance(item, dict) and item.get('type') == 'image_url')
        assert any('almuerzo con amigos' in item.get('text', '') for item in user_msg if isinstance(item, dict) and item.get('type') == 'text')

    def test_parse_receipt_image_not_a_receipt(self, parser, mock_openai_client):
        response = json.dumps({
            'amount': 0.0,
            'category': 'None',
            'payee': 'None',
            'account': None,
            'memo': 'No es un recibo',
            'confidence': 0.0
        })
        _mock_response(mock_openai_client, response)

        result = parser.parse_receipt_image('base64_not_receipt')
        assert result is None  # Porque amount <= 0 falla validación

    def test_parse_receipt_image_api_error(self, parser, mock_openai_client):
        mock_openai_client.chat.completions.create.side_effect = Exception('Vision API error')
        result = parser.parse_receipt_image('base64')
        assert result is None

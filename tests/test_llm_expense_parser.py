"""Tests for LLMExpenseParser.parse_message() intent classification."""
import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo


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

    def test_full_owe_other_paid(self, parser, mock_openai_client):
        """100% debt: another person paid entirely for the user ('por mí')."""
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 100000.0,
            'category': 'Groceries',
            'payee': 'MercadoLibre',
            'account': None,
            'memo': 'Eli gastó 100k en MercadoLibre por mí',
            'confidence': 0.9,
            'person': 'Eli',
            'proportion': '1',
            'payer': 'other',
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('Eli gastó 100k en MercadoLibre por mí')
        assert result is not None
        assert result['intent'] == 'shared_expense'
        assert result['payer'] == 'other'
        assert result['proportion'] == '1'
        assert result['person'] == 'Eli'
        assert result['amount'] == 100000.0


class TestSplitAmountValidation:
    """Tests for split_amount field validation in shared_expense responses."""

    def _shared_expense_base(self) -> dict:
        return {
            'intent': 'shared_expense',
            'amount': 60000.0,
            'category': 'Restaurants',
            'payee': 'El Corral',
            'account': None,
            'memo': 'test',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': None,
            'payer': 'user',
        }

    def test_valid_split_amount_is_preserved(self, parser, mock_openai_client):
        """When LLM returns a valid positive split_amount, it passes through as float."""
        payload = {**self._shared_expense_base(), 'split_amount': 36700}
        _mock_response(mock_openai_client, json.dumps(payload))
        result = parser.parse_message('gasté 60000, 36700 son por Juan')
        assert result is not None
        assert result['split_amount'] == 36700.0

    def test_split_amount_float_is_preserved(self, parser, mock_openai_client):
        """Fractional split_amount values are accepted."""
        payload = {**self._shared_expense_base(), 'split_amount': 36700.5}
        _mock_response(mock_openai_client, json.dumps(payload))
        result = parser.parse_message('test')
        assert result is not None
        assert result['split_amount'] == 36700.5

    def test_split_amount_null_is_accepted(self, parser, mock_openai_client):
        """split_amount: null in LLM response is normalised to None."""
        payload = {**self._shared_expense_base(), 'split_amount': None}
        _mock_response(mock_openai_client, json.dumps(payload))
        result = parser.parse_message('almuerzo 60000 a medias con Juan')
        assert result is not None
        assert result['split_amount'] is None

    def test_split_amount_missing_defaults_to_none(self, parser, mock_openai_client):
        """When LLM omits split_amount entirely, the field is set to None."""
        payload = self._shared_expense_base()
        # no 'split_amount' key at all
        _mock_response(mock_openai_client, json.dumps(payload))
        result = parser.parse_message('almuerzo a medias')
        assert result is not None
        assert result['split_amount'] is None

    def test_split_amount_negative_normalised_to_none(self, parser, mock_openai_client):
        """split_amount: -100 is invalid and should be normalised to None."""
        payload = {**self._shared_expense_base(), 'split_amount': -100}
        _mock_response(mock_openai_client, json.dumps(payload))
        result = parser.parse_message('test')
        assert result is not None
        assert result['split_amount'] is None

    def test_split_amount_zero_normalised_to_none(self, parser, mock_openai_client):
        """split_amount: 0 is treated as invalid (not > 0) and normalised to None."""
        payload = {**self._shared_expense_base(), 'split_amount': 0}
        _mock_response(mock_openai_client, json.dumps(payload))
        result = parser.parse_message('test')
        assert result is not None
        assert result['split_amount'] is None

    def test_split_amount_string_normalised_to_none(self, parser, mock_openai_client):
        """split_amount: 'abc' is not a number and should be normalised to None."""
        payload = {**self._shared_expense_base(), 'split_amount': 'abc'}
        _mock_response(mock_openai_client, json.dumps(payload))
        result = parser.parse_message('test')
        assert result is not None
        assert result['split_amount'] is None


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
            'required_fields_check': True  # Just to avoid validation errors if I change something
        })
        # Remove extra fields so the payload matches required_fields exactly
        response_dict = json.loads(response)
        if 'required_fields_check' in response_dict: del response_dict['required_fields_check']
        
        _mock_response(mock_openai_client, json.dumps(response_dict))

        result = parser.parse_receipt_image('base64_string', 'almuerzo con amigos')
        
        assert result is not None
        assert result['amount'] == 45000.0
        assert result['payee'] == 'El Corral'
        assert result['confidence'] == 0.95
        
        # Verify OpenAI call
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
        assert result is None  # Because amount <= 0 fails validation

    def test_parse_receipt_image_api_error(self, parser, mock_openai_client):
        mock_openai_client.chat.completions.create.side_effect = Exception('Vision API error')
        result = parser.parse_receipt_image('base64')
        assert result is None


# ---------------------------------------------------------------------------
# Date field passthrough
# ---------------------------------------------------------------------------

class TestDateFieldPassthrough:

    def test_parse_message_expense_with_date(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'ayer almuerzo',
            'date': '2026-03-17',
            'confidence': 0.85,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('ayer almuerzo 25 lucas')
        assert result['date'] == '2026-03-17'

    def test_parse_message_expense_with_null_date(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo',
            'date': None,
            'confidence': 0.85,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('almuerzo 25 lucas')
        assert result['date'] is None

    def test_parse_message_shared_expense_with_date(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'shared_expense',
            'amount': 50000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'ayer almuerzo con Juan',
            'date': '2026-03-15',
            'confidence': 0.9,
            'person': 'Juan',
            'proportion': '1/2',
            'payer': 'user',
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('ayer almuerzo mitad 50k con Juan')
        assert result['date'] == '2026-03-15'

    def test_parse_message_query_no_date_field(self, parser, mock_openai_client):
        response = json.dumps({
            'intent': 'query',
            'query_type': 'category_balance',
            'query_target': 'Groceries',
            'confidence': 0.9,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_message('cuanto me queda en groceries')
        assert 'date' not in result

    def test_parse_expense_with_date(self, parser, mock_openai_client):
        response = json.dumps({
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'ayer almuerzo',
            'date': '2026-03-17',
            'confidence': 0.85,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_expense('ayer almuerzo 25 lucas')
        assert result['date'] == '2026-03-17'

    def test_parse_expense_with_null_date(self, parser, mock_openai_client):
        response = json.dumps({
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': "McDonald's",
            'account': None,
            'memo': 'almuerzo',
            'date': None,
            'confidence': 0.85,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_expense('almuerzo 25 lucas')
        assert result['date'] is None

    def test_parse_receipt_with_date(self, parser, mock_openai_client):
        response = json.dumps({
            'amount': 45000.0,
            'category': 'Restaurants',
            'payee': 'El Corral',
            'account': None,
            'memo': '[10/03] Almuerzo',
            'date': '2026-03-10',
            'confidence': 0.95,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_receipt_image('base64_data')
        assert result['date'] == '2026-03-10'

    def test_parse_receipt_with_null_date(self, parser, mock_openai_client):
        response = json.dumps({
            'amount': 45000.0,
            'category': 'Restaurants',
            'payee': 'El Corral',
            'account': None,
            'memo': 'Almuerzo',
            'date': None,
            'confidence': 0.95,
        })
        _mock_response(mock_openai_client, response)
        result = parser.parse_receipt_image('base64_data')
        assert result['date'] is None


class TestLearningHintsInPrompt:
    """Tests that learning_hints are injected into or omitted from prompts correctly."""

    def test_message_system_prompt_includes_hints_when_provided(self, parser):
        hints = "- Movistar: Internet (70%), Telefono (30%)"
        prompt = parser._generate_message_system_prompt(learning_hints=hints)
        assert "HISTORIAL DE CATEGORIZACIÓN" in prompt
        assert hints in prompt

    def test_message_system_prompt_omits_hints_when_none(self, parser):
        prompt = parser._generate_message_system_prompt()
        assert "HISTORIAL DE CATEGORIZACIÓN" not in prompt

    def test_base_system_prompt_includes_hints_when_provided(self, parser):
        hints = "- McDonald's: Meal delivery (100%)"
        prompt = parser._generate_system_prompt(learning_hints=hints)
        assert "HISTORIAL DE CATEGORIZACIÓN" in prompt
        assert hints in prompt

    def test_receipt_system_prompt_includes_hints_when_provided(self, parser):
        hints = "- Movistar: Internet (70%)"
        prompt = parser._generate_receipt_system_prompt(learning_hints=hints)
        assert "HISTORIAL DE CATEGORIZACIÓN" in prompt
        assert hints in prompt

    def test_receipt_system_prompt_omits_hints_when_none(self, parser):
        prompt = parser._generate_receipt_system_prompt()
        assert "HISTORIAL DE CATEGORIZACIÓN" not in prompt

    def test_parse_message_passes_hints_to_system_prompt(self, parser, mock_openai_client):
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

        hints = "- McDonald's: Restaurants (80%), Groceries (20%)"
        parser.parse_message('25 lucas almuerzo', learning_hints=hints)

        system_prompt = mock_openai_client.chat.completions.create.call_args.kwargs['messages'][0]['content']
        assert hints in system_prompt


class TestDateContext:
    """Verify that date context is injected into prompts."""

    def test_system_prompt_contains_date_context(self, parser):
        prompt = parser._generate_system_prompt()
        assert 'FECHA ACTUAL DEL SISTEMA' in prompt
        assert 'DETECCIÓN DE FECHAS' in prompt
        assert '"date"' in prompt

    def test_message_system_prompt_contains_date_context(self, parser):
        prompt = parser._generate_message_system_prompt()
        assert 'FECHA ACTUAL DEL SISTEMA' in prompt
        assert 'DETECCIÓN DE FECHAS' in prompt
        assert '"date"' in prompt

    def test_receipt_system_prompt_contains_date_context(self, parser):
        prompt = parser._generate_receipt_system_prompt()
        assert 'FECHA ACTUAL DEL SISTEMA' in prompt
        assert '"date"' in prompt

    def test_get_date_context_uses_timezone(self, parser):
        """When timezone is specified, _get_date_context uses user_now with that timezone."""
        fixed_dt = datetime(2026, 6, 15, 10, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        with patch('parsers.llm_expense_parser.user_now', return_value=fixed_dt):
            context = parser._get_date_context("America/Bogota")
            assert '2026-06-15' in context
            assert 'lunes' in context

    def test_get_date_context_default_timezone(self, parser):
        """Without specifying timezone, uses DEFAULT_TIMEZONE."""
        from domain.time_utils import DEFAULT_TIMEZONE
        fixed_dt = datetime(2026, 3, 18, 22, 0, 0, tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
        with patch('parsers.llm_expense_parser.user_now', return_value=fixed_dt):
            context = parser._get_date_context()
            assert '2026-03-18' in context

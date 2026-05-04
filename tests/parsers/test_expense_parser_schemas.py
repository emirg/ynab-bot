"""Tests for typed expense parser response schemas."""
import pytest
from pydantic import ValidationError


def test_expense_payload_normalises_to_service_dict():
    from parsers.expense_parser_schemas import ParsedExpense

    parsed = ParsedExpense.model_validate({
        'intent': 'expense',
        'amount': 25000,
        'category': 'Restaurants',
        'payee': "McDonald's",
        'account': None,
        'memo': '25 lucas almuerzo',
        'date': None,
        'confidence': 0.9,
    })

    assert parsed.to_parser_dict() == {
        'intent': 'expense',
        'amount': 25000.0,
        'category': 'Restaurants',
        'payee': "McDonald's",
        'account': None,
        'memo': '25 lucas almuerzo',
        'date': None,
        'confidence': 0.9,
    }


def test_query_payload_normalises_to_service_dict():
    from parsers.expense_parser_schemas import ParsedQuery

    parsed = ParsedQuery.model_validate({
        'intent': 'query',
        'query_type': 'category_balance',
        'query_target': 'Groceries',
        'confidence': 0.8,
    })

    assert parsed.to_parser_dict() == {
        'intent': 'query',
        'query_type': 'category_balance',
        'query_target': 'Groceries',
        'confidence': 0.8,
    }


def test_shared_expense_payload_normalises_legacy_optional_fields():
    from parsers.expense_parser_schemas import ParsedSharedExpense

    parsed = ParsedSharedExpense.model_validate({
        'intent': 'shared_expense',
        'amount': 71800,
        'category': 'Restaurants',
        'payee': 'Pret',
        'account': None,
        'memo': 'Frank gasto 71800 en Pret',
        'date': None,
        'confidence': 0.95,
        'person': 'Frank',
        'proportion': '1/2',
        'payer': 'other',
    })

    assert parsed.to_parser_dict() == {
        'intent': 'shared_expense',
        'amount': 71800.0,
        'category': 'Restaurants',
        'payee': 'Pret',
        'account': None,
        'memo': 'Frank gasto 71800 en Pret',
        'date': None,
        'confidence': 0.95,
        'person': 'Frank',
        'proportion': '1/2',
        'split_amount': None,
        'user_share_amount': None,
        'other_share_amount': None,
        'payer': 'other',
    }


def test_invalid_confidence_is_rejected():
    from parsers.expense_parser_schemas import ParsedExpense

    with pytest.raises(ValidationError):
        ParsedExpense.model_validate({
            'intent': 'expense',
            'amount': 25000,
            'category': 'Restaurants',
            'payee': 'Pret',
            'account': None,
            'memo': 'bad confidence',
            'date': None,
            'confidence': 1.5,
        })


def test_invalid_shared_expense_payer_is_rejected():
    from parsers.expense_parser_schemas import ParsedSharedExpense

    with pytest.raises(ValidationError):
        ParsedSharedExpense.model_validate({
            'intent': 'shared_expense',
            'amount': 50000,
            'category': 'Restaurants',
            'payee': 'Pret',
            'account': None,
            'memo': 'bad payer',
            'date': None,
            'confidence': 0.8,
            'person': 'Frank',
            'proportion': '1/2',
            'payer': 'someone_else',
        })


def test_conflicting_explicit_share_amounts_are_preserved_for_service_validation():
    from parsers.expense_parser_schemas import ParsedSharedExpense

    parsed = ParsedSharedExpense.model_validate({
        'intent': 'shared_expense',
        'amount': 200000,
        'category': 'Groceries',
        'payee': 'Carulla',
        'account': None,
        'memo': '80k son mios y 150k son de Frank',
        'date': None,
        'confidence': 0.8,
        'person': 'Frank',
        'proportion': None,
        'payer': 'other',
        'user_share_amount': 80000,
        'other_share_amount': 150000,
    })

    assert parsed.to_parser_dict()['user_share_amount'] == 80000.0
    assert parsed.to_parser_dict()['other_share_amount'] == 150000.0


def test_parser_response_schema_validates_discriminated_union():
    from parsers.expense_parser_schemas import ParsedExpenseResponse

    parsed = ParsedExpenseResponse.model_validate({
        'intent': 'query',
        'query_type': 'budget_summary',
        'query_target': None,
        'confidence': 0.85,
    })

    assert parsed.to_parser_dict()['intent'] == 'query'


def test_openai_message_response_schema_is_discriminated_union():
    from parsers.expense_parser_schemas import message_response_format_schema

    schema = message_response_format_schema()

    assert schema['type'] == 'object'
    assert 'properties' in schema
    assert 'result' in schema['properties']
    
    result_schema = schema['properties']['result']
    assert 'anyOf' in result_schema
    assert len(result_schema['anyOf']) == 3
    
    # Verify branches
    intents = [s['properties']['intent']['enum'][0] for s in result_schema['anyOf']]
    assert set(intents) == {'query', 'expense', 'shared_expense'}
    
    for branch in result_schema['anyOf']:
        assert branch['type'] == 'object'
        assert branch['additionalProperties'] is False
        assert set(branch['required']) == set(branch['properties'])
        
        # Check specific constraints
        intent = branch['properties']['intent']['enum'][0]
        if intent == 'shared_expense':
            assert branch['properties']['person']['type'] == 'string'
            assert 'null' not in branch['properties']['person'].get('type', [])

"""Tests for OpenAI model parameter compatibility (temperature, max_tokens)."""
import json
import pytest
from unittest.mock import MagicMock, patch
from parsers.llm_expense_parser import LLMExpenseParser


@pytest.fixture
def mock_openai_client():
    with patch('parsers.llm_expense_parser.OpenAI') as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


def _setup_mock_response(client):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps({
        'intent': 'expense',
        'amount': 100.0,
        'category': 'Groceries',
        'payee': 'Test',
        'memo': 'test',
        'confidence': 0.9,
    })
    client.chat.completions.create.return_value = mock_resp


def test_gpt4_mini_uses_temperature_and_max_tokens(mock_openai_client):
    with patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_EXPENSE_PARSER_MODEL': 'gpt-4o-mini',
    }):
        parser = LLMExpenseParser()
    
    _setup_mock_response(mock_openai_client)
    parser.parse_message('test')
    
    kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert kwargs['model'] == 'gpt-4o-mini'
    assert kwargs['temperature'] == 0.1
    assert 'max_tokens' in kwargs
    assert 'max_completion_tokens' not in kwargs


def test_o1_mini_strips_temperature_and_uses_max_completion_tokens(mock_openai_client):
    with patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_EXPENSE_PARSER_MODEL': 'o1-mini',
    }):
        parser = LLMExpenseParser()
    
    _setup_mock_response(mock_openai_client)
    parser.parse_message('test')
    
    kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert kwargs['model'] == 'o1-mini'
    assert 'temperature' not in kwargs
    assert 'max_completion_tokens' in kwargs
    assert 'max_tokens' not in kwargs


def test_gpt5_strips_temperature_and_uses_max_completion_tokens(mock_openai_client):
    with patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_EXPENSE_PARSER_MODEL': 'gpt-5-preview',
    }):
        parser = LLMExpenseParser()
    
    _setup_mock_response(mock_openai_client)
    parser.parse_message('test')
    
    kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert kwargs['model'] == 'gpt-5-preview'
    assert 'temperature' not in kwargs
    assert 'max_completion_tokens' in kwargs
    assert 'max_tokens' not in kwargs


def test_parse_expense_uses_gpt4o_mini_by_default_and_respects_it(mock_openai_client):
    # Even if parser model is set to something else, parse_expense hardcodes gpt-4o-mini
    with patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_EXPENSE_PARSER_MODEL': 'o1-mini',
    }):
        parser = LLMExpenseParser()
    
    # We need to setup a slightly different response for parse_expense
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps({
        'amount': 100.0,
        'category': 'Groceries',
        'payee': 'Test',
        'memo': 'test',
        'confidence': 0.9,
    })
    mock_openai_client.chat.completions.create.return_value = mock_resp

    parser.parse_expense('test')
    
    kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert kwargs['model'] == 'gpt-4o-mini'
    assert kwargs['temperature'] == 0.1
    assert 'max_tokens' in kwargs

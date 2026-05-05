"""Test to verify the default model for LLMExpenseParser."""
import os
import pytest
from unittest.mock import patch
from parsers.llm_expense_parser import LLMExpenseParser

def test_default_model_is_gpt5_mini():
    # Ensure environment variable is not set
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-key'}, clear=True):
        # We need to re-read the environment in the constructor if it's cached, 
        # but LLMExpenseParser reads it in __init__.
        # We must also mock load_dotenv or ensure it doesn't overwrite our empty dict.
        with patch('parsers.llm_expense_parser.load_dotenv'):
            # We must also mock the OpenAI initialization to avoid API key errors
            with patch('parsers.llm_expense_parser.OpenAI'):
                parser = LLMExpenseParser()
                assert parser.expense_parser_model == 'gpt-5-mini'

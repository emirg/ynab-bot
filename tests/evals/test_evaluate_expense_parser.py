"""Tests for the manual expense parser model evaluator."""
from scripts.evals.evaluate_expense_parser import (
    compare_expected,
    evaluate_scenarios,
)


def test_compare_expected_matches_exact_fields_and_date_wildcards():
    expected = {
        'intent': 'expense',
        'amount': 25000.0,
        'category': 'Restaurants',
        'payee': 'Crepes',
        'account': None,
        'memo': 'Ayer almuerzo 25 lucas en Crepes',
        'date': 'RELATIVE_DATE',
        'confidence': 0.8,
    }
    actual = {
        'intent': 'expense',
        'amount': 25000.0,
        'category': 'Restaurants',
        'payee': 'Crepes',
        'account': None,
        'memo': 'Ayer almuerzo 25 lucas en Crepes',
        'date': '2026-05-03',
        'confidence': 0.95,
    }

    assert compare_expected(expected, actual) == []


def test_compare_expected_reports_field_mismatch():
    mismatches = compare_expected(
        {'intent': 'expense', 'amount': 25000.0, 'category': 'Restaurants', 'confidence': 0.8},
        {'intent': 'expense', 'amount': 30000.0, 'category': 'Groceries', 'confidence': 0.9},
    )

    assert mismatches == [
        "amount: expected 25000.0, got 30000.0",
        "category: expected 'Restaurants', got 'Groceries'",
    ]


def test_evaluate_scenarios_uses_parser_factory_without_network():
    scenarios = [{
        'id': 'expense_restaurant',
        'message': '25 lucas almuerzo',
        'categories': ['Restaurants'],
        'accounts': ['Nu Card'],
        'expected': {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': 'Restaurante',
            'account': None,
            'memo': '25 lucas almuerzo',
            'date': None,
            'confidence': 0.8,
        },
    }]

    class FakeParser:
        def update_categories(self, categories):
            self.categories = categories

        def update_accounts(self, accounts):
            self.accounts = accounts

        def parse_message(self, message, learning_hints=None):
            assert message == '25 lucas almuerzo'
            assert learning_hints is None
            return {
                'intent': 'expense',
                'amount': 25000.0,
                'category': 'Restaurants',
                'payee': 'Restaurante',
                'account': None,
                'memo': '25 lucas almuerzo',
                'date': None,
                'confidence': 0.95,
            }

    results = evaluate_scenarios(
        model='test-model',
        scenarios=scenarios,
        parser_factory=lambda model: FakeParser(),
    )

    assert results == [{
        'id': 'expense_restaurant',
        'passed': True,
        'mismatches': [],
    }]

"""Tests for the manual expense parser model evaluator."""
import json

from scripts.evals.evaluate_expense_parser import (
    build_output_document,
    compare_expected,
    evaluate_scenarios,
    main,
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
        'message': '25 lucas almuerzo',
        'passed': True,
        'expected': scenarios[0]['expected'],
        'actual': {
            'intent': 'expense',
            'amount': 25000.0,
            'category': 'Restaurants',
            'payee': 'Restaurante',
            'account': None,
            'memo': '25 lucas almuerzo',
            'date': None,
            'confidence': 0.95,
        },
        'mismatches': [],
        'categories': ['Restaurants'],
        'accounts': ['Nu Card'],
        'learning_hints': None,
    }]


def test_build_output_document_keeps_multiple_models_and_summary():
    model_results = {
        'baseline': [{
            'id': 'one',
            'message': 'msg',
            'passed': True,
            'expected': {'intent': 'expense'},
            'actual': {'intent': 'expense'},
            'mismatches': [],
            'categories': [],
            'accounts': [],
            'learning_hints': None,
        }],
        'candidate': [{
            'id': 'one',
            'message': 'msg',
            'passed': False,
            'expected': {'intent': 'expense'},
            'actual': None,
            'mismatches': ['parser returned None'],
            'categories': [],
            'accounts': [],
            'learning_hints': None,
        }],
    }

    output = build_output_document(
        fixture_dir='tests/fixtures/expense_parser_golden',
        model_results=model_results,
    )

    assert output['fixture_dir'] == 'tests/fixtures/expense_parser_golden'
    assert set(output['models']) == {'baseline', 'candidate'}
    assert output['models']['baseline']['passed_count'] == 1
    assert output['models']['baseline']['failed_count'] == 0
    assert output['models']['candidate']['passed_count'] == 0
    assert output['models']['candidate']['failed_count'] == 1
    assert output['models']['candidate']['scenarios'][0]['actual'] is None
    assert isinstance(output['generated_at'], str)


def test_main_writes_output_json_for_multiple_models(tmp_path, monkeypatch):
    fixture_dir = tmp_path / 'fixtures'
    fixture_dir.mkdir()
    (fixture_dir / 'initial.json').write_text(json.dumps([{
        'id': 'expense_restaurant',
        'message': '25 lucas almuerzo',
        'categories': ['Restaurants'],
        'accounts': ['Nu Card'],
        'expected': {'intent': 'expense', 'confidence': 0.8},
    }]))
    output_path = tmp_path / 'results' / 'eval.json'

    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class FakeParser:
        def __init__(self, model):
            self.model = model

        def update_categories(self, categories):
            pass

        def update_accounts(self, accounts):
            pass

        def parse_message(self, message, learning_hints=None):
            return {'intent': 'expense', 'confidence': 0.9, 'model': self.model}

    import scripts.evals.evaluate_expense_parser as evaluator
    monkeypatch.setattr(evaluator, '_default_parser_factory', lambda model: FakeParser(model))

    exit_code = main([
        '--model', 'baseline',
        '--model', 'candidate',
        '--fixture-dir', str(fixture_dir),
        '--output', str(output_path),
    ])

    assert exit_code == 0
    saved = json.loads(output_path.read_text())
    assert set(saved['models']) == {'baseline', 'candidate'}
    assert saved['models']['baseline']['scenarios'][0]['actual']['model'] == 'baseline'
    assert saved['models']['candidate']['scenarios'][0]['actual']['model'] == 'candidate'

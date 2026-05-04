"""Deterministic validation for expense parser golden fixtures."""
import json
from pathlib import Path

from parsers.expense_parser_schemas import ParsedExpenseResponse


FIXTURE_DIR = Path(__file__).resolve().parents[1] / 'fixtures' / 'expense_parser_golden'


def _load_scenarios() -> list[dict]:
    scenarios = []
    for fixture_path in sorted(FIXTURE_DIR.glob('*.json')):
        scenarios.extend(json.loads(fixture_path.read_text()))
    return scenarios


def test_golden_fixture_ids_are_unique():
    scenarios = _load_scenarios()
    ids = [scenario['id'] for scenario in scenarios]

    assert len(ids) >= 30
    assert len(ids) == len(set(ids))


def test_golden_fixtures_have_required_shape():
    for scenario in _load_scenarios():
        assert scenario['id']
        assert scenario['message']
        assert isinstance(scenario.get('categories'), list)
        assert isinstance(scenario.get('accounts'), list)
        assert isinstance(scenario['expected'], dict)
        assert scenario['expected']['intent'] in {'expense', 'query', 'shared_expense'}


def test_golden_expected_payloads_match_parser_schema():
    for scenario in _load_scenarios():
        expected = scenario['expected']
        if expected.get('date') in {'RELATIVE_DATE', 'YYYY-MM-DD'}:
            expected = {**expected, 'date': '2026-05-04'}

        parsed = ParsedExpenseResponse.model_validate(expected)
        normalised = parsed.to_parser_dict()

        assert normalised['intent'] == expected['intent']


def test_golden_expected_categories_and_accounts_are_available():
    for scenario in _load_scenarios():
        expected = scenario['expected']
        categories = set(scenario['categories'])
        accounts = set(scenario['accounts'])

        if expected['intent'] in {'expense', 'shared_expense'}:
            assert expected['category'] in categories
            if expected.get('account') is not None:
                assert expected['account'] in accounts

        if expected['intent'] == 'query' and expected['query_type'] == 'category_balance':
            assert expected['query_target'] in categories
        if expected['intent'] == 'query' and expected['query_type'] == 'account_balance':
            assert expected['query_target'] in accounts

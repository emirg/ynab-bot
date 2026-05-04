"""Manual real-model evaluation for the expense parser golden suite."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from parsers.llm_expense_parser import LLMExpenseParser

DEFAULT_FIXTURE_DIR = PROJECT_ROOT / 'tests' / 'fixtures' / 'expense_parser_golden'


def load_scenarios(fixture_dir: Path = DEFAULT_FIXTURE_DIR) -> list[dict]:
    scenarios = []
    for fixture_path in sorted(fixture_dir.glob('*.json')):
        scenarios.extend(json.loads(fixture_path.read_text()))
    return scenarios


def _matches_date_wildcard(expected_value: str, actual_value: object) -> bool:
    if expected_value == 'RELATIVE_DATE':
        return isinstance(actual_value, str) and len(actual_value) == 10
    if expected_value == 'YYYY-MM-DD':
        return isinstance(actual_value, str) and len(actual_value) == 10
    return False


def compare_expected(expected: dict, actual: dict | None) -> list[str]:
    if actual is None:
        return ['parser returned None']

    mismatches = []
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        if field == 'confidence':
            if actual_value is None or float(actual_value) < float(expected_value):
                mismatches.append(
                    f"confidence: expected >= {expected_value!r}, got {actual_value!r}"
                )
            continue
        if field == 'date' and isinstance(expected_value, str):
            if _matches_date_wildcard(expected_value, actual_value):
                continue
        if actual_value != expected_value:
            mismatches.append(f"{field}: expected {expected_value!r}, got {actual_value!r}")
    return mismatches


def _default_parser_factory(model: str) -> LLMExpenseParser:
    previous_model = os.environ.get('OPENAI_EXPENSE_PARSER_MODEL')
    os.environ['OPENAI_EXPENSE_PARSER_MODEL'] = model
    try:
        return LLMExpenseParser()
    finally:
        if previous_model is None:
            os.environ.pop('OPENAI_EXPENSE_PARSER_MODEL', None)
        else:
            os.environ['OPENAI_EXPENSE_PARSER_MODEL'] = previous_model


def evaluate_scenarios(
    model: str,
    scenarios: list[dict],
    parser_factory: Callable[[str], object] = _default_parser_factory,
) -> list[dict]:
    parser = parser_factory(model)
    results = []
    for scenario in scenarios:
        parser.update_categories([{'name': category} for category in scenario.get('categories', [])])
        parser.update_accounts(scenario.get('accounts', []))
        actual = parser.parse_message(
            scenario['message'],
            learning_hints=scenario.get('learning_hints'),
        )
        mismatches = compare_expected(scenario['expected'], actual)
        results.append({
            'id': scenario['id'],
            'passed': not mismatches,
            'mismatches': mismatches,
        })
    return results


def _print_model_results(model: str, results: list[dict]) -> None:
    passed = sum(1 for result in results if result['passed'])
    total = len(results)
    print(f"\nModel: {model}")
    print(f"Passed: {passed}/{total}")
    for result in results:
        if result['passed']:
            continue
        print(f"- {result['id']}")
        for mismatch in result['mismatches']:
            print(f"  - {mismatch}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--model',
        action='append',
        required=True,
        help='OpenAI model to evaluate. Repeat to compare multiple models.',
    )
    parser.add_argument(
        '--fixture-dir',
        type=Path,
        default=DEFAULT_FIXTURE_DIR,
        help='Directory containing golden scenario JSON files.',
    )
    args = parser.parse_args(argv)

    if not os.getenv('OPENAI_API_KEY'):
        print('OPENAI_API_KEY is required for real-model evaluation.', file=sys.stderr)
        return 2

    scenarios = load_scenarios(args.fixture_dir)
    exit_code = 0
    for model in args.model:
        results = evaluate_scenarios(model, scenarios)
        _print_model_results(model, results)
        if any(not result['passed'] for result in results):
            exit_code = 1
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())

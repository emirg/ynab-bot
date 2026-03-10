"""Tests for JSONLearningRepository."""
import json
import os
import pytest
from decimal import Decimal
from datetime import datetime

from infrastructure.repositories.json_learning_repository import (
    JSONLearningRepository,
    _PAYEE_NORMALIZATIONS,
    _MAX_RECENT_TRANSACTIONS,
)
from domain.models.expense import Expense
from domain.exceptions import LearningDataException


@pytest.fixture
def repo(tmp_json_file):
    return JSONLearningRepository(tmp_json_file)


@pytest.fixture
def expense_mcdonalds():
    return Expense(
        amount=Decimal('25000'), payee="McDonald's", memo='Almuerzo',
        category_id='cat-restaurants', category_name='Restaurants',
        confidence=0.9, parser_source='llm',
    )


@pytest.fixture
def expense_carulla():
    return Expense(
        amount=Decimal('50000'), payee='Carulla', memo='Mercado',
        category_id='cat-groceries', category_name='Groceries',
        confidence=0.8, parser_source='llm',
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:

    def test_creates_file_if_missing(self, tmp_json_file):
        repo = JSONLearningRepository(tmp_json_file)
        assert os.path.exists(tmp_json_file)

    def test_creates_directory_if_missing(self, tmp_path):
        path = str(tmp_path / 'subdir' / 'data.json')
        repo = JSONLearningRepository(path)
        assert os.path.exists(path)

    def test_loads_existing_data(self, tmp_json_file):
        data = {
            'payee_category_mapping': {'carulla': {'cat-1': 5}},
            'category_confidence': {'carulla': 1.0},
            'last_updated': {},
            'user_corrections': [],
            'recent_transactions': [],
            'statistics': {'total_transactions': 5, 'learned_associations': 1, 'accuracy_improvements': 0},
        }
        with open(tmp_json_file, 'w') as f:
            json.dump(data, f)

        repo = JSONLearningRepository(tmp_json_file)
        assert repo.learning_data['payee_category_mapping']['carulla'] == {'cat-1': 5}

    def test_handles_corrupt_json(self, tmp_json_file):
        with open(tmp_json_file, 'w') as f:
            f.write('{corrupt json!!!')

        repo = JSONLearningRepository(tmp_json_file)
        # Should reinitialize with default structure
        assert 'payee_category_mapping' in repo.learning_data

    def test_handles_wrong_structure(self, tmp_json_file):
        with open(tmp_json_file, 'w') as f:
            json.dump({'wrong': 'structure'}, f)

        repo = JSONLearningRepository(tmp_json_file)
        assert 'payee_category_mapping' in repo.learning_data


# ---------------------------------------------------------------------------
# Payee normalization
# ---------------------------------------------------------------------------

class TestNormalizePayee:

    def test_empty_payee(self, repo):
        assert repo._normalize_payee('') == 'unknown'
        assert repo._normalize_payee(None) == 'unknown'

    def test_basic_normalization(self, repo):
        assert repo._normalize_payee('  Carulla  ') == 'carulla'

    def test_strips_punctuation(self, repo):
        assert repo._normalize_payee("Test's Place.") == "tests place"

    @pytest.mark.parametrize('variant,expected', [
        ("McDonald's", 'mcdonalds'),
        ("MC DONALD'S", 'mcdonalds'),
        ("Éxito", 'exito'),
        ("Almacenes Éxito", 'exito'),
        ("Netflix Inc", 'netflix'),
        ("Spotify Premium", 'spotify'),
        ("Uber Technologies", 'uber'),
        ("Home Burger", 'home burguer'),
        ("Olímpica", 'olimpica'),
        ("Saga Falabella", 'falabella'),
    ])
    def test_known_normalizations(self, repo, variant, expected):
        assert repo._normalize_payee(variant) == expected

    def test_unknown_payee_passes_through(self, repo):
        assert repo._normalize_payee('Random Store') == 'random store'


class TestPayeeNormalizationsConstant:

    def test_all_variants_mapped(self):
        assert _PAYEE_NORMALIZATIONS["mcdonald's"] == 'mcdonalds'
        assert _PAYEE_NORMALIZATIONS['éxito'] == 'exito'
        assert _PAYEE_NORMALIZATIONS['spotify premium'] == 'spotify'

    def test_count(self):
        assert len(_PAYEE_NORMALIZATIONS) > 15


# ---------------------------------------------------------------------------
# Record transactions and learning
# ---------------------------------------------------------------------------

class TestRecordTransaction:

    def test_records_new_payee(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        normalized = repo._normalize_payee(expense_mcdonalds.payee)
        assert normalized in repo.learning_data['payee_category_mapping']
        assert repo.learning_data['payee_category_mapping'][normalized]['cat-restaurants'] == 1

    def test_increments_count(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        repo.record_successful_transaction(expense_mcdonalds)
        normalized = repo._normalize_payee(expense_mcdonalds.payee)
        assert repo.learning_data['payee_category_mapping'][normalized]['cat-restaurants'] == 2

    def test_updates_confidence(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        normalized = repo._normalize_payee(expense_mcdonalds.payee)
        assert repo.learning_data['category_confidence'][normalized] == 1.0

    def test_updates_statistics(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        assert repo.learning_data['statistics']['total_transactions'] == 1

    def test_skips_missing_payee(self, repo):
        e = Expense(amount=Decimal('1000'), payee='', memo='x', category_id='cat-1')
        repo.record_successful_transaction(e)
        assert repo.learning_data['statistics']['total_transactions'] == 0

    def test_skips_missing_category(self, repo):
        e = Expense(amount=Decimal('1000'), payee='Test', memo='x')
        repo.record_successful_transaction(e)
        assert repo.learning_data['statistics']['total_transactions'] == 0

    def test_persists_to_file(self, repo, expense_mcdonalds, tmp_json_file):
        repo.record_successful_transaction(expense_mcdonalds)
        with open(tmp_json_file) as f:
            data = json.load(f)
        assert data['statistics']['total_transactions'] == 1


# ---------------------------------------------------------------------------
# Category prediction
# ---------------------------------------------------------------------------

class TestPredictCategory:

    def test_no_data_returns_none(self, repo):
        assert repo.predict_category('Unknown Store', [{'id': 'cat-1'}]) is None

    def test_empty_payee_returns_none(self, repo):
        assert repo.predict_category('', [{'id': 'cat-1'}]) is None

    def test_predicts_most_frequent(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        categories = [{'id': 'cat-restaurants'}, {'id': 'cat-groceries'}]
        result = repo.predict_category("McDonald's", categories)
        assert result is not None
        assert result[0] == 'cat-restaurants'
        assert result[1] == 1.0

    def test_returns_none_for_deleted_category(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        # Only include a different category
        categories = [{'id': 'cat-other'}]
        result = repo.predict_category("McDonald's", categories)
        assert result is None

    def test_prediction_with_multiple_categories(self, repo):
        # Record 3x groceries, 1x restaurants for same payee
        for _ in range(3):
            e = Expense(amount=Decimal('1000'), payee='Exito', memo='x',
                        category_id='cat-groceries', category_name='Groceries')
            repo.record_successful_transaction(e)
        e = Expense(amount=Decimal('1000'), payee='Exito', memo='x',
                    category_id='cat-restaurants', category_name='Restaurants')
        repo.record_successful_transaction(e)

        categories = [{'id': 'cat-groceries'}, {'id': 'cat-restaurants'}]
        result = repo.predict_category('Exito', categories)
        assert result[0] == 'cat-groceries'
        assert result[1] == 0.75  # 3/4


# ---------------------------------------------------------------------------
# User corrections
# ---------------------------------------------------------------------------

class TestRecordCorrection:

    def test_correction_updates_mapping(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        repo.record_user_correction("McDonald's", 'cat-restaurants', 'cat-fast-food')
        normalized = repo._normalize_payee("McDonald's")
        mapping = repo.learning_data['payee_category_mapping'][normalized]
        assert mapping.get('cat-fast-food', 0) >= 1

    def test_correction_reduces_old_count(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        repo.record_user_correction("McDonald's", 'cat-restaurants', 'cat-fast-food')
        normalized = repo._normalize_payee("McDonald's")
        mapping = repo.learning_data['payee_category_mapping'][normalized]
        assert 'cat-restaurants' not in mapping  # was 1, reduced to 0, deleted

    def test_correction_for_new_payee(self, repo):
        repo.record_user_correction('NewPlace', 'cat-old', 'cat-new')
        normalized = repo._normalize_payee('NewPlace')
        assert repo.learning_data['payee_category_mapping'][normalized]['cat-new'] == 1

    def test_correction_updates_statistics(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(expense_mcdonalds)
        repo.record_user_correction("McDonald's", 'cat-restaurants', 'cat-fast-food')
        assert repo.learning_data['statistics']['accuracy_improvements'] == 1

    def test_correction_appended_to_list(self, repo):
        repo.record_user_correction('Store', 'old', 'new')
        assert len(repo.learning_data['user_corrections']) == 1
        assert repo.learning_data['user_corrections'][0]['payee'] == 'store'


# ---------------------------------------------------------------------------
# Recent transactions
# ---------------------------------------------------------------------------

class TestRecentTransactions:

    def test_add_and_get(self, repo, expense_mcdonalds):
        repo.add_recent_transaction(expense_mcdonalds)
        recent = repo.get_recent_transactions(10)
        assert len(recent) == 1
        assert recent[0]['payee'] == "McDonald's"

    def test_most_recent_first(self, repo, expense_mcdonalds, expense_carulla):
        repo.add_recent_transaction(expense_mcdonalds)
        repo.add_recent_transaction(expense_carulla)
        recent = repo.get_recent_transactions(10)
        assert recent[0]['payee'] == 'Carulla'

    def test_limit_respected(self, repo, expense_mcdonalds):
        for _ in range(5):
            repo.add_recent_transaction(expense_mcdonalds)
        assert len(repo.get_recent_transactions(3)) == 3

    def test_max_recent_transactions(self, repo):
        for i in range(_MAX_RECENT_TRANSACTIONS + 5):
            e = Expense(amount=Decimal('1000'), payee=f'Store {i}', memo='x')
            repo.add_recent_transaction(e)
        assert len(repo.learning_data['recent_transactions']) == _MAX_RECENT_TRANSACTIONS

    def test_empty_by_default(self, repo):
        assert repo.get_recent_transactions(10) == []


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

class TestStatistics:

    def test_initial_stats(self, repo):
        stats = repo.get_learning_statistics()
        assert stats['total_transactions'] == 0
        assert stats['learned_payees'] == 0
        assert stats['total_corrections'] == 0

    def test_stats_after_transactions(self, repo, expense_mcdonalds, expense_carulla):
        repo.record_successful_transaction(expense_mcdonalds)
        repo.record_successful_transaction(expense_carulla)
        stats = repo.get_learning_statistics()
        assert stats['total_transactions'] == 2
        assert stats['learned_payees'] == 2

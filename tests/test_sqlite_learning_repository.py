"""Tests for SQLiteLearningRepository."""
import pytest
from decimal import Decimal

from infrastructure.repositories.database_manager import DatabaseManager
from infrastructure.repositories.sqlite_learning_repository import (
    SQLiteLearningRepository,
    _MAX_RECENT_TRANSACTIONS,
)
from infrastructure.repositories.sqlite_user_repository import SQLiteUserRepository
from domain.models.expense import Expense
from domain.models.user import UserConfiguration, UserStatus
from domain.services.payee_normalizer import normalize_payee, _PAYEE_NORMALIZATIONS

TELEGRAM_ID = 123456789


@pytest.fixture
def db_manager(tmp_db_file):
    mgr = DatabaseManager(tmp_db_file)
    yield mgr
    mgr.close()


@pytest.fixture
def repo(db_manager):
    # Insert a user so foreign keys are satisfied
    user_repo = SQLiteUserRepository(db_manager)
    user_repo.save(UserConfiguration(telegram_id=TELEGRAM_ID, status=UserStatus.AUTHORIZED))
    return SQLiteLearningRepository(db_manager)


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
# Payee normalization (extracted to domain service)
# ---------------------------------------------------------------------------

class TestNormalizePayee:

    def test_empty_payee(self):
        assert normalize_payee('') == 'unknown'
        assert normalize_payee(None) == 'unknown'

    def test_basic_normalization(self):
        assert normalize_payee('  Carulla  ') == 'carulla'

    def test_strips_punctuation(self):
        assert normalize_payee("Test's Place.") == "tests place"

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
    def test_known_normalizations(self, variant, expected):
        assert normalize_payee(variant) == expected

    def test_unknown_payee_passes_through(self):
        assert normalize_payee('Random Store') == 'random store'


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
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", [{'id': 'cat-restaurants'}])
        assert result is not None
        assert result[0] == 'cat-restaurants'
        assert result[2] == 1

    def test_increments_count(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", [{'id': 'cat-restaurants'}])
        assert result[1] == 1.0  # confidence stays 1.0 when only one category
        assert result[2] == 2

    def test_updates_statistics(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        stats = repo.get_learning_statistics(TELEGRAM_ID)
        assert stats['total_transactions'] == 1

    def test_skips_missing_payee(self, repo):
        e = Expense(amount=Decimal('1000'), payee='', memo='x', category_id='cat-1')
        repo.record_successful_transaction(TELEGRAM_ID, e)
        stats = repo.get_learning_statistics(TELEGRAM_ID)
        assert stats['total_transactions'] == 0

    def test_skips_missing_category(self, repo):
        e = Expense(amount=Decimal('1000'), payee='Test', memo='x')
        repo.record_successful_transaction(TELEGRAM_ID, e)
        stats = repo.get_learning_statistics(TELEGRAM_ID)
        assert stats['total_transactions'] == 0


# ---------------------------------------------------------------------------
# Category prediction
# ---------------------------------------------------------------------------

class TestPredictCategory:

    def test_no_data_returns_none(self, repo):
        assert repo.predict_category(TELEGRAM_ID, 'Unknown Store', [{'id': 'cat-1'}]) is None

    def test_empty_payee_returns_none(self, repo):
        assert repo.predict_category(TELEGRAM_ID, '', [{'id': 'cat-1'}]) is None

    def test_predicts_most_frequent(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        categories = [{'id': 'cat-restaurants'}, {'id': 'cat-groceries'}]
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", categories)
        assert result is not None
        assert result[0] == 'cat-restaurants'
        assert result[1] == 1.0
        assert result[2] == 1

    def test_returns_none_for_deleted_category(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        categories = [{'id': 'cat-other'}]
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", categories)
        assert result is None

    def test_prediction_with_multiple_categories(self, repo):
        for _ in range(3):
            e = Expense(amount=Decimal('1000'), payee='Exito', memo='x',
                        category_id='cat-groceries', category_name='Groceries')
            repo.record_successful_transaction(TELEGRAM_ID, e)
        e = Expense(amount=Decimal('1000'), payee='Exito', memo='x',
                    category_id='cat-restaurants', category_name='Restaurants')
        repo.record_successful_transaction(TELEGRAM_ID, e)

        categories = [{'id': 'cat-groceries'}, {'id': 'cat-restaurants'}]
        result = repo.predict_category(TELEGRAM_ID, 'Exito', categories)
        assert result[0] == 'cat-groceries'
        assert result[1] == 0.75  # 3/4
        assert result[2] == 3

    def test_per_user_isolation(self, repo, db_manager, expense_mcdonalds):
        """Data from one user should not leak to another."""
        other_user_id = 999999999
        # Create the other user
        user_repo = SQLiteUserRepository(db_manager)
        user_repo.save(UserConfiguration(telegram_id=other_user_id, status=UserStatus.AUTHORIZED))

        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        result = repo.predict_category(other_user_id, "McDonald's", [{'id': 'cat-restaurants'}])
        assert result is None  # other user has no data


# ---------------------------------------------------------------------------
# User corrections
# ---------------------------------------------------------------------------

class TestRecordCorrection:

    def test_correction_updates_mapping(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_user_correction(TELEGRAM_ID, "McDonald's", 'cat-restaurants', 'cat-fast-food')
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", [{'id': 'cat-fast-food'}])
        assert result is not None
        assert result[0] == 'cat-fast-food'
        assert result[2] == 1

    def test_correction_reduces_old_count(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_user_correction(TELEGRAM_ID, "McDonald's", 'cat-restaurants', 'cat-fast-food')
        # Old category should be removed (count was 1, now 0 -> deleted)
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", [{'id': 'cat-restaurants'}])
        assert result is None

    def test_correction_for_new_payee(self, repo):
        repo.record_user_correction(TELEGRAM_ID, 'NewPlace', 'cat-old', 'cat-new')
        result = repo.predict_category(TELEGRAM_ID, 'NewPlace', [{'id': 'cat-new'}])
        assert result is not None
        assert result[0] == 'cat-new'
        assert result[2] == 1

    def test_correction_updates_statistics(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_user_correction(TELEGRAM_ID, "McDonald's", 'cat-restaurants', 'cat-fast-food')
        stats = repo.get_learning_statistics(TELEGRAM_ID)
        assert stats['total_corrections'] == 1

    def test_correction_saves_category_name(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_user_correction(
            TELEGRAM_ID, "McDonald's", 'cat-restaurants', 'cat-fast-food',
            new_category_name='Fast Food',
        )
        associations = repo.get_payee_associations(TELEGRAM_ID)
        fast_food = [a for a in associations if a['category_id'] == 'cat-fast-food']
        assert len(fast_food) == 1
        assert fast_food[0]['category_name'] == 'Fast Food'

    def test_correction_without_category_name_defaults_empty(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_user_correction(TELEGRAM_ID, "McDonald's", 'cat-restaurants', 'cat-fast-food')
        associations = repo.get_payee_associations(TELEGRAM_ID)
        fast_food = [a for a in associations if a['category_id'] == 'cat-fast-food']
        assert len(fast_food) == 1
        assert fast_food[0]['category_name'] == ''


# ---------------------------------------------------------------------------
# Recent transactions
# ---------------------------------------------------------------------------

class TestRecentTransactions:

    def test_add_and_get(self, repo, expense_mcdonalds):
        repo.add_recent_transaction(TELEGRAM_ID, expense_mcdonalds)
        recent = repo.get_recent_transactions(TELEGRAM_ID, 10)
        assert len(recent) == 1
        assert recent[0]['payee'] == "McDonald's"

    def test_most_recent_first(self, repo, expense_mcdonalds, expense_carulla):
        repo.add_recent_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.add_recent_transaction(TELEGRAM_ID, expense_carulla)
        recent = repo.get_recent_transactions(TELEGRAM_ID, 10)
        assert recent[0]['payee'] == 'Carulla'

    def test_limit_respected(self, repo, expense_mcdonalds):
        for _ in range(5):
            repo.add_recent_transaction(TELEGRAM_ID, expense_mcdonalds)
        assert len(repo.get_recent_transactions(TELEGRAM_ID, 3)) == 3

    def test_max_recent_transactions(self, repo):
        for i in range(_MAX_RECENT_TRANSACTIONS + 5):
            e = Expense(amount=Decimal('1000'), payee=f'Store {i}', memo='x')
            repo.add_recent_transaction(TELEGRAM_ID, e)
        assert len(repo.get_recent_transactions(TELEGRAM_ID, 100)) == _MAX_RECENT_TRANSACTIONS

    def test_empty_by_default(self, repo):
        assert repo.get_recent_transactions(TELEGRAM_ID, 10) == []

    def test_stores_ynab_transaction_id(self, repo, expense_mcdonalds):
        repo.add_recent_transaction(TELEGRAM_ID, expense_mcdonalds, ynab_transaction_id='txn-abc-123')
        recent = repo.get_recent_transactions(TELEGRAM_ID, 10)
        assert len(recent) == 1
        assert recent[0]['ynab_transaction_id'] == 'txn-abc-123'

    def test_ynab_transaction_id_defaults_to_none(self, repo, expense_mcdonalds):
        repo.add_recent_transaction(TELEGRAM_ID, expense_mcdonalds)
        recent = repo.get_recent_transactions(TELEGRAM_ID, 10)
        assert len(recent) == 1
        assert recent[0]['ynab_transaction_id'] is None

    def test_per_user_isolation(self, repo, db_manager, expense_mcdonalds):
        other_user_id = 999999999
        user_repo = SQLiteUserRepository(db_manager)
        user_repo.save(UserConfiguration(telegram_id=other_user_id, status=UserStatus.AUTHORIZED))

        repo.add_recent_transaction(TELEGRAM_ID, expense_mcdonalds)
        assert repo.get_recent_transactions(other_user_id, 10) == []


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

class TestStatistics:

    def test_initial_stats(self, repo):
        stats = repo.get_learning_statistics(TELEGRAM_ID)
        assert stats['total_transactions'] == 0
        assert stats['learned_payees'] == 0
        assert stats['total_corrections'] == 0

    def test_stats_after_transactions(self, repo, expense_mcdonalds, expense_carulla):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_successful_transaction(TELEGRAM_ID, expense_carulla)
        stats = repo.get_learning_statistics(TELEGRAM_ID)
        assert stats['total_transactions'] == 2
        assert stats['learned_payees'] == 2


# ---------------------------------------------------------------------------
# Payee associations
# ---------------------------------------------------------------------------

class TestPayeeAssociations:

    def test_get_payee_associations_returns_correct_data(self, repo, expense_mcdonalds, expense_carulla):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_successful_transaction(TELEGRAM_ID, expense_carulla)
        # Add another mcdonalds to test sorting by count
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)

        associations = repo.get_payee_associations(TELEGRAM_ID)
        assert len(associations) == 2
        # McDonald's should be first because count=2
        assert associations[0]['normalized_payee'] == 'mcdonalds'
        assert associations[0]['count'] == 2
        assert associations[0]['category_name'] == 'Restaurants'

        assert associations[1]['normalized_payee'] == 'carulla'
        assert associations[1]['count'] == 1
        assert associations[1]['category_name'] == 'Groceries'

    def test_get_payee_associations_empty_for_new_user(self, repo):
        assert repo.get_payee_associations(TELEGRAM_ID) == []

    def test_get_payee_associations_per_user_isolation(self, repo, db_manager, expense_mcdonalds):
        other_user_id = 999999999
        # Create the other user
        user_repo = SQLiteUserRepository(db_manager)
        user_repo.save(UserConfiguration(telegram_id=other_user_id, status=UserStatus.AUTHORIZED))

        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        assert len(repo.get_payee_associations(TELEGRAM_ID)) == 1
        assert repo.get_payee_associations(other_user_id) == []

    def test_delete_payee_associations(self, repo, expense_mcdonalds, expense_carulla):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_successful_transaction(TELEGRAM_ID, expense_carulla)

        deleted_count = repo.delete_payee_associations(TELEGRAM_ID, "McDonald's")
        assert deleted_count == 1

        associations = repo.get_payee_associations(TELEGRAM_ID)
        assert len(associations) == 1
        assert associations[0]['normalized_payee'] == 'carulla'

    def test_delete_payee_associations_non_existent(self, repo, expense_carulla):
        repo.record_successful_transaction(TELEGRAM_ID, expense_carulla)
        deleted_count = repo.delete_payee_associations(TELEGRAM_ID, "McDonald's")
        assert deleted_count == 0
        assert len(repo.get_payee_associations(TELEGRAM_ID)) == 1

    def test_delete_payee_associations_per_user_isolation(self, repo, db_manager, expense_mcdonalds):
        other_user_id = 999999999
        # Create the other user
        user_repo = SQLiteUserRepository(db_manager)
        user_repo.save(UserConfiguration(telegram_id=other_user_id, status=UserStatus.AUTHORIZED))

        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_successful_transaction(other_user_id, expense_mcdonalds)

        repo.delete_payee_associations(TELEGRAM_ID, "McDonald's")

        assert repo.get_payee_associations(TELEGRAM_ID) == []
        assert len(repo.get_payee_associations(other_user_id)) == 1


# ---------------------------------------------------------------------------
# Decrement learning
# ---------------------------------------------------------------------------

class TestDecrementLearning:

    def test_decrement_reduces_count(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        # count is now 2
        repo.decrement_learning(TELEGRAM_ID, "McDonald's", 'cat-restaurants')
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", [{'id': 'cat-restaurants'}])
        assert result is not None
        assert result[2] == 1  # count decremented from 2 to 1

    def test_decrement_to_zero_deletes_row(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        # count is 1; decrement should remove the row entirely
        repo.decrement_learning(TELEGRAM_ID, "McDonald's", 'cat-restaurants')
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", [{'id': 'cat-restaurants'}])
        assert result is None

    def test_decrement_nonexistent_is_noop(self, repo):
        # Should not raise; simply does nothing
        repo.decrement_learning(TELEGRAM_ID, "Unknown Payee", 'cat-nonexistent')
        assert repo.get_payee_associations(TELEGRAM_ID) == []

    def test_decrement_normalizes_payee(self, repo, expense_mcdonalds):
        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        # Pass un-normalized variant; should still match
        repo.decrement_learning(TELEGRAM_ID, "MC DONALD'S", 'cat-restaurants')
        result = repo.predict_category(TELEGRAM_ID, "McDonald's", [{'id': 'cat-restaurants'}])
        assert result is None  # row deleted

    def test_decrement_per_user_isolation(self, repo, db_manager, expense_mcdonalds):
        other_user_id = 999999999
        user_repo = SQLiteUserRepository(db_manager)
        user_repo.save(UserConfiguration(telegram_id=other_user_id, status=UserStatus.AUTHORIZED))

        repo.record_successful_transaction(TELEGRAM_ID, expense_mcdonalds)
        repo.record_successful_transaction(other_user_id, expense_mcdonalds)

        # Decrement only for TELEGRAM_ID
        repo.decrement_learning(TELEGRAM_ID, "McDonald's", 'cat-restaurants')

        assert repo.predict_category(TELEGRAM_ID, "McDonald's", [{'id': 'cat-restaurants'}]) is None
        result_other = repo.predict_category(other_user_id, "McDonald's", [{'id': 'cat-restaurants'}])
        assert result_other is not None
        assert result_other[2] == 1  # other user unaffected

    def test_decrement_only_affects_matching_category(self, repo):
        # Two categories for the same payee
        e1 = Expense(amount=Decimal('1000'), payee='Exito', memo='x',
                     category_id='cat-groceries', category_name='Groceries')
        e2 = Expense(amount=Decimal('1000'), payee='Exito', memo='x',
                     category_id='cat-household', category_name='Household')
        repo.record_successful_transaction(TELEGRAM_ID, e1)
        repo.record_successful_transaction(TELEGRAM_ID, e2)

        repo.decrement_learning(TELEGRAM_ID, 'Exito', 'cat-groceries')

        associations = repo.get_payee_associations(TELEGRAM_ID)
        assert len(associations) == 1
        assert associations[0]['category_id'] == 'cat-household'


# ---------------------------------------------------------------------------
# Delete recent transaction
# ---------------------------------------------------------------------------

class TestDeleteRecentTransaction:

    def test_delete_existing_transaction_returns_true(self, repo, expense_mcdonalds):
        repo.add_recent_transaction(TELEGRAM_ID, expense_mcdonalds, ynab_transaction_id='txn-abc-123')

        result = repo.delete_recent_transaction(TELEGRAM_ID, 'txn-abc-123')

        assert result is True
        transactions = repo.get_recent_transactions(TELEGRAM_ID)
        assert all(t['ynab_transaction_id'] != 'txn-abc-123' for t in transactions)

    def test_delete_nonexistent_transaction_returns_false(self, repo):
        result = repo.delete_recent_transaction(TELEGRAM_ID, 'txn-does-not-exist')

        assert result is False

    def test_delete_enforces_per_user_isolation(self, repo, db_manager, expense_mcdonalds):
        other_user_id = 999999999
        user_repo = SQLiteUserRepository(db_manager)
        user_repo.save(UserConfiguration(telegram_id=other_user_id, status=UserStatus.AUTHORIZED))

        repo.add_recent_transaction(other_user_id, expense_mcdonalds, ynab_transaction_id='txn-other-user')

        # Trying to delete other user's transaction as TELEGRAM_ID should return False
        result = repo.delete_recent_transaction(TELEGRAM_ID, 'txn-other-user')

        assert result is False
        # Other user's transaction must still exist
        other_transactions = repo.get_recent_transactions(other_user_id)
        assert any(t['ynab_transaction_id'] == 'txn-other-user' for t in other_transactions)

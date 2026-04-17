"""Tests for LearningService."""
import pytest

from application.services.learning_service import LearningService

TELEGRAM_ID = 123456789


@pytest.fixture
def service(mock_learning_repository):
    return LearningService(learning_repository=mock_learning_repository)


class TestGetLearningStatistics:

    def test_calculates_accuracy_rate(self, service):
        stats = service.get_learning_statistics(TELEGRAM_ID)
        # 5/10 * 100 = 50%
        assert stats['accuracy_rate'] == 50.0

    def test_calculates_correction_rate(self, service):
        stats = service.get_learning_statistics(TELEGRAM_ID)
        # 2/5 * 100 = 40%
        assert stats['correction_rate'] == 40.0

    def test_zero_transactions(self, service, mock_learning_repository):
        mock_learning_repository.get_learning_statistics.return_value = {
            'total_transactions': 0,
            'learned_associations': 0,
            'accuracy_improvements': 0,
        }
        stats = service.get_learning_statistics(TELEGRAM_ID)
        assert stats['accuracy_rate'] == 0.0
        assert stats['correction_rate'] == 0.0

    def test_error_returns_defaults(self, service, mock_learning_repository):
        mock_learning_repository.get_learning_statistics.side_effect = Exception('fail')
        stats = service.get_learning_statistics(TELEGRAM_ID)
        assert 'error' in stats
        assert stats['total_transactions'] == 0


class TestGetRecentTransactions:

    def test_returns_transactions(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.return_value = [
            {'payee': 'Test', 'amount': 1000},
        ]
        result = service.get_recent_transactions(TELEGRAM_ID, 5)
        assert len(result) == 1

    def test_error_returns_empty(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.side_effect = Exception('fail')
        assert service.get_recent_transactions(TELEGRAM_ID) == []


class TestFormatStatisticsMessage:

    def test_contains_key_info(self, service):
        msg = service.format_statistics_message(TELEGRAM_ID)
        assert 'Transacciones totales' in msg
        assert 'Comercios aprendidos' in msg

    def test_error_message(self, service, mock_learning_repository):
        mock_learning_repository.get_learning_statistics.side_effect = Exception('fail')
        msg = service.format_statistics_message(TELEGRAM_ID)
        assert '❌' in msg

    def test_active_state(self, service):
        msg = service.format_statistics_message(TELEGRAM_ID)
        assert 'Activo' in msg

    def test_starting_state(self, service, mock_learning_repository):
        mock_learning_repository.get_learning_statistics.return_value = {
            'total_transactions': 0,
            'learned_associations': 0,
            'accuracy_improvements': 0,
            'learned_payees': 0,
            'total_corrections': 0,
        }
        msg = service.format_statistics_message(TELEGRAM_ID)
        assert 'Iniciando' in msg


class TestFormatRecentTransactionsMessage:

    def test_empty(self, service):
        msg = service.format_recent_transactions_message(TELEGRAM_ID)
        assert 'No hay transacciones' in msg

    def test_with_transactions(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.return_value = [
            {
                'payee': "McDonald's", 'amount': 25000,
                'category_name': 'Restaurants', 'confidence': 0.9,
                'parser_source': 'llm',
            },
            {
                'payee': 'Carulla', 'amount': 50000,
                'category_name': 'Groceries', 'confidence': 0.8,
                'parser_source': 'learning',
            },
        ]
        msg = service.format_recent_transactions_message(TELEGRAM_ID, 5)
        assert "McDonald's" in msg
        assert 'Carulla' in msg
        assert '🤖' in msg  # llm emoji
        assert '🧠' in msg  # learning emoji
        assert 'no un historial canónico de YNAB' in msg
        assert '/editar <número>' in msg

    def test_unknown_parser_source(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.return_value = [
            {
                'payee': 'Test', 'amount': 1000,
                'category_name': 'Cat', 'confidence': 0.5,
                'parser_source': 'custom',
            },
        ]
        msg = service.format_recent_transactions_message(TELEGRAM_ID)
        assert '❓' in msg


class TestLearningDashboard:

    def test_get_payee_associations_delegates(self, service, mock_learning_repository):
        mock_learning_repository.get_payee_associations.return_value = [{'payee': 'X'}]
        assert service.get_payee_associations(TELEGRAM_ID) == [{'payee': 'X'}]

    def test_forget_payee_success(self, service, mock_learning_repository):
        mock_learning_repository.delete_payee_associations.return_value = 1
        assert service.forget_payee(TELEGRAM_ID, "McDonald's") is True
        mock_learning_repository.delete_payee_associations.assert_called_with(
            TELEGRAM_ID, 'mcdonalds'
        )

    def test_forget_payee_failure(self, service, mock_learning_repository):
        mock_learning_repository.delete_payee_associations.return_value = 0
        assert service.forget_payee(TELEGRAM_ID, "McDonald's") is False

    def test_format_learning_dashboard_empty(self, service, mock_learning_repository):
        mock_learning_repository.get_payee_associations.return_value = []
        msg = service.format_learning_dashboard_message(TELEGRAM_ID)
        assert 'Todavía no he aprendido nada' in msg

    def test_format_learning_dashboard_with_data(self, service, mock_learning_repository):
        mock_learning_repository.get_payee_associations.return_value = [
            {'normalized_payee': 'mcdonalds', 'category_name': 'Restaurants', 'count': 5},
            {'normalized_payee': 'carulla', 'category_name': 'Groceries', 'count': 2},
        ]
        msg = service.format_learning_dashboard_message(TELEGRAM_ID)
        assert 'Mcdonalds' in msg
        assert 'Restaurants' in msg
        assert '5 veces' in msg
        assert 'Carulla' in msg
        assert 'Groceries' in msg
        assert '2 veces' in msg

    def test_format_learning_dashboard_missing_category_name(
        self, service, mock_learning_repository
    ):
        mock_learning_repository.get_payee_associations.return_value = [
            {'normalized_payee': 'old_shop', 'category_name': '', 'count': 1},
        ]
        msg = service.format_learning_dashboard_message(TELEGRAM_ID)
        assert 'Categoría desconocida' in msg

    def test_format_forget_result_message(self, service):
        assert 'He olvidado' in service.format_forget_result_message('Test', True)
        assert 'No encontré' in service.format_forget_result_message('Test', False)


class TestEnhancedStatistics:

    def test_contains_top_payees(self, service, mock_learning_repository):
        mock_learning_repository.get_payee_associations.return_value = [
            {'normalized_payee': 'mcdonalds', 'count': 10},
        ]
        msg = service.format_statistics_message(TELEGRAM_ID)
        assert 'Comercios más frecuentes' in msg
        assert 'Mcdonalds' in msg

    def test_contains_top_categories(self, service, mock_learning_repository):
        mock_learning_repository.get_payee_associations.return_value = [
            {'category_id': 'c1', 'category_name': 'Food', 'count': 10},
            {'category_id': 'c1', 'category_name': 'Food', 'count': 5},
            {'category_id': 'c2', 'category_name': 'Transport', 'count': 3},
        ]
        msg = service.format_statistics_message(TELEGRAM_ID)
        assert 'Categorías más usadas' in msg
        assert 'Food (15 txn)' in msg
        assert 'Transport (3 txn)' in msg

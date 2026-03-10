"""Tests for LearningService."""
import pytest

from application.services.learning_service import LearningService


@pytest.fixture
def service(mock_learning_repository):
    return LearningService(learning_repository=mock_learning_repository)


class TestGetLearningStatistics:

    def test_calculates_accuracy_rate(self, service):
        stats = service.get_learning_statistics()
        # 5/10 * 100 = 50%
        assert stats['accuracy_rate'] == 50.0

    def test_calculates_correction_rate(self, service):
        stats = service.get_learning_statistics()
        # 2/5 * 100 = 40%
        assert stats['correction_rate'] == 40.0

    def test_zero_transactions(self, service, mock_learning_repository):
        mock_learning_repository.get_learning_statistics.return_value = {
            'total_transactions': 0,
            'learned_associations': 0,
            'accuracy_improvements': 0,
        }
        stats = service.get_learning_statistics()
        assert stats['accuracy_rate'] == 0.0
        assert stats['correction_rate'] == 0.0

    def test_error_returns_defaults(self, service, mock_learning_repository):
        mock_learning_repository.get_learning_statistics.side_effect = Exception('fail')
        stats = service.get_learning_statistics()
        assert 'error' in stats
        assert stats['total_transactions'] == 0


class TestGetRecentTransactions:

    def test_returns_transactions(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.return_value = [
            {'payee': 'Test', 'amount': 1000},
        ]
        result = service.get_recent_transactions(5)
        assert len(result) == 1

    def test_error_returns_empty(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.side_effect = Exception('fail')
        assert service.get_recent_transactions() == []


class TestFormatStatisticsMessage:

    def test_contains_key_info(self, service):
        msg = service.format_statistics_message()
        assert 'Transacciones totales' in msg
        assert 'Comercios aprendidos' in msg

    def test_error_message(self, service, mock_learning_repository):
        mock_learning_repository.get_learning_statistics.side_effect = Exception('fail')
        msg = service.format_statistics_message()
        assert '❌' in msg

    def test_active_state(self, service):
        msg = service.format_statistics_message()
        assert 'Activo' in msg

    def test_starting_state(self, service, mock_learning_repository):
        mock_learning_repository.get_learning_statistics.return_value = {
            'total_transactions': 0,
            'learned_associations': 0,
            'accuracy_improvements': 0,
            'learned_payees': 0,
            'total_corrections': 0,
        }
        msg = service.format_statistics_message()
        assert 'Iniciando' in msg


class TestFormatRecentTransactionsMessage:

    def test_empty(self, service):
        msg = service.format_recent_transactions_message()
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
        msg = service.format_recent_transactions_message(5)
        assert "McDonald's" in msg
        assert 'Carulla' in msg
        assert '🤖' in msg  # llm emoji
        assert '🧠' in msg  # learning emoji

    def test_unknown_parser_source(self, service, mock_learning_repository):
        mock_learning_repository.get_recent_transactions.return_value = [
            {
                'payee': 'Test', 'amount': 1000,
                'category_name': 'Cat', 'confidence': 0.5,
                'parser_source': 'custom',
            },
        ]
        msg = service.format_recent_transactions_message()
        assert '❓' in msg

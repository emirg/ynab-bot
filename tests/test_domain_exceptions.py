"""Tests for domain exceptions."""
import pytest

from domain.exceptions import (
    YNABBotException,
    UserNotConfiguredException,
    ExpenseParsingException,
    YNABApiException,
    InvalidExpenseException,
    LearningDataException,
    ConfigurationException,
    SpeechProcessingException,
    ImageProcessingException,
)


class TestExceptionHierarchy:

    def test_all_inherit_from_base(self):
        exceptions = [
            UserNotConfiguredException(1),
            ExpenseParsingException('msg'),
            YNABApiException('msg'),
            InvalidExpenseException('msg'),
            LearningDataException('msg'),
            ConfigurationException('msg'),
            SpeechProcessingException('msg'),
            ImageProcessingException('msg'),
        ]
        for exc in exceptions:
            assert isinstance(exc, YNABBotException)
            assert isinstance(exc, Exception)


class TestUserNotConfiguredException:

    def test_basic(self):
        exc = UserNotConfiguredException(123)
        assert exc.user_id == 123
        assert exc.missing_config is None
        assert '123' in str(exc)

    def test_with_missing_config(self):
        exc = UserNotConfiguredException(123, 'budget_id')
        assert exc.missing_config == 'budget_id'
        assert 'budget_id' in str(exc)


class TestExpenseParsingException:

    def test_attributes(self):
        exc = ExpenseParsingException('compre algo', 0.1)
        assert exc.original_message == 'compre algo'
        assert exc.confidence == 0.1
        assert 'compre algo' in str(exc)


class TestYNABApiException:

    def test_basic(self):
        exc = YNABApiException('timeout')
        assert exc.status_code is None
        assert exc.response_body is None

    def test_with_status(self):
        exc = YNABApiException('not found', 404, '{"error": "not found"}')
        assert exc.status_code == 404
        assert exc.response_body == '{"error": "not found"}'


class TestInvalidExpenseException:

    def test_with_data(self):
        data = {'amount': -1}
        exc = InvalidExpenseException('negative amount', data)
        assert exc.expense_data == data
        assert 'negative amount' in str(exc)


class TestSpeechProcessingException:

    def test_with_file_size(self):
        exc = SpeechProcessingException('too large', file_size=2048000)
        assert exc.file_size == 2048000
        assert 'too large' in str(exc)

    def test_without_file_size(self):
        exc = SpeechProcessingException('unknown error')
        assert exc.file_size is None


class TestImageProcessingException:

    def test_with_file_size(self):
        exc = ImageProcessingException('too large', file_size=5242880)
        assert exc.file_size == 5242880
        assert 'too large' in str(exc)

    def test_without_file_size(self):
        exc = ImageProcessingException('unknown error')
        assert exc.file_size is None

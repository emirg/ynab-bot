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
    OAuthException,
    TokenExpiredException,
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

    def test_token_expired_inherits_ynab_api_and_base(self):
        exc = TokenExpiredException()
        assert isinstance(exc, YNABApiException)
        assert isinstance(exc, YNABBotException)


class TestBaseExceptionUserMessage:

    def test_default_user_message(self):
        exc = YNABBotException("technical error")
        assert exc.user_message == "Ocurrió un error inesperado. Intenta de nuevo."

    def test_custom_user_message(self):
        exc = YNABBotException("technical error", user_message="Mensaje personalizado.")
        assert exc.user_message == "Mensaje personalizado."

    def test_str_returns_technical_message(self):
        exc = YNABBotException("technical error", user_message="Mensaje personalizado.")
        assert str(exc) == "technical error"


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

    def test_user_message(self):
        exc = UserNotConfiguredException(123)
        assert exc.user_message == "No tienes tu presupuesto configurado. Usa /config para empezar."

    def test_str_is_technical(self):
        exc = UserNotConfiguredException(42)
        assert "42" in str(exc)
        assert "not configured" in str(exc)


class TestExpenseParsingException:

    def test_attributes(self):
        exc = ExpenseParsingException('compre algo', 0.1)
        assert exc.original_message == 'compre algo'
        assert exc.confidence == 0.1
        assert 'compre algo' in str(exc)

    def test_user_message(self):
        exc = ExpenseParsingException('compre algo')
        assert exc.user_message == "No pude entender tu mensaje. Intenta con un formato como: almuerzo 25000"

    def test_str_is_technical(self):
        exc = ExpenseParsingException('compre algo', 0.3)
        assert "Could not parse expense" in str(exc)
        assert "compre algo" in str(exc)


class TestYNABApiException:

    def test_basic(self):
        exc = YNABApiException('timeout')
        assert exc.status_code is None
        assert exc.response_body is None

    def test_with_status(self):
        exc = YNABApiException('not found', 404, '{"error": "not found"}')
        assert exc.status_code == 404
        assert exc.response_body == '{"error": "not found"}'

    def test_user_message(self):
        exc = YNABApiException('timeout')
        assert exc.user_message == "Hubo un problema conectando con YNAB. Intenta de nuevo en unos segundos."

    def test_str_is_technical(self):
        exc = YNABApiException('server error', 500)
        assert "YNAB API error" in str(exc)
        assert "server error" in str(exc)

    def test_is_retryable_429(self):
        assert YNABApiException('rate limit', 429).is_retryable is True

    def test_is_retryable_500(self):
        assert YNABApiException('server error', 500).is_retryable is True

    def test_is_retryable_502(self):
        assert YNABApiException('bad gateway', 502).is_retryable is True

    def test_is_retryable_503(self):
        assert YNABApiException('service unavailable', 503).is_retryable is True

    def test_is_retryable_504(self):
        assert YNABApiException('gateway timeout', 504).is_retryable is True

    def test_is_retryable_none_status_code(self):
        # Network error (no HTTP response) should be retryable
        assert YNABApiException('connection refused').is_retryable is True

    def test_not_retryable_401(self):
        assert YNABApiException('unauthorized', 401).is_retryable is False

    def test_not_retryable_400(self):
        assert YNABApiException('bad request', 400).is_retryable is False

    def test_not_retryable_404(self):
        assert YNABApiException('not found', 404).is_retryable is False

    def test_not_retryable_200(self):
        assert YNABApiException('ok', 200).is_retryable is False


class TestInvalidExpenseException:

    def test_with_data(self):
        data = {'amount': -1}
        exc = InvalidExpenseException('negative amount', data)
        assert exc.expense_data == data
        assert 'negative amount' in str(exc)

    def test_user_message(self):
        exc = InvalidExpenseException('negative amount')
        assert exc.user_message == "Los datos del gasto no son válidos. Revisa el monto e intenta de nuevo."

    def test_str_is_technical(self):
        exc = InvalidExpenseException('bad data')
        assert "Invalid expense" in str(exc)


class TestLearningDataException:

    def test_user_message(self):
        exc = LearningDataException('db error')
        assert exc.user_message == "Hubo un problema con el sistema de aprendizaje."

    def test_str_is_technical(self):
        exc = LearningDataException('db error')
        assert "db error" in str(exc)


class TestConfigurationException:

    def test_user_message(self):
        exc = ConfigurationException('missing key')
        assert exc.user_message == "Error de configuración del bot."

    def test_str_is_technical(self):
        exc = ConfigurationException('missing key')
        assert "missing key" in str(exc)


class TestSpeechProcessingException:

    def test_with_file_size(self):
        exc = SpeechProcessingException('too large', file_size=2048000)
        assert exc.file_size == 2048000
        assert 'too large' in str(exc)

    def test_without_file_size(self):
        exc = SpeechProcessingException('unknown error')
        assert exc.file_size is None

    def test_user_message(self):
        exc = SpeechProcessingException('error')
        assert exc.user_message == "No pude procesar el mensaje de voz. Intenta de nuevo o envía un texto."

    def test_str_is_technical(self):
        exc = SpeechProcessingException('audio corrupt')
        assert "Speech processing error" in str(exc)


class TestImageProcessingException:

    def test_with_file_size(self):
        exc = ImageProcessingException('too large', file_size=5242880)
        assert exc.file_size == 5242880
        assert 'too large' in str(exc)

    def test_without_file_size(self):
        exc = ImageProcessingException('unknown error')
        assert exc.file_size is None

    def test_user_message(self):
        exc = ImageProcessingException('error')
        assert exc.user_message == "No pude analizar la imagen. Asegúrate de que sea legible e intenta de nuevo."

    def test_str_is_technical(self):
        exc = ImageProcessingException('bad format')
        assert "Image processing error" in str(exc)


class TestOAuthException:

    def test_user_message(self):
        exc = OAuthException('invalid grant')
        assert exc.user_message == "Hubo un problema con la autenticación de YNAB. Intenta reconectar con /connect."

    def test_str_is_technical(self):
        exc = OAuthException('invalid grant')
        assert "invalid grant" in str(exc)

    def test_custom_user_message_override(self):
        exc = OAuthException('error', user_message="Mensaje alternativo.")
        assert exc.user_message == "Mensaje alternativo."


class TestTokenExpiredException:

    def test_default_message(self):
        exc = TokenExpiredException()
        assert "Token expirado" in str(exc)

    def test_user_message(self):
        exc = TokenExpiredException()
        assert exc.user_message == "Tu sesión de YNAB expiró. Usa /connect para reconectar."

    def test_custom_technical_message(self):
        exc = TokenExpiredException("refresh failed")
        assert "refresh failed" in str(exc)

    def test_is_retryable_always_false(self):
        # TokenExpired overrides is_retryable to always return False:
        # a token expiry is not a transient error that a retry will fix.
        exc = TokenExpiredException()
        assert exc.is_retryable is False

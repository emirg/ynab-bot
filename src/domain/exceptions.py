"""Domain exceptions for YNAB Bot"""

_DEFAULT_USER_MESSAGE = "Ocurrió un error inesperado. Intenta de nuevo."


class YNABBotException(Exception):
    """Base exception for YNAB Bot"""
    def __init__(self, *args, user_message: str = _DEFAULT_USER_MESSAGE, **kwargs):
        self.user_message = user_message
        super().__init__(*args, **kwargs)


class UserNotConfiguredException(YNABBotException):
    """User hasn't configured their YNAB settings"""
    def __init__(self, user_id: int, missing_config: str = None):
        self.user_id = user_id
        self.missing_config = missing_config
        message = f"User {user_id} not configured"
        if missing_config:
            message += f": missing {missing_config}"
        super().__init__(
            message,
            user_message="No tienes tu presupuesto configurado. Usa /config para empezar.",
        )


class ExpenseParsingException(YNABBotException):
    """Could not parse expense message"""
    def __init__(
        self,
        message: str,
        confidence: float = 0.0,
        user_message: str = "No pude entender tu mensaje. Intenta con un formato como: almuerzo 25000",
    ):
        self.original_message = message
        self.confidence = confidence
        super().__init__(
            f"Could not parse expense: '{message}' (confidence: {confidence})",
            user_message=user_message,
        )


class YNABApiException(YNABBotException):
    """YNAB API error"""

    _RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, message: str, status_code: int = None, response_body: str = None,
                 user_message: str = "Hubo un problema conectando con YNAB. Intenta de nuevo en unos segundos."):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"YNAB API error: {message}", user_message=user_message)

    @property
    def is_retryable(self) -> bool:
        """Returns True for transient errors that can be retried."""
        if self.status_code is None:
            return True
        return self.status_code in self._RETRYABLE_STATUS_CODES


class InvalidExpenseException(YNABBotException):
    """Expense data is invalid"""
    def __init__(self, message: str, expense_data: dict = None):
        self.expense_data = expense_data
        super().__init__(
            f"Invalid expense: {message}",
            user_message="Los datos del gasto no son válidos. Revisa el monto e intenta de nuevo.",
        )


class LearningDataException(YNABBotException):
    """Error with learning data operations"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("user_message", "Hubo un problema con el sistema de aprendizaje.")
        super().__init__(*args, **kwargs)


class ConfigurationException(YNABBotException):
    """Configuration error"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("user_message", "Error de configuración del bot.")
        super().__init__(*args, **kwargs)


class SpeechProcessingException(YNABBotException):
    """Speech-to-text processing error"""
    def __init__(self, message: str, file_size: int = None):
        self.file_size = file_size
        super().__init__(
            f"Speech processing error: {message}",
            user_message="No pude procesar el mensaje de voz. Intenta de nuevo o envía un texto.",
        )


class ImageProcessingException(YNABBotException):
    """Receipt image processing error"""
    def __init__(self, message: str, file_size: int = None):
        self.file_size = file_size
        super().__init__(
            f"Image processing error: {message}",
            user_message="No pude analizar la imagen. Asegúrate de que sea legible e intenta de nuevo.",
        )


class OAuthException(YNABBotException):
    """OAuth flow error"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "user_message",
            "Hubo un problema con la autenticación de YNAB. Intenta reconectar con /connect.",
        )
        super().__init__(*args, **kwargs)


class AdvisorAuthenticationException(YNABBotException):
    """Advisor launch/session authentication error"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "user_message",
            "No se pudo validar el acceso al advisor. Vuelve a abrirlo desde /analisis.",
        )
        super().__init__(*args, **kwargs)


class TokenExpiredException(YNABApiException):
    """Token has expired and could not be refreshed"""
    def __init__(self, message: str = "Token expirado y no se pudo refrescar"):
        super().__init__(
            message,
            user_message="Tu sesión de YNAB expiró. Usa /connect para reconectar.",
        )

    @property
    def is_retryable(self) -> bool:
        return False

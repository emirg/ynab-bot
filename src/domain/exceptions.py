"""Domain exceptions for YNAB Bot"""


class YNABBotException(Exception):
    """Base exception for YNAB Bot"""
    pass


class UserNotConfiguredException(YNABBotException):
    """User hasn't configured their YNAB settings"""
    def __init__(self, user_id: int, missing_config: str = None):
        self.user_id = user_id
        self.missing_config = missing_config
        message = f"User {user_id} not configured"
        if missing_config:
            message += f": missing {missing_config}"
        super().__init__(message)


class ExpenseParsingException(YNABBotException):
    """Could not parse expense message"""
    def __init__(self, message: str, confidence: float = 0.0):
        self.original_message = message
        self.confidence = confidence
        super().__init__(f"Could not parse expense: '{message}' (confidence: {confidence})")


class YNABApiException(YNABBotException):
    """YNAB API error"""
    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"YNAB API error: {message}")


class InvalidExpenseException(YNABBotException):
    """Expense data is invalid"""
    def __init__(self, message: str, expense_data: dict = None):
        self.expense_data = expense_data
        super().__init__(f"Invalid expense: {message}")


class LearningDataException(YNABBotException):
    """Error with learning data operations"""
    pass


class ConfigurationException(YNABBotException):
    """Configuration error"""
    pass


class SpeechProcessingException(YNABBotException):
    """Speech-to-text processing error"""
    def __init__(self, message: str, file_size: int = None):
        self.file_size = file_size
        super().__init__(f"Speech processing error: {message}")
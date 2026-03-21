import pytest
from unittest.mock import patch, MagicMock
from infrastructure.telegram_notifier import TelegramNotifier


@pytest.fixture
def notifier():
    return TelegramNotifier("test_token")


def test_send_message_success(notifier):
    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        
        reply_markup = {"inline_keyboard": [[{"text": "Btn", "callback_data": "data"}]]}
        success = notifier.send_message(12345, "Hello", reply_markup=reply_markup)
        
        assert success is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.telegram.org/bottest_token/sendMessage"
        assert kwargs["json"]["chat_id"] == 12345
        assert kwargs["json"]["text"] == "Hello"
        assert kwargs["json"]["reply_markup"] == reply_markup


def test_send_message_failure(notifier):
    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("API Error")
        
        success = notifier.send_message(12345, "Hello")
        
        assert success is False
        mock_post.assert_called_once()

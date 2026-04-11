from unittest.mock import MagicMock, patch

import main


class TestMain:
    @patch.dict("os.environ", {"PORT": "8080"}, clear=False)
    @patch("main.YNABTelegramBot")
    @patch("main.TelegramNotifier")
    @patch("main.configure_http_api")
    @patch("main.set_on_oauth_success")
    @patch("main.set_oauth_service")
    @patch("main.create_container")
    @patch("main.start_health_server")
    def test_main_starts_health_and_http_api_servers(
        self,
        mock_start_health_server,
        mock_create_container,
        mock_set_oauth_service,
        mock_set_on_oauth_success,
        mock_configure_http_api,
        mock_telegram_notifier,
        mock_bot_cls,
    ):
        container = MagicMock()
        container.get_config.return_value = MagicMock(telegram_token="tg-token")
        container.get_oauth_service.return_value = MagicMock()
        mock_create_container.return_value = container

        bot = MagicMock()
        mock_bot_cls.return_value = bot

        main.main()

        mock_start_health_server.assert_called_once_with(8080)
        mock_create_container.assert_called_once_with("config/.env")
        mock_set_oauth_service.assert_called_once_with(container.get_oauth_service.return_value)
        mock_configure_http_api.assert_called_once_with(container)
        mock_set_on_oauth_success.assert_called_once()
        mock_telegram_notifier.assert_called_once_with("tg-token")
        mock_bot_cls.assert_called_once_with(container)
        bot.run.assert_called_once_with()

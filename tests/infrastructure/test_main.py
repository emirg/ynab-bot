from unittest.mock import MagicMock, patch

import pytest

import main
from infrastructure.config.app_config import AppConfig


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

    @patch.dict("os.environ", {"PORT": "8080", "APP_HOLD_OPEN": "0"}, clear=False)
    @patch("main.YNABTelegramBot")
    @patch("main.TelegramNotifier")
    @patch("main.configure_http_api")
    @patch("main.set_on_oauth_success")
    @patch("main.set_oauth_service")
    @patch("main.create_container")
    @patch("main.start_health_server")
    def test_http_dev_mode_skips_bot_polling(
        self,
        mock_start_health_server,
        mock_create_container,
        mock_set_oauth_service,
        mock_set_on_oauth_success,
        mock_configure_http_api,
        mock_telegram_notifier,
        mock_bot_cls,
    ):
        config = AppConfig(
            telegram_token=None,
            openai_key=None,
            admin_ids=[1],
            ynab_client_id=None,
            ynab_client_secret=None,
            ynab_redirect_uri=None,
            token_encryption_key="k",
            http_api_key="dev-http-key",
            app_mode="http-dev",
            external_mode="stub",
        )
        container = MagicMock()
        container.get_config.return_value = config
        mock_create_container.return_value = container

        main.main()

        mock_start_health_server.assert_called_once_with(8080)
        mock_configure_http_api.assert_called_once_with(container)
        mock_set_oauth_service.assert_called_once_with(None)
        mock_bot_cls.assert_not_called()
        mock_telegram_notifier.assert_not_called()

    @patch.dict("os.environ", {"PORT": "8080"}, clear=False)
    @patch("main.create_container")
    @patch("main.start_health_server")
    def test_startup_error_print_redacts_telegram_token(
        self,
        mock_start_health_server,
        mock_create_container,
        capsys,
    ):
        mock_create_container.side_effect = RuntimeError(
            "The token `123456789:abcdefghijklmnopqrstuvwxyzABCDE-abc` "
            "was rejected by the server."
        )

        with pytest.raises(SystemExit):
            main.main()

        output = capsys.readouterr().out
        assert "123456789:abcdefghijklmnopqrstuvwxyzABCDE-abc" not in output
        assert "Error starting the bot: The token `[REDACTED]` was rejected by the server." in output

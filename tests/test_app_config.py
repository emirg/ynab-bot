"""Tests for AppConfig."""
import os
import pytest

from infrastructure.config.app_config import AppConfig, _PROJECT_ROOT
from domain.exceptions import ConfigurationException


class TestProjectRoot:

    def test_project_root_exists(self):
        assert os.path.isdir(_PROJECT_ROOT)

    def test_project_root_contains_src(self):
        assert os.path.isdir(os.path.join(_PROJECT_ROOT, 'src'))


class TestParseAdminIds:

    def test_single_id(self):
        assert AppConfig._parse_admin_ids('123') == [123]

    def test_multiple_ids(self):
        assert AppConfig._parse_admin_ids('123,456,789') == [123, 456, 789]

    def test_with_spaces(self):
        assert AppConfig._parse_admin_ids(' 123 , 456 ') == [123, 456]

    def test_empty_raises(self):
        with pytest.raises(ConfigurationException):
            AppConfig._parse_admin_ids('')

    def test_whitespace_only_raises(self):
        with pytest.raises(ConfigurationException):
            AppConfig._parse_admin_ids('   ')

    def test_invalid_format_raises(self):
        with pytest.raises(ConfigurationException):
            AppConfig._parse_admin_ids('abc,def')

    def test_mixed_valid_invalid_raises(self):
        with pytest.raises(ConfigurationException):
            AppConfig._parse_admin_ids('123,abc')


class TestRequireEnv:

    def test_returns_value(self, monkeypatch):
        monkeypatch.setenv('TEST_VAR', 'value')
        assert AppConfig._require_env('TEST_VAR') == 'value'

    def test_raises_if_missing(self, monkeypatch):
        monkeypatch.delenv('TEST_VAR', raising=False)
        with pytest.raises(ConfigurationException):
            AppConfig._require_env('TEST_VAR')

    def test_raises_if_empty(self, monkeypatch):
        monkeypatch.setenv('TEST_VAR', '')
        with pytest.raises(ConfigurationException):
            AppConfig._require_env('TEST_VAR')


class TestGetAbsolutePath:

    def test_absolute_path_unchanged(self):
        config = AppConfig(
            telegram_token='t', ynab_token='y', openai_key='o', admin_ids=[1],
        )
        assert config.get_absolute_path('/absolute/path') == '/absolute/path'

    def test_relative_path_joined(self):
        config = AppConfig(
            telegram_token='t', ynab_token='y', openai_key='o', admin_ids=[1],
        )
        result = config.get_absolute_path('data/test.db')
        assert result.endswith('data/test.db')
        assert os.path.isabs(result)


class TestDatabaseAbsolutePath:

    def test_default_path(self):
        config = AppConfig(
            telegram_token='t', ynab_token='y', openai_key='o', admin_ids=[1],
        )
        path = config.database_absolute_path
        assert path.endswith('data/users.db')
        assert os.path.isabs(path)


class TestLearningDataAbsolutePath:

    def test_default_path(self):
        config = AppConfig(
            telegram_token='t', ynab_token='y', openai_key='o', admin_ids=[1],
        )
        path = config.learning_data_absolute_path
        assert path.endswith('data/category_learning_data.json')
        assert os.path.isabs(path)


class TestFromEnv:

    def test_loads_from_env(self, monkeypatch, tmp_path):
        # Clear any env vars that might leak from other tests
        monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
        monkeypatch.delenv('YNAB_ACCESS_TOKEN', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('ADMIN_IDS', raising=False)
        env_file = tmp_path / '.env'
        env_file.write_text(
            'TELEGRAM_BOT_TOKEN=tg-token\n'
            'YNAB_ACCESS_TOKEN=ynab-token\n'
            'OPENAI_API_KEY=openai-key\n'
            'ADMIN_IDS=111,222\n'
        )
        config = AppConfig.from_env(str(env_file))
        assert config.telegram_token == 'tg-token'
        assert config.ynab_token == 'ynab-token'
        assert config.openai_key == 'openai-key'
        assert config.admin_ids == [111, 222]

    def test_missing_required_raises(self, monkeypatch, tmp_path):
        env_file = tmp_path / '.env'
        env_file.write_text('ADMIN_IDS=111\n')
        # Clear any existing env vars
        monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
        monkeypatch.delenv('YNAB_ACCESS_TOKEN', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        with pytest.raises(ConfigurationException):
            AppConfig.from_env(str(env_file))

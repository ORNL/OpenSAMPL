"""
Tests for the CLI module.

This module tests the command-line interface functionality including configuration,
command parsing, and various CLI commands.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner
import click

from opensampl.cli import cli, load_config, path_or_string
from opensampl.config.base import BaseConfig


class TestCLIConfig:
    """Test CLI configuration functionality."""

    def test_cli_config_defaults(self):
        """Test CLIConfig default values."""
        config = BaseConfig()
        assert config.ROUTE_TO_BACKEND is False
        assert config.BACKEND_URL is None
        assert config.DATABASE_URL is None
        assert config.ARCHIVE_PATH == Path("archive")
        assert config.LOG_LEVEL == "INFO"
        assert config.API_KEY is None
        assert config.INSECURE_REQUESTS is False

    def test_cli_config_with_env_vars(self):
        """Test CLIConfig with environment variables."""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'postgresql://test:5432/testdb',
            'LOG_LEVEL': 'DEBUG',
            'ROUTE_TO_BACKEND': 'true'
        }):
            config = BaseConfig()
            assert config.DATABASE_URL == 'postgresql://test:5432/testdb'
            assert config.LOG_LEVEL == 'DEBUG'
            assert config.ROUTE_TO_BACKEND is True

    @patch('opensampl.cli.find_dotenv')
    def test_cli_config_auto_find_env_file(self, mock_find_dotenv, tmp_path):
        """Test CLIConfig auto-finding .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("DATABASE_URL=postgresql://auto:5432/autodb")
        mock_find_dotenv.return_value = str(env_file)

        config = load_config()
        assert config.DATABASE_URL == "postgresql://auto:5432/autodb"

    def test_cli_config_validation(self):
        """Test CLIConfig validation."""
        # Should work with valid data
        config = BaseConfig(DATABASE_URL="postgresql://test:5432/testdb")
        assert config.DATABASE_URL == "postgresql://test:5432/testdb"

        # Should work with routing enabled
        config = BaseConfig(ROUTE_TO_BACKEND=True, BACKEND_URL="http://localhost:8000")
        assert config.ROUTE_TO_BACKEND is True
        assert config.BACKEND_URL == "http://localhost:8000"


class TestPathOrString:
    """Test path_or_string utility function."""

    def test_path_or_string_with_file(self, tmp_path):
        """Test path_or_string with existing file."""
        test_file = tmp_path / "test.yaml"
        test_data = {"key": "value", "list": [1, 2, 3]}
        test_file.write_text(yaml.dump(test_data))

        result = path_or_string(str(test_file))
        assert result == test_data

    def test_path_or_string_with_string(self):
        """Test path_or_string with string input."""
        test_data = {"key": "value"}
        test_string = yaml.dump(test_data)

        result = path_or_string(test_string)
        assert result == test_data

    def test_path_or_string_with_invalid_file(self, tmp_path):
        """Test path_or_string with non-existent file."""
        # Use a string that is invalid for both YAML and JSON parsing
        invalid_string = "[unclosed_list"

        # Should fail to parse as both YAML and JSON
        with pytest.raises(click.BadParameter):
            path_or_string(invalid_string)

    def test_path_or_string_with_invalid_yaml(self):
        """Test path_or_string with invalid YAML."""
        # Use a string that is invalid for both YAML and JSON parsing
        invalid_string = "{unclosed: [1, 2, 3"

        with pytest.raises(click.BadParameter):
            path_or_string(invalid_string)


class TestCLI:
    """Test CLI command functionality."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner for testing."""
        return CliRunner()

    def test_cli_help(self, runner):
        """Test CLI help command."""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "CLI utility for openSAMPL" in result.output

    def test_cli_with_env_file(self, runner, tmp_path):
        """Test CLI with environment file."""
        env_file = tmp_path / ".env"
        env_file.write_text("DATABASE_URL=postgresql://test:5432/testdb")

        result = runner.invoke(cli, ['--env-file', str(env_file), '--help'])

        assert result.exit_code == 0

    def test_cli_load_command(self, runner):
        """Test the load command."""
        result = runner.invoke(cli, ['load', '--help'])

        assert result.exit_code == 0

    def test_cli_load_table_command(self, runner):
        """Test the load table command."""
        result = runner.invoke(cli, ['load', 'table', '--help'])

        assert result.exit_code == 0

    def test_cli_create_command(self, runner):
        """Test the create command."""
        result = runner.invoke(cli, ['create', '--help'])

        assert result.exit_code == 0

    def test_cli_config_command(self, runner):
        """Test the config command."""
        result = runner.invoke(cli, ['config', '--help'])

        assert result.exit_code == 0

    def test_cli_config_show_command(self, runner):
        """Test the config show command."""
        result = runner.invoke(cli, ['config', 'show', '--help'])

        assert result.exit_code == 0

    def test_cli_config_file_command(self, runner):
        """Test the config file command."""
        result = runner.invoke(cli, ['config', 'file', '--help'])

        assert result.exit_code == 0

    def test_cli_config_set_command(self, runner):
        """Test the config set command."""
        result = runner.invoke(cli, ['config', 'set', '--help'])

        assert result.exit_code == 0

    def test_cli_init_command(self, runner):
        """Test the init command."""
        result = runner.invoke(cli, ['init', '--help'])

        assert result.exit_code == 0

    def test_cli_case_insensitive_commands(self, runner):
        """Test case-insensitive subcommand handling for 'load'."""
        # Only subcommands of 'load' are case-insensitive, not the top-level
        result1 = runner.invoke(cli, ['load', 'TABLE', '--help'])
        result2 = runner.invoke(cli, ['load', 'table', '--help'])
        result3 = runner.invoke(cli, ['load', 'Table', '--help'])

        # All should work the same
        assert result1.exit_code == result2.exit_code == result3.exit_code == 0 
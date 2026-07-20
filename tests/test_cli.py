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
        # Use a non-existent env file to prevent loading from .env
        with patch.dict('os.environ', clear=True):
            config = BaseConfig(_env_file="/nonexistent/env/file")
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

    def test_cli_sdk_commands(self, runner):
        """Test the SDK command group and its subcommands."""
        result = runner.invoke(cli, ["sdk", "--help"])

        assert result.exit_code == 0
        assert "create" in result.output
        assert "template" in result.output

        create_help = runner.invoke(cli, ["sdk", "create", "--help"])

        assert create_help.exit_code == 0
        assert "--collect-mixin" in create_help.output
        assert "--update-db" in create_help.output

    def test_cli_sdk_template_creates_valid_config(self, runner, tmp_path):
        """The SDK template command should create a config accepted by VendorConfig."""
        from opensampl.create.create_vendor import VendorConfig

        config_path = tmp_path / "probe.yaml"

        result = runner.invoke(cli, ["sdk", "template", str(config_path)])

        assert result.exit_code == 0
        assert config_path.is_file()
        assert str(config_path) in result.output

        config = VendorConfig.from_config_file(config_path)
        assert config.name == "My Vendor"
        assert config.parser_class == "MyVendorProbe"
        assert config.parser_module == "my_vendor"
        assert {field.name for field in config.metadata_fields} == {
            "serial_number",
            "firmware_version",
            "sample_rate_hz",
            "additional_metadata",
        }

    def test_cli_sdk_template_does_not_overwrite_existing_file(self, runner, tmp_path):
        """The SDK template command should leave an existing destination untouched."""
        config_path = tmp_path / "probe.yaml"
        original_content = "user-owned content\n"
        config_path.write_text(original_content)

        result = runner.invoke(cli, ["sdk", "template", str(config_path)])

        assert result.exit_code != 0
        assert config_path.read_text() == original_content

    def test_cli_sdk_template_does_not_create_parent_directories(self, runner, tmp_path):
        """The SDK template command should fail when the destination parent is missing."""
        config_path = tmp_path / "missing" / "probe.yaml"

        result = runner.invoke(cli, ["sdk", "template", str(config_path)])

        assert result.exit_code != 0
        assert "Could not create config template" in result.output
        assert not config_path.parent.exists()

    @patch("opensampl.create.create_vendor.VendorConfig.from_config_file")
    def test_cli_sdk_create_matches_top_level_create(self, mock_from_config, runner, tmp_path):
        """SDK and top-level create commands should invoke the same scaffolding behavior."""
        config_path = tmp_path / "probe.yaml"
        config_path.write_text("name: Test Probe\nmetadata_fields: []\n")
        vendor_config = Mock()
        mock_from_config.return_value = vendor_config

        root_result = runner.invoke(cli, ["create", str(config_path), "--collect-mixin"])
        sdk_result = runner.invoke(cli, ["sdk", "create", str(config_path), "--collect-mixin"])

        assert root_result.exit_code == 0
        assert sdk_result.exit_code == 0
        assert mock_from_config.call_count == 2
        assert vendor_config.create.call_count == 2
        vendor_config.create.assert_called_with(collect_mixin=True)

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

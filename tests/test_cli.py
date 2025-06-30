"""Tests for the CLI module."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from opensampl.cli import cli, path_or_string


@pytest.fixture
def runner():
    """Fixture that provides a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_yaml_file(test_data_dir):
    """Fixture that provides a sample YAML file for testing."""
    yaml_file = test_data_dir / "sample.yaml"
    yaml_content = """
    name: test_probe
    type: test
    config:
      host: localhost
      port: 8080
    """
    yaml_file.write_text(yaml_content)
    return yaml_file


@pytest.fixture
def sample_json_file(test_data_dir):
    """Fixture that provides a sample JSON file for testing."""
    json_file = test_data_dir / "sample.json"
    json_content = {"name": "test_probe", "type": "test", "config": {"host": "localhost", "port": 8080}}
    json_file.write_text(json.dumps(json_content))
    return json_file


def test_cli_import():
    """Test that the CLI module can be imported."""
    from opensampl import cli

    assert cli is not None


def test_cli_help(runner):
    """Test CLI help command."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "CLI utility for openSAMPL" in result.output


def test_init_command(runner):
    """Test database initialization command."""
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "Initializing database" in result.output


def test_config_commands(runner, mock_env_vars):
    """Test config-related commands."""
    # Test config show
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "Variable" in result.output
    assert "Value" in result.output

    # Test config show with explanation
    result = runner.invoke(cli, ["config", "show", "--explain"])
    assert result.exit_code == 0
    assert "Description" in result.output

    # Test config show specific variable
    result = runner.invoke(cli, ["config", "show", "--var", "OPEN_SAMPL_DB_HOST"])
    assert result.exit_code == 0
    assert "OPEN_SAMPL_DB_HOST" in result.output
    assert "localhost" in result.output

    # Test config set
    result = runner.invoke(cli, ["config", "set", "TEST_VAR", "test_value"])
    assert result.exit_code == 0


def test_load_commands(runner, sample_yaml_file, sample_json_file):
    """Test load-related commands."""
    # Test loading YAML file
    result = runner.invoke(cli, ["load", "table", "probe_metadata", str(sample_yaml_file)])
    assert result.exit_code == 0
    assert "Successfully wrote data to table" in result.output

    # Test loading JSON file
    result = runner.invoke(cli, ["load", "table", "probe_metadata", str(sample_json_file)])
    assert result.exit_code == 0
    assert "Successfully wrote data to table" in result.output

    # Test loading with different if-exists options
    for option in ["update", "error", "replace", "ignore"]:
        result = runner.invoke(cli, ["load", "table", "--if-exists", option, "probe_metadata", str(sample_yaml_file)])
        assert result.exit_code == 0


def test_create_command(runner, sample_yaml_file):
    """Test probe creation command."""
    result = runner.invoke(cli, ["create", str(sample_yaml_file)])
    assert result.exit_code == 0

    # Test with database update
    result = runner.invoke(cli, ["create", "--update-db", str(sample_yaml_file)])
    assert result.exit_code == 0


def test_path_or_string():
    """Test path_or_string function."""
    # Test with file path
    test_file = Path("test.yaml")
    test_file.write_text("name: test")
    try:
        result = path_or_string(str(test_file))
        assert result == {"name": "test"}
    finally:
        test_file.unlink()

    # Test with YAML string
    result = path_or_string('{"name": "test"}')
    assert result == {"name": "test"}

    # Test with invalid input
    with pytest.raises(Exception):
        path_or_string("invalid: yaml: content:")


def test_load_invalid_table(runner, sample_yaml_file):
    """Test loading data into invalid table."""
    result = runner.invoke(cli, ["load", "table", "invalid_table", str(sample_yaml_file)])
    assert result.exit_code != 0
    assert "Error" in result.output


def test_load_invalid_file(runner):
    """Test loading invalid file."""
    result = runner.invoke(cli, ["load", "table", "probe_metadata", "nonexistent.yaml"])
    assert result.exit_code != 0
    assert "Error" in result.output


def test_config_invalid_var(runner):
    """Test showing invalid environment variable."""
    result = runner.invoke(cli, ["config", "show", "--var", "INVALID_VAR"])
    assert result.exit_code == 0
    assert "Error" in result.output


def test_case_insensitive_commands(runner):
    """Test case-insensitive command handling."""
    # Test with different cases
    commands = ["INIT", "Init", "init"]
    for cmd in commands:
        result = runner.invoke(cli, [cmd])
        assert result.exit_code == 0

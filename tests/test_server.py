"""Tests for the server module package structure."""

import pkgutil
from pathlib import Path

import pytest


def test_server_package_import():
    """Test that the server package can be imported."""
    import opensampl.server

    assert opensampl.server is not None


def test_server_submodules():
    """Test that all server submodules can be imported."""
    import opensampl.server

    submodules = [name for _, name, _ in pkgutil.iter_modules(opensampl.server.__path__)]
    assert "cli" in submodules
    assert "grafana" in submodules


def test_server_module_files():
    """Test that required server module files exist."""
    server_dir = Path(opensampl.server.__file__).parent
    required_files = ["__init__.py", "cli.py", "grafana.py"]
    for file in required_files:
        assert (server_dir / file).exists(), f"Required file {file} not found in server module"


def test_server_cli_import():
    """Test that the server CLI module can be imported."""
    from opensampl.server import cli

    assert cli is not None


def test_server_grafana_import():
    """Test that the server Grafana module can be imported."""
    from opensampl.server import grafana

    assert grafana is not None


def test_server_cli_commands():
    """Test server CLI commands."""
    assert hasattr(cli, "start_server")
    assert hasattr(cli, "stop_server")
    assert callable(cli.start_server)
    assert callable(cli.stop_server)


def test_grafana_setup(mock_grafana_config):
    """Test Grafana setup functionality."""
    setup_result = setup_grafana(mock_grafana_config)
    assert setup_result is not None
    assert "port" in setup_result
    assert setup_result["port"] == mock_grafana_config["port"]
    assert "datasources" in setup_result
    assert len(setup_result["datasources"]) == len(mock_grafana_config["datasources"])
    assert setup_result["datasources"][0]["name"] == mock_grafana_config["datasources"][0]["name"]


def test_server_env_file(test_data_dir, mock_env_vars):
    """Test server environment file handling."""
    env_file = test_data_dir / "test.env"
    env_content = """
    SERVER_HOST=localhost
    SERVER_PORT=8000
    DEBUG=True
    GRAFANA_PORT=3000
    """
    env_file.write_text(env_content)

    assert env_file.exists()
    # Test env file loading
    from opensampl.server.cli import load_env_file

    config = load_env_file(env_file)
    assert config["SERVER_HOST"] == "localhost"
    assert config["SERVER_PORT"] == "8000"
    assert config["DEBUG"] == "True"
    assert config["GRAFANA_PORT"] == "3000"


@pytest.mark.parametrize(
    "invalid_config",
    [
        {},  # Empty config
        {"host": "localhost"},  # Missing port
        {"port": 8000},  # Missing host
        {"host": "localhost", "port": "invalid"},  # Invalid port type
    ],
)
def test_server_invalid_config(invalid_config):
    """Test server initialization with invalid configurations."""
    with pytest.raises(ValueError):
        cli.start_server(invalid_config)


def test_server_metrics(mock_metrics_data):
    """Test server metrics collection."""
    from opensampl.server.cli import collect_metrics

    metrics = collect_metrics()
    assert metrics is not None
    assert "timestamp" in metrics
    assert "metrics" in metrics
    assert "cpu_usage" in metrics["metrics"]
    assert "memory_usage" in metrics["metrics"]
    assert "disk_usage" in metrics["metrics"]

    # Validate metric ranges
    assert 0 <= metrics["metrics"]["cpu_usage"] <= 100
    assert 0 <= metrics["metrics"]["memory_usage"] <= 100
    assert 0 <= metrics["metrics"]["disk_usage"] <= 100


def test_server_logging(temp_log_file):
    """Test server logging functionality."""
    from opensampl.server.cli import setup_logging

    logger = setup_logging(temp_log_file)
    assert logger is not None

    # Test logging
    test_message = "Test log message"
    logger.info(test_message)

    # Verify log file content
    log_content = temp_log_file.read_text()
    assert test_message in log_content
    assert "INFO" in log_content


def test_server_api_endpoints(mock_api_client):
    """Test server API endpoints."""
    # Test GET endpoint
    response = mock_api_client.get("/api/v1/status")
    assert response["status"] == "success"
    assert "data" in response

    # Test POST endpoint
    response = mock_api_client.post("/api/v1/action", data={"action": "test"})
    assert response["status"] == "success"
    assert "data" in response
    assert "id" in response["data"]

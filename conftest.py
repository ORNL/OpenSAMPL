"""Shared fixtures for pytest."""

import os
import sys
import pytest
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import MagicMock

# Add the project root to the path so pytest can find the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

@pytest.fixture
def test_data_dir() -> Path:
    """Fixture that provides a temporary directory for test data."""
    return Path(__file__).parent / "test_data"

@pytest.fixture
def sample_config() -> dict:
    """Fixture that provides a sample configuration for testing."""
    return {
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "test_db"
        },
        "api": {
            "base_url": "http://localhost:8000",
            "timeout": 30
        }
    }

@pytest.fixture
def mock_env_vars(monkeypatch) -> None:
    """Fixture that sets up mock environment variables for testing."""
    monkeypatch.setenv("OPEN_SAMPL_DB_HOST", "localhost")
    monkeypatch.setenv("OPEN_SAMPL_DB_PORT", "5432")
    monkeypatch.setenv("OPEN_SAMPL_API_KEY", "test_api_key")

@pytest.fixture
def temp_db_file(tmp_path) -> Generator[Path, None, None]:
    """Fixture that provides a temporary database file for testing."""
    db_file = tmp_path / "test.db"
    yield db_file
    if db_file.exists():
        db_file.unlink()

@pytest.fixture
def db_session(temp_db_file) -> Generator[Session, None, None]:
    """Fixture that provides a database session for testing."""
    engine = create_engine(f"sqlite:///{temp_db_file}")
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def mock_api_response() -> Dict[str, Any]:
    """Fixture that provides a mock API response for testing."""
    return {
        "status": "success",
        "data": {
            "id": 1,
            "name": "test_item",
            "value": 42
        }
    }

@pytest.fixture
def mock_api_client() -> MagicMock:
    """Fixture that provides a mock API client for testing."""
    mock = MagicMock()
    mock.get.return_value = {
        "status": "success",
        "data": {"id": 1}
    }
    mock.post.return_value = {
        "status": "success",
        "data": {"id": 2}
    }
    return mock

@pytest.fixture
def temp_yaml_file(tmp_path) -> Generator[Path, None, None]:
    """Fixture that provides a temporary YAML file for testing."""
    yaml_file = tmp_path / "test_config.yaml"
    yaml_content = """
    vendors:
      - name: test_vendor
        type: test
        config:
          host: localhost
          port: 8080
    """
    yaml_file.write_text(yaml_content)
    yield yaml_file
    if yaml_file.exists():
        yaml_file.unlink()

@pytest.fixture
def mock_vendor_data() -> Dict[str, Any]:
    """Fixture that provides mock vendor data for testing."""
    return {
        "name": "test_vendor",
        "type": "adva",
        "config": {
            "host": "localhost",
            "port": 8080,
            "timeout": 30
        },
        "credentials": {
            "username": "test_user",
            "password": "test_pass"
        }
    }

@pytest.fixture
def mock_grafana_config() -> Dict[str, Any]:
    """Fixture that provides mock Grafana configuration for testing."""
    return {
        "enabled": True,
        "port": 3000,
        "admin_user": "admin",
        "admin_password": "admin",
        "datasources": [
            {
                "name": "TestDB",
                "type": "postgres",
                "url": "localhost:5432",
                "database": "test_db"
            }
        ]
    }

@pytest.fixture
def mock_user_data() -> Dict[str, Any]:
    """Fixture that provides mock user data for testing."""
    return {
        "username": "test_user",
        "email": "test@example.com",
        "password": "test_password",
        "role": "admin",
        "permissions": ["read", "write", "delete"]
    }

@pytest.fixture
def mock_role_data() -> Dict[str, Any]:
    """Fixture that provides mock role data for testing."""
    return {
        "name": "admin",
        "permissions": ["read", "write", "delete"],
        "description": "Administrator role"
    }

@pytest.fixture
def mock_http_response() -> MagicMock:
    """Fixture that provides a mock HTTP response for testing."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "status": "success",
        "data": {"id": 1}
    }
    return mock

@pytest.fixture
def temp_log_file(tmp_path) -> Generator[Path, None, None]:
    """Fixture that provides a temporary log file for testing."""
    log_file = tmp_path / "test.log"
    yield log_file
    if log_file.exists():
        log_file.unlink()

@pytest.fixture
def mock_metrics_data() -> Dict[str, Any]:
    """Fixture that provides mock metrics data for testing."""
    return {
        "timestamp": "2024-03-20T10:00:00Z",
        "metrics": {
            "cpu_usage": 45.5,
            "memory_usage": 60.2,
            "disk_usage": 75.8
        }
    }
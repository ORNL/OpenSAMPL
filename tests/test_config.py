"""
Tests for the config module.

This module tests the configuration functionality including default values,
environment variable handling, and validation.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from opensampl.config.base import BaseConfig
from opensampl.config.server import ServerConfig


class TestBaseConfig:
    """Test BaseConfig functionality."""

    def test_base_config_defaults(self):
        """Test BaseConfig with default values."""
        # Clear environment and use a non-existent env file to prevent loading
        with patch.dict('os.environ', clear=True):
            config = BaseConfig(_env_file="/nonexistent/env/file")
            
            # Test default values
            assert config.DATABASE_URL is None
            assert config.BACKEND_URL is None
            assert config.ROUTE_TO_BACKEND is False
            assert config.ARCHIVE_PATH == Path("archive")
            assert config.LOG_LEVEL == "INFO"
            assert config.API_KEY is None
            assert config.INSECURE_REQUESTS is False

    def test_base_config_custom_values(self):
        """Test BaseConfig with custom values."""
        config = BaseConfig(
            DATABASE_URL="postgresql://test:5432/testdb",
            BACKEND_URL="http://localhost:8000",
            ROUTE_TO_BACKEND=True,
            LOG_LEVEL="DEBUG"
        )
        
        assert config.DATABASE_URL == "postgresql://test:5432/testdb"
        assert config.BACKEND_URL == "http://localhost:8000"
        assert config.ROUTE_TO_BACKEND is True
        assert config.LOG_LEVEL == "DEBUG"

    def test_base_config_env_vars(self):
        """Test BaseConfig with environment variables."""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'postgresql://env:5432/envdb',
            'LOG_LEVEL': 'WARNING',
            'ROUTE_TO_BACKEND': 'true'
        }):
            config = BaseConfig()
            
            assert config.DATABASE_URL == 'postgresql://env:5432/envdb'
            assert config.LOG_LEVEL == 'WARNING'
            assert config.ROUTE_TO_BACKEND is True

    def test_base_config_validation(self):
        """Test BaseConfig validation."""
        # Should work with valid data
        config = BaseConfig(DATABASE_URL="postgresql://test:5432/testdb")
        assert config.DATABASE_URL == "postgresql://test:5432/testdb"

        # Should work with routing enabled
        config = BaseConfig(ROUTE_TO_BACKEND=True, BACKEND_URL="http://localhost:8000")
        assert config.ROUTE_TO_BACKEND is True
        assert config.BACKEND_URL == "http://localhost:8000"

    def test_base_config_backend_routing_dependencies(self):
        """Test backend routing dependency checking."""
        config = BaseConfig(ROUTE_TO_BACKEND=True)
        
        # Should raise error when backend routing is enabled but URL is not set
        with pytest.raises(ValueError, match="BACKEND_URL must be set if ROUTE_TO_BACKEND is True"):
            config.check_routing_dependencies()

    def test_base_config_database_routing_dependencies(self):
        """Test database routing dependency checking."""
        # Use a non-existent env file to prevent loading from .env
        with patch.dict('os.environ', clear=True):
            config = BaseConfig(ROUTE_TO_BACKEND=False, _env_file="/nonexistent/env/file")
            
            # Should raise error when database routing is disabled but URL is not set
            with pytest.raises(ValueError, match="DATABASE_URL must be set if ROUTE_TO_BACKEND is False"):
                config.check_routing_dependencies()


class TestServerConfig:
    """Test ServerConfig functionality."""

    def test_server_config_defaults(self):
        """Test ServerConfig with default values."""
        # Clear environment and use a non-existent env file to prevent loading
        with patch.dict('os.environ', clear=True):
            config = ServerConfig(_env_file="/nonexistent/env/file")
            
            # Test default values
            assert config.DATABASE_URL is None
            assert config.BACKEND_URL is None
            assert config.ROUTE_TO_BACKEND is False
            assert config.ARCHIVE_PATH == Path("archive")
            assert config.LOG_LEVEL == "INFO"
            assert config.API_KEY is None
            assert config.INSECURE_REQUESTS is False
            assert config.COMPOSE_FILE != ""
            assert config.DOCKER_ENV_FILE != ""
            assert hasattr(config, "docker_env_values")

    def test_server_config_custom_values(self):
        """Test ServerConfig with custom values."""
        config = ServerConfig(
            DATABASE_URL="postgresql://test:5432/testdb",
            COMPOSE_FILE="/custom/compose.yaml",
            DOCKER_ENV_FILE="/custom/env"
        )
        
        assert config.DATABASE_URL == "postgresql://test:5432/testdb"
        assert config.COMPOSE_FILE == "/custom/compose.yaml"
        assert config.DOCKER_ENV_FILE == "/custom/env"

    def test_server_config_env_vars(self):
        """Test ServerConfig with environment variables."""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'postgresql://env:5432/envdb',
            'OPENSAMPL_SERVER__COMPOSE_FILE': '/env/compose.yaml',
            'OPENSAMPL_SERVER__DOCKER_ENV_FILE': '/env/env'
        }):
            config = ServerConfig()
            
            assert config.DATABASE_URL == 'postgresql://env:5432/envdb'
            assert config.COMPOSE_FILE == '/env/compose.yaml'
            assert config.DOCKER_ENV_FILE == '/env/env'

    def test_server_config_inherits_base_config(self):
        """Test that ServerConfig inherits from BaseConfig."""
        config = ServerConfig()
        
        # Should have all BaseConfig fields
        assert hasattr(config, 'DATABASE_URL')
        assert hasattr(config, 'BACKEND_URL')
        assert hasattr(config, 'ROUTE_TO_BACKEND')
        assert hasattr(config, 'ARCHIVE_PATH')
        assert hasattr(config, 'LOG_LEVEL')
        assert hasattr(config, 'API_KEY')
        assert hasattr(config, 'INSECURE_REQUESTS')
        
        # Should have ServerConfig-specific fields
        assert hasattr(config, 'COMPOSE_FILE')
        assert hasattr(config, 'DOCKER_ENV_FILE')
        assert hasattr(config, 'docker_env_values')

    @patch('opensampl.config.server.check_command')
    def test_get_compose_command(self, mock_check_command):
        """Test get_compose_command method."""
        # Test docker-compose
        mock_check_command.side_effect = lambda cmd: cmd == ["docker-compose", "--version"]
        command = ServerConfig.get_compose_command()
        assert command == "docker-compose"

        # Test docker compose
        mock_check_command.side_effect = lambda cmd: cmd == ["docker", "compose", "--version"]
        command = ServerConfig.get_compose_command()
        assert command == "docker compose"

        # Test neither available
        mock_check_command.return_value = False
        mock_check_command.side_effect = lambda cmd: False
        with pytest.raises(ImportError):
            ServerConfig.get_compose_command()

    def test_build_docker_compose_base(self):
        """Test build_docker_compose_base method."""
        with patch.object(ServerConfig, 'get_compose_command', return_value="docker-compose"):
            config = ServerConfig()
            command = config.build_docker_compose_base()
            
            assert command[0] == "docker-compose"
            assert "--env-file" in command
            assert "-f" in command

    def test_get_db_url(self):
        """Test get_db_url method."""
        config = ServerConfig()
        config.docker_env_values = {
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
            "POSTGRES_DB": "testdb"
        }
        
        db_url = config.get_db_url()
        assert db_url == "postgresql://testuser:testpass@localhost:5415/testdb"

        # Test missing environment variables
        config.docker_env_values = {}
        with pytest.raises(ValueError):
            config.get_db_url()


class TestConfigIntegration:
    """Test configuration integration scenarios."""

    def test_config_with_env_file(self, tmp_path):
        """Test configuration with environment file."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
DATABASE_URL=postgresql://envfile:5432/envfiledb
LOG_LEVEL=DEBUG
ROUTE_TO_BACKEND=true
        """)
        
        with patch.dict('os.environ', clear=True):
            config = BaseConfig(_env_file=str(env_file))
            
            assert config.DATABASE_URL == "postgresql://envfile:5432/envfiledb"
            assert config.LOG_LEVEL == "DEBUG"
            assert config.ROUTE_TO_BACKEND is True

    def test_config_priority(self):
        """Test configuration priority (kwargs > env vars > defaults)."""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'postgresql://env:5432/envdb',
            'LOG_LEVEL': 'WARNING'
        }):
            # kwargs should override env vars
            config = BaseConfig(
                DATABASE_URL="postgresql://kwargs:5432/kwargsdb",
                LOG_LEVEL="ERROR"
            )
            
            assert config.DATABASE_URL == "postgresql://kwargs:5432/kwargsdb"
            assert config.LOG_LEVEL == "ERROR" 
"""Tests for the opensampl.config module."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from opensampl.config.base import BaseConfig
from opensampl.config.server import ServerConfig


class TestBaseConfig:
    """Test the BaseConfig class."""

    def test_base_config_defaults(self):
        """Test BaseConfig with default values."""
        config = BaseConfig()
        
        # Test default values
        assert config.DATABASE_URL is None  # No default in actual config
        assert config.LOG_LEVEL == "INFO"
        assert config.ROUTE_TO_BACKEND is False
        assert config.ARCHIVE_PATH == Path("archive")

    def test_base_config_custom_values(self):
        """Test BaseConfig with custom values."""
        config = BaseConfig(
            DATABASE_URL="postgresql://test:5432/testdb",
            LOG_LEVEL="DEBUG",
            ROUTE_TO_BACKEND=True,
            ARCHIVE_PATH="/custom/archive"
        )
        
        assert config.DATABASE_URL == "postgresql://test:5432/testdb"
        assert config.LOG_LEVEL == "DEBUG"
        assert config.ROUTE_TO_BACKEND is True
        assert config.ARCHIVE_PATH == Path("/custom/archive")

    def test_base_config_env_vars(self):
        """Test BaseConfig with environment variables."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://env:5432/envdb",
            "LOG_LEVEL": "WARNING",
            "ROUTE_TO_BACKEND": "true",
            "ARCHIVE_PATH": "/env/archive"
        }):
            config = BaseConfig()
            
            assert config.DATABASE_URL == "postgresql://env:5432/envdb"
            assert config.LOG_LEVEL == "WARNING"
            assert config.ROUTE_TO_BACKEND is True
            assert config.ARCHIVE_PATH == Path("/env/archive")

    def test_base_config_validation(self):
        """Test BaseConfig validation."""
        # Test invalid boolean
        with pytest.raises(ValidationError):
            BaseConfig(ROUTE_TO_BACKEND="not_a_boolean")

    def test_base_config_backend_routing_dependencies(self):
        """Test backend routing dependency checking."""
        config = BaseConfig(ROUTE_TO_BACKEND=True)
        
        # Should raise error when backend routing is enabled but URL is not set
        with pytest.raises(ValueError, match="BACKEND_URL must be set if ROUTE_TO_BACKEND is True"):
            config.check_routing_dependencies()

        # Should not raise error when backend routing is disabled and DATABASE_URL is set
        config.ROUTE_TO_BACKEND = False
        config.DATABASE_URL = "postgresql://localhost/testdb"
        config.check_routing_dependencies()  # Should not raise

        # Should not raise error when backend routing is enabled and URL is set
        config.ROUTE_TO_BACKEND = True
        config.BACKEND_URL = "http://localhost:8000"
        config.check_routing_dependencies()  # Should not raise

    def test_base_config_database_routing_dependencies(self):
        """Test database routing dependency checking."""
        config = BaseConfig(ROUTE_TO_BACKEND=False)
        
        # Should raise error when database routing is disabled but URL is not set
        with pytest.raises(ValueError, match="DATABASE_URL must be set if ROUTE_TO_BACKEND is False"):
            config.check_routing_dependencies()

        # Should not raise error when database URL is set
        config.DATABASE_URL = "postgresql://localhost/testdb"
        config.check_routing_dependencies()  # Should not raise


class TestServerConfig:
    """Test the ServerConfig class."""

    def test_server_config_defaults(self):
        """Test ServerConfig with default values."""
        config = ServerConfig()
        
        # Test default values
        assert config.COMPOSE_FILE != ""  # Should be resolved to actual path
        assert config.DOCKER_ENV_FILE != ""  # Should be resolved to actual path
        assert hasattr(config, "docker_env_values")

    def test_server_config_custom_values(self):
        """Test ServerConfig with custom values."""
        config = ServerConfig(
            DATABASE_URL="postgresql://test:5432/testdb",
            LOG_LEVEL="DEBUG",
            ROUTE_TO_BACKEND=True,
            COMPOSE_FILE="/custom/compose.yaml",
            DOCKER_ENV_FILE="/custom/env"
        )
        
        assert config.DATABASE_URL == "postgresql://test:5432/testdb"
        assert config.LOG_LEVEL == "DEBUG"
        assert config.ROUTE_TO_BACKEND is True
        assert config.COMPOSE_FILE == "/custom/compose.yaml"
        assert config.DOCKER_ENV_FILE == "/custom/env"

    def test_server_config_env_vars(self):
        """Test ServerConfig with environment variables."""
        with patch.dict(os.environ, {
            "OPENSAMPL_SERVER__COMPOSE_FILE": "/env/compose.yaml",
            "OPENSAMPL_SERVER__DOCKER_ENV_FILE": "/env/env",
            "DATABASE_URL": "postgresql://env:5432/envdb",
            "LOG_LEVEL": "WARNING"
        }):
            config = ServerConfig()
            
            assert config.COMPOSE_FILE == "/env/compose.yaml"
            assert config.DOCKER_ENV_FILE == "/env/env"
            assert config.DATABASE_URL == "postgresql://env:5432/envdb"
            assert config.LOG_LEVEL == "WARNING"

    def test_server_config_inherits_base_config(self):
        """Test that ServerConfig inherits from BaseConfig."""
        config = ServerConfig()
        
        # Should have BaseConfig fields
        assert hasattr(config, "DATABASE_URL")
        assert hasattr(config, "LOG_LEVEL")
        assert hasattr(config, "ROUTE_TO_BACKEND")
        
        # Should have ServerConfig fields
        assert hasattr(config, "COMPOSE_FILE")
        assert hasattr(config, "DOCKER_ENV_FILE")
        assert hasattr(config, "docker_env_values")

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
    """Integration tests for configuration."""

    def test_config_with_env_file(self, tmp_path):
        """Test configuration loading from environment file."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
DATABASE_URL=postgresql://test:5432/testdb
LOG_LEVEL=DEBUG
ROUTE_TO_BACKEND=true
OPENSAMPL_SERVER__COMPOSE_FILE=/custom/compose.yaml
        """)
        
        with patch.dict(os.environ, {}, clear=True):
            config = ServerConfig(_env_file=str(env_file))
            
            assert config.DATABASE_URL == "postgresql://test:5432/testdb"
            assert config.LOG_LEVEL == "DEBUG"
            assert config.ROUTE_TO_BACKEND is True
            assert config.COMPOSE_FILE == "/custom/compose.yaml"

    def test_config_priority(self):
        """Test that explicit values override environment variables."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://env:5432/envdb",
            "LOG_LEVEL": "WARNING"
        }):
            config = BaseConfig(
                DATABASE_URL="postgresql://explicit:5432/explicitdb",
                LOG_LEVEL="DEBUG"
            )
            
            # Explicit values should override environment variables
            assert config.DATABASE_URL == "postgresql://explicit:5432/explicitdb"
            assert config.LOG_LEVEL == "DEBUG" 
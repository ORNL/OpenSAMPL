"""Tests for the ConfigManager module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from opensampl.helpers.config_manager import ConfigManager


class TestConfigManager:
    """Test cases for ConfigManager."""

    def test_init(self):
        """Test ConfigManager initialization."""
        config_manager = ConfigManager()
        assert config_manager.config_file == "config"

    def test_read_config_empty_file(self, tmp_path):
        """Test reading from empty config file."""
        config_file = tmp_path / "config"
        config_file.write_text("")
        
        with patch.object(ConfigManager, 'get_config_path', return_value=config_file):
            config_manager = ConfigManager()
            config = config_manager.read_config()
            assert config == {}

    def test_read_config_with_values(self, tmp_path):
        """Test reading config file with values."""
        config_file = tmp_path / "config"
        config_content = """# Test config
KEY1=value1
KEY2=value2
# Comment line
KEY3=value3
"""
        config_file.write_text(config_content)
        
        with patch.object(ConfigManager, 'get_config_path', return_value=config_file):
            config_manager = ConfigManager()
            config = config_manager.read_config()
            assert config == {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}

    def test_write_config(self, tmp_path):
        """Test writing config file."""
        config_file = tmp_path / "config"
        
        with patch.object(ConfigManager, 'get_config_path', return_value=config_file):
            config_manager = ConfigManager()
            config = {"KEY1": "value1", "KEY2": "value2"}
            config_manager.write_config(config)
            
            assert config_file.exists()
            content = config_file.read_text()
            assert "KEY1=value1" in content
            assert "KEY2=value2" in content
            assert "# openSAMPL Configuration" in content

    def test_set_and_get_config_value(self, tmp_path):
        """Test setting and getting a single config value."""
        config_file = tmp_path / "config"
        
        with patch.object(ConfigManager, 'get_config_path', return_value=config_file):
            config_manager = ConfigManager()
            
            # Set a value
            config_manager.set_config_value("TEST_KEY", "test_value")
            
            # Get the value
            value = config_manager.get_config_value("TEST_KEY")
            assert value == "test_value"
            
            # Get non-existent value
            value = config_manager.get_config_value("NON_EXISTENT")
            assert value is None

    def test_create_systemd_service(self):
        """Test systemd service creation."""
        config_manager = ConfigManager()
        service_content = config_manager.create_systemd_service(
            "test-service", "testuser", Path("/test/dir")
        )
        
        assert "[Unit]" in service_content
        assert "Description=openSAMPL Data Processing Service" in service_content
        assert "User=testuser" in service_content
        assert "WorkingDirectory=/test/dir" in service_content
        assert "ExecStart=/usr/bin/env opensampl-server up" in service_content 
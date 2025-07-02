"""Tests for the constants module."""

import pytest
from pathlib import Path

from opensampl.constants import ENV_VARS, EnvVar


def test_constants_import():
    """Test that the constants module can be imported."""
    from opensampl import constants

    assert constants is not None


def test_env_vars_class_exists():
    """Test that the ENV_VARS class exists and has expected attributes."""
    assert hasattr(ENV_VARS, "ROUTE_TO_BACKEND")
    assert hasattr(ENV_VARS, "BACKEND_URL")
    assert hasattr(ENV_VARS, "DATABASE_URL")
    assert hasattr(ENV_VARS, "ARCHIVE_PATH")
    assert hasattr(ENV_VARS, "LOG_LEVEL")
    assert hasattr(ENV_VARS, "API_KEY")
    assert hasattr(ENV_VARS, "SYSTEMD_SERVICE_NAME")
    assert hasattr(ENV_VARS, "SYSTEMD_USER")
    assert hasattr(ENV_VARS, "SYSTEMD_WORKING_DIRECTORY")
    assert hasattr(ENV_VARS, "SYSTEMD_CONFIG_DIR")
    assert hasattr(ENV_VARS, "SYSTEMD_USER_CONFIG_DIR")


def test_env_var_instances():
    """Test that ENV_VARS attributes are EnvVar instances."""
    for var in ENV_VARS.all():
        assert isinstance(var, EnvVar)


@pytest.mark.parametrize(
    "var_name,expected_type",
    [
        ("ROUTE_TO_BACKEND", bool),
        ("BACKEND_URL", str),
        ("DATABASE_URL", str),
        ("ARCHIVE_PATH", Path),
        ("LOG_LEVEL", str),
        ("API_KEY", str),
        ("SYSTEMD_SERVICE_NAME", str),
        ("SYSTEMD_USER", str),
        ("SYSTEMD_WORKING_DIRECTORY", Path),
        ("SYSTEMD_CONFIG_DIR", Path),
        ("SYSTEMD_USER_CONFIG_DIR", Path),
    ],
)
def test_env_var_types(var_name, expected_type):
    """Test that environment variables have the correct types."""
    var = getattr(ENV_VARS, var_name)
    assert isinstance(var, EnvVar)
    assert var.type_ == expected_type


def test_env_var_defaults():
    """Test that environment variables have appropriate default values."""
    # Test some key defaults
    assert ENV_VARS.LOG_LEVEL.default == "INFO"
    assert ENV_VARS.SYSTEMD_SERVICE_NAME.default == "opensampl"
    assert ENV_VARS.SYSTEMD_USER.default == "opensampl"
    assert ENV_VARS.SYSTEMD_WORKING_DIRECTORY.default == "/opt/opensampl"
    assert ENV_VARS.SYSTEMD_CONFIG_DIR.default == "/etc/opensampl"
    assert ENV_VARS.SYSTEMD_USER_CONFIG_DIR.default == "$HOME/.config/opensampl"


def test_env_vars_iteration():
    """Test that ENV_VARS can be iterated over."""
    vars_list = ENV_VARS.all()
    assert len(vars_list) > 0
    assert all(isinstance(var, EnvVar) for var in vars_list)


def test_env_vars_get_method():
    """Test the get method of ENV_VARS."""
    # Test getting a known variable
    result = ENV_VARS.get("LOG_LEVEL")
    assert result is not None
    
    # Test getting a non-existent variable
    result = ENV_VARS.get("NON_EXISTENT_VAR")
    assert result is None


def test_env_vars_all_method():
    """Test the all method of ENV_VARS."""
    all_vars = ENV_VARS.all()
    assert isinstance(all_vars, list)
    assert len(all_vars) > 0
    assert all(isinstance(var, EnvVar) for var in all_vars)


def test_get_config_dir_method():
    """Test the get_config_dir method."""
    config_dir = ENV_VARS.get_config_dir()
    assert isinstance(config_dir, Path)

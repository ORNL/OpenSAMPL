"""Tests for the constants module."""

import pytest
from opensampl.constants import *

def test_constants_import():
    """Test that the constants module can be imported."""
    from opensampl import constants
    assert constants is not None

def test_constants_exist():
    """Test that essential constants are defined."""
    # Database related constants
    assert hasattr(constants, "DEFAULT_DB_HOST")
    assert hasattr(constants, "DEFAULT_DB_PORT")
    assert hasattr(constants, "DEFAULT_DB_NAME")
    
    # API related constants
    assert hasattr(constants, "API_TIMEOUT")
    assert hasattr(constants, "API_RETRY_COUNT")
    
    # File path constants
    assert hasattr(constants, "CONFIG_DIR")
    assert hasattr(constants, "DATA_DIR")

@pytest.mark.parametrize("constant_name,expected_type", [
    ("DEFAULT_DB_HOST", str),
    ("DEFAULT_DB_PORT", int),
    ("DEFAULT_DB_NAME", str),
    ("API_TIMEOUT", int),
    ("API_RETRY_COUNT", int),
    ("CONFIG_DIR", str),
    ("DATA_DIR", str),
])
def test_constant_types(constant_name, expected_type):
    """Test that constants have the correct types."""
    constant = globals().get(constant_name)
    assert constant is not None, f"Constant {constant_name} is not defined"
    assert isinstance(constant, expected_type), \
        f"Constant {constant_name} should be of type {expected_type.__name__}"

def test_constant_values():
    """Test that constants have valid values."""
    # Database constants
    assert DEFAULT_DB_HOST in ["localhost", "127.0.0.1"]
    assert 1024 <= DEFAULT_DB_PORT <= 65535
    assert DEFAULT_DB_NAME
    
    # API constants
    assert API_TIMEOUT > 0
    assert API_RETRY_COUNT >= 0
    
    # Path constants
    assert CONFIG_DIR
    assert DATA_DIR 
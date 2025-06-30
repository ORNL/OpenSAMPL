"""Tests for the vendors module."""

import pytest
from pathlib import Path
from opensampl.vendors import base_probe, adva
from opensampl.vendors.constants import VENDOR_TYPES

def test_vendors_import():
    """Test that the vendors module can be imported."""
    from opensampl import vendors
    assert vendors is not None

def test_base_probe_import():
    """Test that the base probe module can be imported."""
    from opensampl.vendors import base_probe
    assert base_probe is not None

def test_base_probe_class():
    """Test the BaseProbe class initialization."""
    probe = base_probe.BaseProbe("test_vendor", {})
    assert probe is not None
    assert probe.name == "test_vendor"
    assert hasattr(probe, "connect")
    assert hasattr(probe, "disconnect")
    assert hasattr(probe, "get_data")
    assert hasattr(probe, "is_connected")
    assert hasattr(probe, "validate_config")

def test_adva_vendor(mock_vendor_data):
    """Test Adva vendor implementation."""
    adva_vendor = adva.AdvaVendor(
        mock_vendor_data["name"],
        mock_vendor_data["config"],
        mock_vendor_data["credentials"]
    )
    assert adva_vendor is not None
    assert adva_vendor.name == mock_vendor_data["name"]
    assert adva_vendor.type == "adva"
    assert adva_vendor.config == mock_vendor_data["config"]
    assert adva_vendor.credentials == mock_vendor_data["credentials"]

@pytest.mark.parametrize("vendor_type", VENDOR_TYPES)
def test_vendor_types(vendor_type):
    """Test that all vendor types are properly defined."""
    assert vendor_type in VENDOR_TYPES
    if vendor_type == "adva":
        assert hasattr(adva, "AdvaVendor")
        assert issubclass(adva.AdvaVendor, base_probe.BaseProbe)

def test_vendor_connection(mock_vendor_data, mock_api_client):
    """Test vendor connection functionality."""
    vendor = adva.AdvaVendor(
        mock_vendor_data["name"],
        mock_vendor_data["config"],
        mock_vendor_data["credentials"]
    )
    
    # Test connection
    try:
        vendor.connect()
        assert vendor.is_connected()
        assert vendor.get_connection_status() == "connected"
        
        # Test data retrieval
        data = vendor.get_data()
        assert data is not None
        assert "status" in data
        assert "metrics" in data
    finally:
        vendor.disconnect()
        assert not vendor.is_connected()
        assert vendor.get_connection_status() == "disconnected"

@pytest.mark.parametrize("invalid_credentials", [
    {},  # Empty credentials
    {"username": "test"},  # Missing password
    {"password": "test"},  # Missing username
    {"username": "", "password": "test"},  # Empty username
    {"username": "test", "password": ""},  # Empty password
])
def test_vendor_invalid_credentials(mock_vendor_data, invalid_credentials):
    """Test vendor initialization with invalid credentials."""
    with pytest.raises(ValueError):
        adva.AdvaVendor(
            mock_vendor_data["name"],
            mock_vendor_data["config"],
            invalid_credentials
        )

def test_vendor_metrics_collection(mock_vendor_data, mock_metrics_data):
    """Test vendor metrics collection."""
    vendor = adva.AdvaVendor(
        mock_vendor_data["name"],
        mock_vendor_data["config"],
        mock_vendor_data["credentials"]
    )
    
    metrics = vendor.collect_metrics()
    assert metrics is not None
    assert "timestamp" in metrics
    assert "metrics" in metrics
    assert all(key in metrics["metrics"] for key in ["cpu_usage", "memory_usage", "disk_usage"])
    
    # Validate metric ranges
    for value in metrics["metrics"].values():
        assert 0 <= value <= 100

def test_vendor_error_handling(mock_vendor_data):
    """Test vendor error handling."""
    vendor = adva.AdvaVendor(
        mock_vendor_data["name"],
        mock_vendor_data["config"],
        mock_vendor_data["credentials"]
    )
    
    # Test connection timeout
    vendor.config["timeout"] = 0.001  # Set very short timeout
    with pytest.raises(TimeoutError):
        vendor.connect()
    
    # Test invalid data format
    with pytest.raises(ValueError):
        vendor.process_data({"invalid": "format"})

def test_vendor_logging(mock_vendor_data, temp_log_file):
    """Test vendor logging functionality."""
    vendor = adva.AdvaVendor(
        mock_vendor_data["name"],
        mock_vendor_data["config"],
        mock_vendor_data["credentials"]
    )
    
    # Test logging
    test_message = "Test vendor log message"
    vendor.log_event(test_message)
    
    # Verify log file content
    log_content = temp_log_file.read_text()
    assert test_message in log_content
    assert vendor.name in log_content 
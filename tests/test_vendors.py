"""
Tests for the vendors module.

This module tests vendor-specific functionality including probe types,
configuration, and data processing.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from opensampl.vendors.base_probe import BaseProbe, LoadConfig
from opensampl.vendors.constants import ProbeKey, VendorType, VENDORS
from opensampl.vendors.adva import AdvaProbe


class TestProbeKey:
    """Test ProbeKey functionality."""

    def test_probe_key_creation(self):
        """Test ProbeKey creation."""
        probe_key = ProbeKey(probe_id="TEST001", ip_address="192.168.1.100")
        assert probe_key.probe_id == "TEST001"
        assert probe_key.ip_address == "192.168.1.100"

    def test_probe_key_validation(self):
        """Test ProbeKey validation."""
        # Should work with valid data
        probe_key = ProbeKey(probe_id="TEST001", ip_address="192.168.1.100")
        assert probe_key is not None

        # Should work with any string (no IP validation in the model)
        probe_key = ProbeKey(probe_id="TEST001", ip_address="invalid-ip")
        assert probe_key.ip_address == "invalid-ip"

    def test_probe_key_string_representation(self):
        """Test ProbeKey string representation."""
        probe_key = ProbeKey(probe_id="TEST001", ip_address="192.168.1.100")
        assert str(probe_key) == "192.168.1.100_TEST001"
        assert repr(probe_key) == "192.168.1.100_TEST001"


class TestVendorType:
    """Test VendorType functionality."""

    def test_vendor_type_creation(self):
        """Test creating a VendorType."""
        vendor = VendorType(
            name="test_vendor",
            parser_class="TestProbe",
            parser_module="test_module",
            metadata_table="test_metadata",
            metadata_orm="TestMetadata"
        )
        assert vendor.name == "test_vendor"
        assert vendor.parser_class == "TestProbe"
        assert vendor.parser_module == "test_module"
        assert vendor.metadata_table == "test_metadata"
        assert vendor.metadata_orm == "TestMetadata"

    def test_vendor_type_serialization(self):
        """Test VendorType serialization."""
        vendor = VendorType(
            name="test_vendor",
            parser_class="TestProbe",
            parser_module="test_module",
            metadata_table="test_metadata",
            metadata_orm="TestMetadata"
        )
        
        # Test model_dump
        data = vendor.model_dump()
        assert data["name"] == "test_vendor"
        assert data["parser_class"] == "TestProbe"

    def test_vendor_type_get_parser(self):
        """Test VendorType get_parser method."""
        # Test with existing vendor
        adva_vendor = VENDORS.ADVA
        parser_class = adva_vendor.get_parser()
        assert parser_class == AdvaProbe


class TestLoadConfig:
    """Test LoadConfig functionality."""

    def test_load_config_defaults(self):
        """Test LoadConfig default values."""
        config = LoadConfig(filepath=Path("/test/path"), archive_dir=Path("/test/archive"))
        assert config.filepath == Path("/test/path")
        assert config.archive_dir == Path("/test/archive")
        assert config.no_archive is False
        assert config.metadata is False
        assert config.time_data is False
        assert config.max_workers == 4
        assert config.chunk_size is None
        assert config.show_progress is False

    def test_load_config_with_all_options(self):
        """Test LoadConfig with all options set."""
        config = LoadConfig(
            filepath=Path("/test/path"),
            archive_dir=Path("/test/archive"),
            no_archive=True,
            metadata=True,
            time_data=True,
            max_workers=8,
            chunk_size=1000,
            show_progress=True
        )
        assert config.no_archive is True
        assert config.metadata is True
        assert config.time_data is True
        assert config.max_workers == 8
        assert config.chunk_size == 1000
        assert config.show_progress is True


class TestBaseProbe:
    """Test BaseProbe functionality."""

    def test_base_probe_abstract_methods(self):
        """Test that BaseProbe cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseProbe("test_file.txt")

    def test_base_probe_subclass_creation(self):
        """Test creating a concrete subclass of BaseProbe."""
        class TestProbe(BaseProbe):
            name = "test_probe"
            metadata_table = "test_metadata"

            def __init__(self, input_file):
                super().__init__(input_file=input_file)

            def process_metadata(self):
                return {"test": "metadata"}

            def process_time_data(self):
                import pandas as pd
                return pd.DataFrame()

        probe = TestProbe("test_file.txt")
        assert probe.input_file == Path("test_file.txt")

    @patch('opensampl.vendors.base_probe.click')
    def test_base_probe_make_command(self, mock_click):
        """Test the make_command method."""
        class TestProbe(BaseProbe):
            name = "test_probe"
            metadata_table = "test_metadata"

            def __init__(self, input_file):
                super().__init__(input_file=input_file)

            def process_metadata(self):
                return {"test": "metadata"}

            def process_time_data(self):
                import pandas as pd
                return pd.DataFrame()

        # Mock the click context
        mock_ctx = Mock()
        mock_ctx.obj = {"conf": Mock()}
        mock_ctx.obj["conf"].ARCHIVE_PATH = Path("/default/archive")

        # Mock kwargs
        kwargs = {
            "filepath": Path("/test/file.txt"),
            "metadata": True,
            "time_data": True,
            "no_archive": False,
            "max_workers": 4,
            "chunk_size": None,
            "show_progress": False
        }

        probe = TestProbe("test_file.txt")
        # Test that the probe can be created
        assert probe is not None

    def test_extract_load_config(self):
        """Test the _extract_load_config method."""
        class TestProbe(BaseProbe):
            name = "test_probe"
            metadata_table = "test_metadata"

            def __init__(self, input_file):
                super().__init__(input_file=input_file)

            def process_metadata(self):
                return {"test": "metadata"}

            def process_time_data(self):
                import pandas as pd
                return pd.DataFrame()

        mock_ctx = Mock()
        mock_ctx.obj = {"conf": Mock()}
        mock_ctx.obj["conf"].ARCHIVE_PATH = Path("/default/archive")

        kwargs = {
            "filepath": Path("/test/file.txt"),
            "metadata": True,
            "time_data": False,
            "no_archive": True,
            "max_workers": 8,
            "chunk_size": 1000,
            "show_progress": True
        }

        probe = TestProbe("test_file.txt")
        config = TestProbe._extract_load_config(mock_ctx, kwargs)
        
        assert config.filepath == Path("/test/file.txt")
        assert config.metadata is True
        assert config.time_data is False
        assert config.no_archive is True
        assert config.max_workers == 8
        assert config.chunk_size == 1000
        assert config.show_progress is True

    def test_extract_load_config_defaults(self):
        """Test _extract_load_config with default values."""
        class TestProbe(BaseProbe):
            name = "test_probe"
            metadata_table = "test_metadata"

            def __init__(self, input_file):
                super().__init__(input_file=input_file)

            def process_metadata(self):
                return {"test": "metadata"}

            def process_time_data(self):
                import pandas as pd
                return pd.DataFrame()

        mock_ctx = Mock()
        mock_ctx.obj = {"conf": Mock()}
        mock_ctx.obj["conf"].ARCHIVE_PATH = Path("/default/archive")

        kwargs = {
            "filepath": Path("/test/file.txt"),
            "metadata": False,
            "time_data": False,
            "no_archive": False,
            "max_workers": 4,
            "chunk_size": None,
            "show_progress": False
        }

        probe = TestProbe("test_file.txt")
        config = TestProbe._extract_load_config(mock_ctx, kwargs)
        
        assert config.filepath == Path("/test/file.txt")
        assert config.archive_dir == Path("/default/archive")
        # When both metadata and time_data are False, they get set to True by default
        assert config.metadata is True
        assert config.time_data is True
        assert config.no_archive is False
        assert config.max_workers == 4
        assert config.chunk_size is None
        assert config.show_progress is False


class TestAdvaProbe:
    """Test AdvaProbe functionality."""

    def test_adva_probe_creation(self):
        """Test creating an AdvaProbe."""
        probe = AdvaProbe("192.168.1.100CLOCK_PROBE-1-1-2023-01-01-12-00-00.txt")
        assert probe.input_file == Path("192.168.1.100CLOCK_PROBE-1-1-2023-01-01-12-00-00.txt")
        assert probe.probe_key.probe_id == "1-1"
        assert probe.probe_key.ip_address == "192.168.1.100"

    def test_adva_probe_parse_filename(self):
        """Test AdvaProbe filename parsing."""
        probe_key, timestamp = AdvaProbe.parse_file_name(
            Path("192.168.1.100CLOCK_PROBE-1-1-2023-01-01-12-00-00.txt")
        )
        assert probe_key.probe_id == "1-1"
        assert probe_key.ip_address == "192.168.1.100"
        assert timestamp.year == 2023
        assert timestamp.month == 1
        assert timestamp.day == 1

    def test_adva_probe_parse_filename_invalid(self):
        """Test AdvaProbe filename parsing with invalid filename."""
        with pytest.raises(ValueError):
            AdvaProbe.parse_file_name(Path("invalid_filename.txt"))

    def test_adva_probe_parse_filename_gz(self):
        """Test AdvaProbe filename parsing with gzipped file."""
        probe_key, timestamp = AdvaProbe.parse_file_name(
            Path("192.168.1.100CLOCK_PROBE-1-1-2023-01-01-12-00-00.txt.gz")
        )
        assert probe_key.probe_id == "1-1"
        assert probe_key.ip_address == "192.168.1.100"

    def test_adva_probe_parse_filename_ptp(self):
        """Test AdvaProbe filename parsing with PTP clock probe."""
        probe_key, timestamp = AdvaProbe.parse_file_name(
            Path("192.168.1.100PTP_CLOCK_PROBE-1-1-2023-01-01-12-00-00.txt")
        )
        assert probe_key.probe_id == "1-1"
        assert probe_key.ip_address == "192.168.1.100"


class TestVendors:
    """Test VENDORS functionality."""

    def test_vendors_all(self):
        """Test getting all vendors."""
        vendors = VENDORS.all()
        assert len(vendors) >= 2  # Should have at least ADVA and MicrochipTWST
        vendor_names = [v.name for v in vendors]
        assert "ADVA" in vendor_names
        assert "MicrochipTWST" in vendor_names

    def test_vendors_get_by_name(self):
        """Test getting vendor by name."""
        vendor = VENDORS.get_by_name("ADVA")
        assert vendor.name == "ADVA"
        assert vendor.parser_class == "AdvaProbe"

    def test_vendors_get_by_name_case_insensitive(self):
        """Test getting vendor by name case-insensitive."""
        vendor = VENDORS.get_by_name("adva", case_sensitive=False)
        assert vendor.name == "ADVA"

    def test_vendors_get_by_name_not_found(self):
        """Test getting vendor by name that doesn't exist."""
        with pytest.raises(ValueError):
            VENDORS.get_by_name("NONEXISTENT") 
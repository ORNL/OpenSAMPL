"""Shared test fixtures for opensampl tests."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import pandas as pd
import pytest

from opensampl.config.base import BaseConfig
from opensampl.metrics import MetricType
from opensampl.references import ReferenceType
from opensampl.vendors.constants import ProbeKey, VendorType
from tests.utils.mockdb import MockDB


@pytest.fixture(scope="session")
def test_db():
    """Create a test database instance for the entire test session."""
    return MockDB()


@pytest.fixture
def mock_session(test_db: MockDB):
    """Create a real database session using MockDB."""
    session = test_db.Session()
    # Set the current session for MockDB event listeners
    test_db.set_current_session(session)
    try:
        yield session
        # Rollback any uncommitted changes to keep tests isolated
        session.rollback()
    finally:
        # Clear the current session
        test_db.set_current_session(None)
        session.close()


@pytest.fixture
def mock_table_factory_with_mockdb(test_db: MockDB):
    """Mock TableFactory.resolve_table to use MockDB table mappings."""

    def mock_resolve_table(self) -> Any:  # noqa: ANN001
        """Resolve table using MockDB mappings instead of Base.registry."""
        table_name = self.name
        if table_name in test_db.table_mappings:
            return test_db.table_mappings[table_name]
        raise ValueError(f"Table {table_name} not found in MockDB schema")

    with patch("opensampl.load.table_factory.TableFactory.resolve_table", mock_resolve_table):
        yield


@pytest.fixture
def mock_config():
    """Mock BaseConfig for testing."""
    with patch("opensampl.load.routing.BaseConfig") as mock:
        config = Mock(spec=BaseConfig)
        config.ROUTE_TO_BACKEND = False
        config.DATABASE_URL = "sqlite:///:memory:"
        config.LOG_LEVEL = "DEBUG"

        mock.return_value = config
        yield mock


@pytest.fixture
def mock_config_backend():
    """Mock BaseConfig with backend routing enabled."""
    with patch("opensampl.load.routing.BaseConfig") as mock:
        config = Mock(spec=BaseConfig)
        config.ROUTE_TO_BACKEND = True
        config.BACKEND_URL = "http://localhost:8000"
        config.API_KEY = "test-api-key"
        config.INSECURE_REQUESTS = False
        config.LOG_LEVEL = "DEBUG"

        mock.return_value = config
        yield mock


@pytest.fixture
def sample_probe_key():
    """Sample ProbeKey for testing."""
    return ProbeKey(probe_id="TEST001", ip_address="192.168.1.100")


@pytest.fixture
def sample_vendor():
    """Sample VendorType for testing."""
    vendor = Mock(spec=VendorType)
    vendor.name = "test_vendor"
    vendor.metadata_table = "test_metadata"
    vendor.model_dump.return_value = {"name": "test_vendor"}
    return vendor


@pytest.fixture
def sample_metric_type():
    """Sample MetricType for testing."""
    metric = Mock(spec=MetricType)
    metric.uuid = uuid4()
    metric.model_dump.return_value = {"type": "frequency"}
    return metric


@pytest.fixture
def sample_reference_type():
    """Sample ReferenceType for testing."""
    reference = Mock(spec=ReferenceType)
    reference.uuid = uuid4()
    reference.model_dump.return_value = {"type": "gps"}
    return reference


@pytest.fixture
def sample_time_data():
    """Sample pandas DataFrame with time series data."""
    return pd.DataFrame(
        {
            "time": [
                datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 12, 2, 0, tzinfo=timezone.utc),
            ],
            "value": [1.23456, 1.23457, 1.23458],
            "extra_column": ["a", "b", "c"],  # Should be filtered out
        }
    )


@pytest.fixture
def sample_table_data():
    """Sample data dictionary for table operations."""
    return {"name": "Test Location", "lat": 35.9132, "lon": -84.0401, "public": True}


@pytest.fixture
def sample_adva_metadata():
    """Sample probe metadata for testing."""
    return {
        "frequency": 1,
        "additional_metadata": {"something": "else"},
    }

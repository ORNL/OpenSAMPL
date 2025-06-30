"""Tests for the load_data module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy.exc import SQLAlchemyError

from opensampl.db.orm import Locations
from opensampl.load_data import (
    build_pk_conditions,
    create_new_tables,
    extract_unique_constraints,
    find_existing_entry,
    handle_existing_entry,
    load_probe_metadata,
    load_time_data,
    resolve_table_model,
    route_or_direct,
    write_to_table,
)
from opensampl.vendors.constants import ProbeKey, VendorType


@pytest.fixture
def mock_session():
    """Fixture that provides a mock SQLAlchemy session."""
    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def sample_location_data():
    """Fixture that provides sample location data."""
    return {"name": "Test Location", "lat": 40.7128, "lon": -74.0060, "z": 0, "public": True}


@pytest.fixture
def sample_probe_data():
    """Fixture that provides sample probe data."""
    return {
        "probe_id": "TEST001",
        "ip_address": "192.168.1.1",
        "vendor": "Test Vendor",
        "model": "Test Model",
        "name": "Test Probe",
        "public": True,
    }


@pytest.fixture
def sample_time_data():
    """Fixture that provides sample time series data."""
    return pd.DataFrame({"time": [datetime.now()], "value": [123.45]})


def test_write_to_table_new_entry(mock_session, sample_location_data):
    """Test writing a new entry to a table."""
    result = write_to_table("locations", sample_location_data, if_exists="error", session=mock_session)
    assert result is None
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_write_to_table_update(mock_session, sample_location_data):
    """Test updating an existing entry."""
    # First create an entry
    write_to_table("locations", sample_location_data, if_exists="error", session=mock_session)

    # Then update it
    updated_data = sample_location_data.copy()
    updated_data["public"] = False
    result = write_to_table("locations", updated_data, if_exists="update", session=mock_session)
    assert result is None
    mock_session.commit.assert_called()


def test_write_to_table_replace(mock_session, sample_location_data):
    """Test replacing an existing entry."""
    # First create an entry
    write_to_table("locations", sample_location_data, if_exists="error", session=mock_session)

    # Then replace it
    new_data = sample_location_data.copy()
    new_data["name"] = "New Location"
    result = write_to_table("locations", new_data, if_exists="replace", session=mock_session)
    assert result is None
    mock_session.commit.assert_called()


def test_write_to_table_ignore(mock_session, sample_location_data):
    """Test ignoring existing entries."""
    # First create an entry
    write_to_table("locations", sample_location_data, if_exists="error", session=mock_session)

    # Then try to create it again with ignore
    result = write_to_table("locations", sample_location_data, if_exists="ignore", session=mock_session)
    assert result is None
    mock_session.commit.assert_called()


def test_write_to_table_invalid_table(mock_session, sample_location_data):
    """Test writing to an invalid table."""
    with pytest.raises(ValueError):
        write_to_table("invalid_table", sample_location_data, session=mock_session)


def test_write_to_table_invalid_if_exists(mock_session, sample_location_data):
    """Test writing with invalid if_exists value."""
    with pytest.raises(ValueError):
        write_to_table("locations", sample_location_data, if_exists="invalid", session=mock_session)


def test_write_to_table_no_identifiable_fields(mock_session):
    """Test writing without identifiable fields."""
    with pytest.raises(ValueError):
        write_to_table("locations", {"public": True}, session=mock_session)


def test_load_time_data(mock_session, sample_time_data):
    """Test loading time series data."""
    probe_key = ProbeKey(probe_id="TEST001", ip_address="192.168.1.1")
    result = load_time_data(probe_key, sample_time_data, session=mock_session)
    assert result is None
    mock_session.commit.assert_called_once()


def test_load_probe_metadata(mock_session, sample_probe_data):
    """Test loading probe metadata."""
    result = load_probe_metadata(
        VendorType.ADVA, ProbeKey(probe_id="TEST001", ip_address="192.168.1.1"), sample_probe_data, session=mock_session
    )
    assert result is None
    mock_session.commit.assert_called_once()


def test_create_new_tables(mock_session):
    """Test creating new tables."""
    result = create_new_tables(create_schema=True, session=mock_session)
    assert result is None


def test_route_or_direct_decorator():
    """Test the route_or_direct decorator."""

    @route_or_direct("test_endpoint")
    def test_function(*args, **kwargs):
        return {"test": "data"}

    # Test with ROUTE_TO_BACKEND=True
    with (
        patch("opensampl.load_data.ENV_VARS.ROUTE_TO_BACKEND.get_value", return_value=True),
        patch("opensampl.load_data.ENV_VARS.BACKEND_URL.get_value", return_value="http://test.com"),
        patch("opensampl.load_data.requests.request") as mock_request,
    ):
        mock_request.return_value.json.return_value = {"status": "success"}
        result = test_function()
        assert result == {"test": "data"}
        mock_request.assert_called_once()

    # Test with ROUTE_TO_BACKEND=False
    with (
        patch("opensampl.load_data.ENV_VARS.ROUTE_TO_BACKEND.get_value", return_value=False),
        patch("opensampl.load_data.ENV_VARS.DATABASE_URL.get_value", return_value="sqlite:///:memory:"),
    ):
        result = test_function()
        assert result == {"test": "data"}


def test_resolve_table_model():
    """Test resolving table models."""
    # Test valid table
    model = resolve_table_model("locations")
    assert model == Locations

    # Test invalid table
    with pytest.raises(ValueError):
        resolve_table_model("invalid_table")


def test_build_pk_conditions(sample_location_data):
    """Test building primary key conditions."""
    conditions = build_pk_conditions(Locations, ["uuid"], sample_location_data)
    assert len(conditions) == 0  # No UUID in sample data

    # Test with UUID
    data_with_uuid = sample_location_data.copy()
    data_with_uuid["uuid"] = "test-uuid"
    conditions = build_pk_conditions(Locations, ["uuid"], data_with_uuid)
    assert len(conditions) == 1


def test_extract_unique_constraints():
    """Test extracting unique constraints."""
    inspector = MagicMock()
    inspector.get_unique_constraints.return_value = [{"name": "uq_name", "column_names": ["name"]}]
    data = {"name": "Test Location"}
    constraints = extract_unique_constraints(inspector, data)
    assert len(constraints) == 1


def test_find_existing_entry(mock_session):
    """Test finding existing entries."""
    # Mock query result
    mock_query = MagicMock()
    mock_query.first.return_value = None
    mock_session.query.return_value = mock_query

    result = find_existing_entry(mock_session, Locations, [("name", "Test Location")], [[("name", "Test Location")]])
    assert result is None


def test_handle_existing_entry(mock_session, sample_location_data):
    """Test handling existing entries."""
    existing = Locations(**sample_location_data)
    inspector = MagicMock()
    inspector.columns = []

    # Test update strategy
    handle_existing_entry(existing, Locations, {"public": False}, ["uuid"], inspector, "update", mock_session)
    assert existing.public is False

    # Test replace strategy
    handle_existing_entry(existing, Locations, {"name": "New Location"}, ["uuid"], inspector, "replace", mock_session)
    assert existing.name == "New Location"


@pytest.mark.parametrize("error_type", [SQLAlchemyError, ValueError, TypeError])
def test_error_handling(mock_session, sample_location_data, error_type):
    """Test error handling in various functions."""
    mock_session.commit.side_effect = error_type("Test error")

    with pytest.raises(error_type):
        write_to_table("locations", sample_location_data, session=mock_session)
    mock_session.rollback.assert_called_once()


def test_load_time_data_validation(mock_session):
    """Test time data validation."""
    # Test with invalid data format
    invalid_data = pd.DataFrame({"invalid": ["data"]})
    with pytest.raises(ValueError):
        load_time_data(ProbeKey("TEST001", "192.168.1.1"), invalid_data, session=mock_session)

    # Test with empty data
    empty_data = pd.DataFrame()
    with pytest.raises(ValueError):
        load_time_data(ProbeKey("TEST001", "192.168.1.1"), empty_data, session=mock_session)


def test_load_probe_metadata_validation(mock_session):
    """Test probe metadata validation."""
    # Test with missing required fields
    invalid_data = {"name": "Test Probe"}
    with pytest.raises(ValueError):
        load_probe_metadata(VendorType.ADVA, ProbeKey("TEST001", "192.168.1.1"), invalid_data, session=mock_session)

    # Test with invalid vendor type
    with pytest.raises(ValueError):
        load_probe_metadata(
            "InvalidVendor", ProbeKey("TEST001", "192.168.1.1"), {"name": "Test Probe"}, session=mock_session
        )


def test_load_data_import():
    """Test that the load_data module can be imported."""
    from opensampl import load_data

    assert load_data is not None


def test_load_data_function():
    """Test that the load_data function exists."""
    assert callable(load_data)


@pytest.fixture
def sample_data_file(test_data_dir) -> Path:
    """Fixture that provides a sample data file for testing."""
    data_file = test_data_dir / "sample_data.yaml"
    data_file.parent.mkdir(exist_ok=True)
    data_file.write_text("""
    vendors:
      - name: test_vendor
        type: test
        config:
          host: localhost
          port: 8080
    """)
    return data_file


def test_load_data_from_file(sample_data_file):
    """Test loading data from a file."""
    data = load_data(sample_data_file)
    assert data is not None
    assert "vendors" in data
    assert len(data["vendors"]) > 0
    assert data["vendors"][0]["name"] == "test_vendor"


def test_load_data_invalid_file(test_data_dir):
    """Test loading data from an invalid file."""
    invalid_file = test_data_dir / "nonexistent.yaml"
    with pytest.raises(FileNotFoundError):
        load_data(invalid_file)


@pytest.mark.parametrize(
    "invalid_content",
    [
        "",  # Empty file
        "invalid: yaml: content:",  # Invalid YAML
        "vendors: []",  # Empty vendors list
    ],
)
def test_load_data_invalid_content(test_data_dir, invalid_content):
    """Test loading data with invalid content."""
    invalid_file = test_data_dir / "invalid_data.yaml"
    invalid_file.write_text(invalid_content)

    with pytest.raises(ValueError):
        load_data(invalid_file)


@pytest.mark.parametrize(
    "test_input,expected",
    [
        # Test loading time data
        (
            {
                "table": "probe_data",
                "data": pd.DataFrame(
                    {
                        "uuid": ["test-uuid-1", "test-uuid-2"],
                        "time": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
                        "value": [1.0, 2.0],
                    }
                ),
                "conflict": "update",
            },
            {"rows_affected": 2, "error": None},
        ),
        # Test loading probe metadata
        (
            {
                "table": "probe_metadata",
                "data": pd.DataFrame(
                    {
                        "uuid": ["test-uuid-1"],
                        "probe_id": ["probe-1"],
                        "ip_address": ["192.168.1.1"],
                        "vendor": ["test_vendor"],
                        "model": ["test_model"],
                        "name": ["Test Probe"],
                    }
                ),
                "conflict": "update",
            },
            {"rows_affected": 1, "error": None},
        ),
        # Test loading location data
        (
            {
                "table": "locations",
                "data": pd.DataFrame(
                    {"uuid": ["loc-1"], "name": ["Test Location"], "geom": ["POINT(0 0)"], "public": [True]}
                ),
                "conflict": "update",
            },
            {"rows_affected": 1, "error": None},
        ),
        # Test loading test metadata
        (
            {
                "table": "test_metadata",
                "data": pd.DataFrame(
                    {
                        "uuid": ["test-1"],
                        "name": ["Test Run"],
                        "start_date": [pd.Timestamp("2024-01-01")],
                        "end_date": [pd.Timestamp("2024-01-02")],
                    }
                ),
                "conflict": "update",
            },
            {"rows_affected": 1, "error": None},
        ),
        # Test loading ADVA metadata
        (
            {
                "table": "adva_metadata",
                "data": pd.DataFrame(
                    {
                        "uuid": ["adva-1"],
                        "probe_metadata_uuid": ["test-uuid-1"],
                        "type": ["test_type"],
                        "frequency": [1000],
                    }
                ),
                "conflict": "update",
            },
            {"rows_affected": 1, "error": None},
        ),
        # Test invalid table name
        (
            {"table": "invalid_table", "data": pd.DataFrame({"col": [1]}), "conflict": "update"},
            {"rows_affected": 0, "error": "Invalid table name"},
        ),
        # Test empty data
        ({"table": "probe_data", "data": pd.DataFrame(), "conflict": "update"}, {"rows_affected": 0, "error": None}),
        # Test missing required columns
        (
            {"table": "probe_metadata", "data": pd.DataFrame({"invalid_col": [1]}), "conflict": "update"},
            {"rows_affected": 0, "error": "Missing required columns"},
        ),
        # Test invalid data types
        (
            {
                "table": "probe_data",
                "data": pd.DataFrame({"uuid": ["test-uuid-1"], "time": ["invalid_time"], "value": ["invalid_value"]}),
                "conflict": "update",
            },
            {"rows_affected": 0, "error": "Invalid data types"},
        ),
        # Test conflict resolution strategies
        (
            {
                "table": "probe_metadata",
                "data": pd.DataFrame(
                    {
                        "uuid": ["test-uuid-1"],
                        "probe_id": ["probe-1"],
                        "ip_address": ["192.168.1.1"],
                        "vendor": ["test_vendor"],
                        "model": ["test_model"],
                        "name": ["Test Probe"],
                    }
                ),
                "conflict": "ignore",
            },
            {"rows_affected": 1, "error": None},
        ),
        (
            {
                "table": "probe_metadata",
                "data": pd.DataFrame(
                    {
                        "uuid": ["test-uuid-1"],
                        "probe_id": ["probe-1"],
                        "ip_address": ["192.168.1.1"],
                        "vendor": ["test_vendor"],
                        "model": ["test_model"],
                        "name": ["Test Probe"],
                    }
                ),
                "conflict": "replace",
            },
            {"rows_affected": 1, "error": None},
        ),
    ],
)
def test_load_data_cases(test_input, expected, test_db):
    """Test various load_data scenarios."""
    from opensampl.load_data import write_to_table

    try:
        result = write_to_table(test_input["table"], test_input["data"], conflict=test_input["conflict"])
        assert result == expected["rows_affected"]
        assert expected["error"] is None
    except Exception as e:
        assert expected["error"] is not None
        assert str(e) == expected["error"]

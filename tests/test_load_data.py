"""Integration tests for opensampl.load_data module using real database operations."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from opensampl.load_data import load_probe_metadata, write_to_table
from opensampl.vendors.constants import ProbeKey
from tests.utils.mockdb import MockDB


class TestWriteToTable:
    """Integration tests for write_to_table with real database operations."""

    def test_write_to_table(
        self,
        mock_config: Mock,
        mock_session: Session,
        sample_table_data: dict,
        test_db: MockDB,
        mock_table_factory_with_mockdb: Any,
    ):
        """Test write_to_table with actual database writes."""
        # Get the real table class for locations
        Locations = test_db.table_mappings["Locations"]  # noqa: N806

        # Verify table is empty initially
        count_before = mock_session.query(Locations).count()
        assert count_before == 0

        # Call write_to_table with real database operation
        result = write_to_table(table="locations", data=sample_table_data, if_exists="update", session=mock_session)

        # Verify data was written to database
        locations = mock_session.query(Locations).all()
        assert len(locations) == 1

        location = locations[0]
        assert location.name == "Test Location"
        assert location.public is True
        assert location.geom is not None  # Should have geometry from lat/lon
        assert result is None

    def test_conflict_handling(
        self,
        mock_config: Mock,
        mock_session: Session,
        sample_table_data: dict,
        test_db: MockDB,
        mock_table_factory_with_mockdb: Any,
    ):
        """Test write_to_table conflict handling with real database."""
        Locations = test_db.table_mappings["Locations"]  # noqa: N806

        # First insert
        write_to_table(table="locations", data=sample_table_data, if_exists="update", session=mock_session)

        # Verify first insert
        count_after_first = mock_session.query(Locations).count()
        assert count_after_first == 1

        # Second insert with same name (should handle conflict)
        updated_data = sample_table_data.copy()
        updated_data["lat"] = sample_table_data["lat"] + 4

        write_to_table(table="locations", data=updated_data, if_exists="update", session=mock_session)

        # Should still be only one record
        locations = mock_session.query(Locations).all()
        assert len(locations) == 1

    def test_backend_routing(self, sample_table_data: dict):
        """Test backend routing behavior with proper HTTP mocking."""
        # Setup mock config for backend routing
        with (
            patch("opensampl.load.routing.requests.request") as mock_request,
            patch("opensampl.load.routing.BaseConfig") as mock_config_class,
        ):
            mock_config = Mock()
            mock_config.ROUTE_TO_BACKEND = True
            mock_config.BACKEND_URL = "http://localhost:8000"
            mock_config.API_KEY = "test-api-key"
            mock_config.INSECURE_REQUESTS = False
            mock_config.check_routing_dependencies = Mock()
            mock_config_class.return_value = mock_config

            # Setup mock HTTP response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "success"}
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            write_to_table(table="locations", data=sample_table_data, if_exists="update")

            # Verify backend call was made correctly
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert kwargs["method"] == "POST"  # method
            assert kwargs["url"] == "http://localhost:8000/write_to_table"
            assert kwargs["headers"]["access-key"] == "test-api-key"
            expected_payload = {"table": "locations", "data": sample_table_data, "if_exists": "update"}
            assert kwargs["json"] == expected_payload

    def test_validation(self, mock_config: Mock, mock_session: Session, sample_table_data: dict):
        """Test validation with real logic - no mocking of validation itself."""
        from opensampl.load_data import write_to_table

        # Test invalid conflict action using unwrapped function
        original_func = getattr(write_to_table, "__wrapped__", write_to_table)
        with pytest.raises(ValueError, match="on_conflict must be one of"):
            original_func(
                table="locations",
                data=sample_table_data,
                _config=mock_config(),
                if_exists="invalid_action",
                session=mock_session,
            )

    def test_session_validation(self, mock_config: Mock, sample_table_data: dict):
        """Test session validation with real isinstance check."""
        from opensampl.load_data import write_to_table

        original_func = getattr(write_to_table, "__wrapped__", write_to_table)

        with pytest.raises(TypeError, match="Session must be a SQLAlchemy session"):
            original_func(
                table="locations",
                data=sample_table_data,
                _config=mock_config(),
                if_exists="update",
                session="not_a_session",  # String instead of session
            )


# class TestLoadTimeData:
#     """Integration tests for load_time_data with real database operations."""
#
#     @patch('opensampl.load.routing.requests.request')
#     @patch('opensampl.load.routing.BaseConfig')
#     def test_backend_routing(self, mock_config_class, mock_request,
#                              sample_probe_key, sample_metric_type,
#                              sample_reference_type, sample_time_data):
#         """Test backend routing with proper HTTP mocking."""
#         # Setup mock config for backend routing
#         mock_config = Mock()
#         mock_config.ROUTE_TO_BACKEND = True
#         mock_config.BACKEND_URL = "http://localhost:8000"
#         mock_config.API_KEY = "test-api-key"
#         mock_config.INSECURE_REQUESTS = False
#         mock_config.check_routing_dependencies = Mock()
#         mock_config_class.return_value = mock_config
#
#         # Setup mock HTTP response
#         mock_response = Mock()
#         mock_response.status_code = 200
#         mock_response.json.return_value = {"status": "success"}
#         mock_response.raise_for_status = Mock()
#         mock_request.return_value = mock_response
#
#         compound_key = {"test": "key"}
#
#         result = load_time_data(
#             probe_key=sample_probe_key,
#             metric_type=sample_metric_type,
#             reference_type=sample_reference_type,
#             data=sample_time_data,
#             compound_key=compound_key
#         )
#
#         # Verify backend call was made correctly
#         mock_request.assert_called_once()
#         args, kwargs = mock_request.call_args
#         assert kwargs['method'] == "POST"  # method
#         assert kwargs['url'] == "http://localhost:8000/load_time_data"
#         assert kwargs['headers']['access-key'] == "test-api-key"
#
#         # Check file upload structure
#         assert 'files' in kwargs
#         assert 'data' in kwargs
#
#         # Verify CSV file was created properly
#         file_info = kwargs['files']['file']
#         assert len(file_info) == 3  # (filename, file_content, content_type)
#         assert isinstance(file_info[1], bytes)
#         assert file_info[2] == 'text/csv'
#
#         # Verify CSV content - note: column filtering happens in the actual function
#         csv_content = file_info[1].decode()
#         assert "time" in csv_content
#         assert "value" in csv_content
#         # Note: extra_column filtering may happen server-side, so we don't test that here
#
#     def test_real_database_write(self, mock_config, mock_session: Session, test_db,
#                                                sample_probe_key, sample_metric_type,
#                                                sample_reference_type, sample_time_data):
#         """Test time data loading with actual database writes."""
#         # Get real database models
#         ProbeData = test_db.table_mappings["ProbeData"]
#
#         # Verify table is empty initially
#         count_before = mock_session.query(ProbeData).count()
#         assert count_before == 0
#
#         # Call load_time_data with real database operation
#         load_time_data(
#             probe_key=sample_probe_key,
#             metric_type=sample_metric_type,
#             reference_type=sample_reference_type,
#             data=sample_time_data,
#             session=mock_session
#         )
#
#         # Verify data was written to database
#         probe_data_records = mock_session.query(ProbeData).all()
#         assert len(probe_data_records) == 3  # Should match number of rows in sample_time_data
#
#         # Verify the data content
#         for record in probe_data_records:
#             assert record.value is not None
#             assert record.time is not None


class TestLoadProbeMetadata:
    """Integration tests for load_probe_metadata with real database operations."""

    # @patch('opensampl.load.routing.requests.request')
    # @patch('opensampl.load.routing.BaseConfig')
    # def test_backend_routing(self, mock_config_class, mock_request,
    #                          sample_vendor, sample_probe_key, sample_probe_metadata):
    #     """Test backend routing behavior with proper HTTP mocking."""
    #     # Setup mock config for backend routing
    #     mock_config = Mock()
    #     mock_config.ROUTE_TO_BACKEND = True
    #     mock_config.BACKEND_URL = "http://localhost:8000"
    #     mock_config.API_KEY = "test-api-key"
    #     mock_config.INSECURE_REQUESTS = False
    #     mock_config.check_routing_dependencies = Mock()
    #     mock_config_class.return_value = mock_config
    #
    #     # Setup mock HTTP response
    #     mock_response = Mock()
    #     mock_response.status_code = 200
    #     mock_response.json.return_value = {"status": "success"}
    #     mock_response.raise_for_status = Mock()
    #     mock_request.return_value = mock_response
    #
    #     result = load_probe_metadata(
    #         vendor=sample_vendor,
    #         probe_key=sample_probe_key,
    #         data=sample_probe_metadata
    #     )
    #
    #     # Verify backend call was made correctly
    #     mock_request.assert_called_once()
    #     args, kwargs = mock_request.call_args
    #     assert kwargs['method'] == "POST"  # method
    #     assert kwargs['url'] == "http://localhost:8000/load_probe_metadata"
    #     assert kwargs['headers']['access-key'] == "test-api-key"
    #
    #     # Check JSON payload structure
    #     payload = kwargs['json']
    #     assert "vendor" in payload
    #     assert "probe_key" in payload
    #     assert "data" in payload
    #     assert payload["vendor"] == sample_vendor
    #     assert payload["probe_key"] == sample_probe_key
    #     assert payload["data"] == sample_probe_metadata

    def test_real_session_flow(
        self,
        mock_config: Mock,
        mock_session: Session,
        sample_probe_key: ProbeKey,
        sample_adva_metadata: dict,
        test_db: MockDB,
        mock_table_factory_with_mockdb: Any,
    ):  # noqaARG002
        """Test probe metadata creation with real session and database models."""
        # Use real database models from MockDB
        from opensampl.vendors.constants import VENDORS

        ProbeMetadata = test_db.table_mappings.get("ProbeMetadata")  # noqa: N806
        count_before = mock_session.query(ProbeMetadata).count()
        assert count_before == 0

        result = load_probe_metadata(
            vendor=VENDORS.ADVA, probe_key=sample_probe_key, data=sample_adva_metadata, session=mock_session
        )
        assert result is None

        metadata = mock_session.query(ProbeMetadata).all()
        assert len(metadata) == 1

        entry = metadata[0]
        assert entry.uuid is not None
        assert entry.probe_id == sample_probe_key.probe_id
        assert entry.ip_address == sample_probe_key.ip_address


class TestMockDb:
    """Tests for the mock database itself"""

    def test_real_database_models_accessible(self, test_db: MockDB):
        """Test that real database models are accessible through MockDB."""
        # Verify we have access to real ORM models
        assert "Locations" in test_db.table_mappings
        assert "ProbeMetadata" in test_db.table_mappings
        assert "ProbeData" in test_db.table_mappings

        # Verify models have expected attributes
        Locations = test_db.table_mappings["Locations"]  # noqa: N806
        assert hasattr(Locations, "__tablename__")
        assert hasattr(Locations, "uuid")
        assert hasattr(Locations, "name")

        ProbeMetadata = test_db.table_mappings["ProbeMetadata"]  # noqa: N806
        assert hasattr(ProbeMetadata, "__tablename__")
        assert hasattr(ProbeMetadata, "uuid")
        assert hasattr(ProbeMetadata, "name")
        assert hasattr(ProbeMetadata, "resolve_references")

    def test_real_session_operations(self, mock_session: Session, test_db: MockDB):
        """Test basic session operations work with real database."""
        # This verifies the session is actually functional
        from sqlalchemy import text

        # Test a simple query
        result = mock_session.execute(text("SELECT 1 as test_value")).fetchone()
        assert result[0] == 1

        # Test that we can create a model instance
        Locations = test_db.table_mappings["Locations"]  # noqa: N806
        location = Locations(name="Test Location", public=True)

        # Verify model has expected attributes
        assert location.name == "Test Location"
        assert location.public is True

        metrics = mock_session.query(test_db.table_mappings.get("MetricType")).all()
        assert len(metrics) > 0

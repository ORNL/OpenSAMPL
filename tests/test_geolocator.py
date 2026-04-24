"""Tests for geolocation helper behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from opensampl.helpers import geolocator


class TestLookupGeoIpApi:
    """Tests for the ip-api lookup helper."""

    def test_lookup_geo_ipapi_success_is_cached(self):
        """Successful lookups should be cached and return a stable tuple."""
        body = {"status": "success", "lat": 35.9, "lon": -84.3, "city": "Oak Ridge", "country": "United States"}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):  # noqa: ANN001,ARG002
                return False

            def read(self):
                return json.dumps(body).encode("utf-8")

        geolocator._GEO_CACHE.clear()
        with patch("opensampl.helpers.geolocator.urllib.request.urlopen", return_value=Response()) as mock_urlopen:
            first = geolocator._lookup_geo_ipapi("8.8.8.8")
            second = geolocator._lookup_geo_ipapi("8.8.8.8")

        assert first == (35.9, -84.3, "Oak Ridge, United States")
        assert second == first
        mock_urlopen.assert_called_once()

    def test_lookup_geo_ipapi_failure_returns_none(self):
        """Lookup failures should degrade to None instead of raising."""
        geolocator._GEO_CACHE.clear()
        with patch("opensampl.helpers.geolocator.urllib.request.urlopen", side_effect=OSError("blocked")):
            assert geolocator._lookup_geo_ipapi("8.8.8.8") is None


class TestCreateLocation:
    """Tests for location creation decisions."""

    def test_create_location_uses_override_without_network_lookup(self):
        """Explicit overrides should be written directly."""
        fake_loc = SimpleNamespace(uuid="loc-123")
        fake_factory = Mock()
        fake_factory.find_existing.return_value = None
        fake_factory.write.return_value = fake_loc

        with patch("opensampl.helpers.geolocator.TableFactory", return_value=fake_factory):
            result = geolocator.create_location(
                session=Mock(),
                geolocate_enabled=False,
                ip_address="mock-ntp-a",
                geo_override={"name": "Docker lab", "lat": 37.37, "lon": -122.05},
            )

        assert result == "loc-123"
        fake_factory.write.assert_called_once_with(
            {"name": "Docker lab", "lat": 37.37, "lon": -122.05, "public": True},
            if_exists="ignore",
        )

    def test_create_location_uses_existing_named_location(self):
        """Named overrides should reuse existing locations when present."""
        fake_factory = Mock()
        fake_factory.find_existing.return_value = SimpleNamespace(uuid="loc-existing")

        with patch("opensampl.helpers.geolocator.TableFactory", return_value=fake_factory):
            result = geolocator.create_location(
                session=Mock(),
                geolocate_enabled=False,
                ip_address="mock-ntp-b",
                geo_override={"name": "Docker lab", "lat": 37.38, "lon": -122.06},
            )

        assert result == "loc-existing"
        fake_factory.write.assert_not_called()

    def test_create_location_uses_public_lookup_when_enabled(self):
        """Public hosts should use lookup-derived coordinates and label when enabled."""
        fake_loc = SimpleNamespace(uuid="loc-public")
        fake_factory = Mock()
        fake_factory.find_existing.return_value = None
        fake_factory.write.return_value = fake_loc

        with (
            patch("opensampl.helpers.geolocator.TableFactory", return_value=fake_factory),
            patch("opensampl.helpers.geolocator.socket.gethostbyname", return_value="8.8.8.8"),
            patch("opensampl.helpers.geolocator._lookup_geo_ipapi", return_value=(40.71, -74.0, "New York, United States")),
        ):
            result = geolocator.create_location(
                session=Mock(),
                geolocate_enabled=True,
                ip_address="time.example.com",
                geo_override={},
            )

        assert result == "loc-public"
        fake_factory.write.assert_called_once_with(
            {"name": "New York, United States", "lat": 40.71, "lon": -74.0, "public": True},
            if_exists="ignore",
        )

    def test_create_location_returns_none_when_name_is_unavailable(self):
        """Private/loopback lookups without a name should skip location creation."""
        fake_factory = Mock()
        fake_factory.find_existing.return_value = None

        with (
            patch("opensampl.helpers.geolocator.TableFactory", return_value=fake_factory),
            patch("opensampl.helpers.geolocator.socket.gethostbyname", return_value="127.0.0.1"),
        ):
            result = geolocator.create_location(
                session=Mock(),
                geolocate_enabled=True,
                ip_address="localhost",
                geo_override={},
            )

        assert result is None
        fake_factory.write.assert_not_called()

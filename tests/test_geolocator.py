"""Tests for geolocation helper behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from opensampl.helpers import geolocator

class TestLookupGeoIpApi:
    """Tests for the ip-api lookup helper."""

    def test_lookup_geo_ipapi_success_is_cached(self):
        """Successful lookups should be cached and return a stable tuple."""
        body = {
            "status": "success",
            "lat": 35.9,
            "lon": -84.3,
            "city": "Oak Ridge",
            "country": "United States",
        }

        mock_response = Mock()
        mock_response.json.return_value = body
        mock_response.raise_for_status.return_value = None

        geolocator._GEO_CACHE.clear()

        with patch(
            "opensampl.helpers.geolocator.requests.get",
            return_value=mock_response,
        ) as mock_get:
            first = geolocator._lookup_geo_ipapi("8.8.8.8")
            second = geolocator._lookup_geo_ipapi("8.8.8.8")

        assert first == (35.9, -84.3, "Oak Ridge, United States")
        assert second == first

        mock_get.assert_called_once_with(
            "http://ip-api.com/json/8.8.8.8",
            params={"fields": "status,lat,lon,city,country"},
            timeout=4.0,
            allow_redirects=False,
        )
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

    def test_lookup_geo_ipapi_failure_returns_none(self):
        """Network failures should degrade to None instead of raising."""
        geolocator._GEO_CACHE.clear()

        with patch(
            "opensampl.helpers.geolocator.requests.get",
            side_effect=requests.exceptions.ConnectionError("blocked"),
        ) as mock_get:
            result = geolocator._lookup_geo_ipapi("8.8.8.8")

        assert result is None
        mock_get.assert_called_once()

    def test_lookup_geo_ipapi_http_error_returns_none(self):
        """HTTP errors should return None without propagating exceptions."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "429 Too Many Requests"
        )

        geolocator._GEO_CACHE.clear()

        with patch(
            "opensampl.helpers.geolocator.requests.get",
            return_value=mock_response,
        ):
            result = geolocator._lookup_geo_ipapi("8.8.8.8")

        assert result is None

    def test_lookup_geo_ipapi_invalid_ip_returns_none(self):
        """Invalid IP addresses should be rejected without network access."""
        geolocator._GEO_CACHE.clear()

        with patch("opensampl.helpers.geolocator.requests.get") as mock_get:
            result = geolocator._lookup_geo_ipapi("not-an-ip-address")

        assert result is None
        mock_get.assert_not_called()

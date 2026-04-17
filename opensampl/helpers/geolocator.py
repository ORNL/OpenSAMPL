"""Associate NTP probes with ``castdb.locations`` for the geospatial Grafana dashboard."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import urllib.request
from typing import TYPE_CHECKING

from loguru import logger

from opensampl.load.table_factory import TableFactory

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


_GEO_CACHE: dict[str, tuple[float, float, str]] = {}


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _default_lab_coords() -> tuple[float, float]:
    lat = float(os.getenv("DEFAULT_LAT", "35.9312"))
    lon = float(os.getenv("DEFAULT_LON", "-84.3101"))
    return lat, lon


def _is_private_or_loopback(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return bool(addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)


def _lookup_geo_ipapi(ip: str) -> tuple[float, float, str] | None:
    if ip in _GEO_CACHE:
        return _GEO_CACHE[ip]
    url = f"http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country"
    try:
        with urllib.request.urlopen(url, timeout=4.0) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("ip-api geolocation failed for {}: {}", ip, e)
        return None

    if body.get("status") != "success" or body.get("lat") is None or body.get("lon") is None:
        logger.warning("ip-api returned no coordinates for {}", ip)
        return None

    city = body.get("city") or ""
    country = body.get("country") or ""
    label = ", ".join(x for x in (city, country) if x)
    out = (float(body["lat"]), float(body["lon"]), label or ip)
    _GEO_CACHE[ip] = out
    return out


def create_location(session: Session, geolocate_enabled: bool, ip_address: str, geo_override: dict) -> str | None:
    """
    Set probe ``name``, ``public``, and ``location_uuid`` on NTP metadata before ``probe_metadata`` insert.

    Uses ``additional_metadata.geo_override`` when present (lat/lon/label). Otherwise resolves the remote
    host, uses RFC1918/loopback defaults from env, or ip-api.com for public IPs (HTTP, no API key).
    """
    lat: float | None = None
    lon: float | None = None
    name: str | None = None

    if isinstance(geo_override, dict) and geo_override.get("lat") is not None and geo_override.get("lon") is not None:
        lat = float(geo_override["lat"])
        lon = float(geo_override["lon"])

    if isinstance(geo_override, dict) and geo_override.get("name") is not None:
        name = geo_override["name"]

    if geolocate_enabled and lat is None and lon is None:
        ip_for_geo = ip_address
        try:
            ip_for_geo = socket.gethostbyname(ip_address)
        except OSError as e:
            logger.debug("Could not resolve {}: {}", ip_address, e)

        if _is_private_or_loopback(ip_for_geo):
            lat, lon = _default_lab_coords()
        else:
            geo = _lookup_geo_ipapi(ip_for_geo)
            if geo:
                lat, lon, _name = geo
                name = name or _name
            else:
                lat, lon = _default_lab_coords()

    loc_factory = TableFactory("locations", session=session)
    loc = None
    if name:
        loc = loc_factory.find_existing({"name": name})

    if loc is None:
        loc = loc_factory.write(
            {"name": name, "lat": lat, "lon": lon, "public": True},
            if_exists="ignore",
        )

    if loc:
        return loc.uuid
    return None

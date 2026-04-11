"""Associate NTP probes with ``castdb.locations`` for the geospatial Grafana dashboard."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import urllib.request
from typing import TYPE_CHECKING, Any

from loguru import logger

from opensampl.load.table_factory import TableFactory

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from opensampl.vendors.constants import ProbeKey

_GEO_CACHE: dict[str, tuple[float, float, str]] = {}


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _default_lab_coords() -> tuple[float, float]:
    lat = float(os.getenv("NTP_GEO_DEFAULT_LAT", "37.4419"))
    lon = float(os.getenv("NTP_GEO_DEFAULT_LON", "-122.1430"))
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


def attach_ntp_location(session: Session, probe_key: ProbeKey, data: dict[str, Any]) -> None:
    """
    Set probe ``name``, ``public``, and ``location_uuid`` on NTP metadata before ``probe_metadata`` insert.

    Uses ``additional_metadata.geo_override`` when present (lat/lon/label). Otherwise resolves the remote
    host, uses RFC1918/loopback defaults from env, or ip-api.com for public IPs (HTTP, no API key).
    """
    if not _env_bool("NTP_GEO_ENABLED", True):
        data.setdefault("name", data.get("probe_name") or f"NTP {probe_key.probe_id}")
        return

    extras = data.get("additional_metadata") or {}
    if not isinstance(extras, dict):
        extras = {}
    geo_override = extras.get("geo_override")

    mode = data.get("mode")
    target_host = (data.get("target_host") or "").strip()
    target_port = data.get("target_port")
    probe_name = data.get("probe_name") or f"NTP {probe_key.probe_id}"

    lat: float | None = None
    lon: float | None = None

    if isinstance(geo_override, dict) and geo_override.get("lat") is not None and geo_override.get("lon") is not None:
        lat = float(geo_override["lat"])
        lon = float(geo_override["lon"])
    elif mode == "remote_server" and target_host:
        ip_for_geo = target_host
        try:
            ip_for_geo = socket.gethostbyname(target_host)
        except OSError as e:
            logger.debug("Could not resolve {}: {}", target_host, e)

        if _is_private_or_loopback(ip_for_geo):
            lat, lon = _default_lab_coords()
        else:
            geo = _lookup_geo_ipapi(ip_for_geo)
            if geo:
                lat, lon, _ = geo
            else:
                lat, lon = _default_lab_coords()
    else:
        lat, lon = _default_lab_coords()

    loc_name = f"NTP: {target_host}:{target_port}" if target_host and target_port is not None else f"NTP: {probe_key}"

    loc_factory = TableFactory("locations", session=session)
    existing = loc_factory.find_existing({"name": loc_name})
    if existing is not None:
        loc = existing
    else:
        loc = loc_factory.write(
            {"name": loc_name, "lat": lat, "lon": lon, "public": True},
            if_exists="ignore",
        )

    data["location_uuid"] = loc.uuid
    data["name"] = probe_name
    data["public"] = True

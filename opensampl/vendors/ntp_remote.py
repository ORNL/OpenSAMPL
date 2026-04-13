"""Remote NTP client queries (UDP)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger


def query_ntp_server(host: str, port: int = 123, timeout: float = 3.0) -> dict[str, Any]:
    """
    Perform one NTP client request and return a snapshot document (metadata + one series row).

    Requires optional dependency ``ntplib``.
    """
    try:
        import ntplib  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError("Remote NTP collection requires the 'ntplib' package (install opensampl[collect]).") from e

    client = ntplib.NTPClient()
    try:
        resp = client.request(host, port=port, version=3, timeout=timeout)
    except Exception as e:
        logger.warning(f"NTP request to {host}:{port} failed: {e}")
        now = datetime.now(tz=timezone.utc)
        meta = {
            "mode": "remote_server",
            "probe_name": f"ntp-{host}-{port}",
            "target_host": host,
            "target_port": port,
            "sync_status": "unreachable",
            "leap_status": "unknown",
            "stratum": None,
            "reachability": None,
            "offset_last_s": None,
            "delay_s": None,
            "jitter_s": None,
            "dispersion_s": None,
            "root_delay_s": None,
            "root_dispersion_s": None,
            "poll_interval_s": None,
            "reference_id": None,
            "observation_source": "ntplib_error",
            "collection_host": "",
            "additional_metadata": {"error": str(e)},
        }
        row = {
            "time": now.isoformat(),
            "sync_health": 0.0,
        }
        return {
            "format_version": 1,
            "probe_id": f"remote-{host}-{port}",
            "probe_ip": host,
            "metadata": meta,
            "series": [row],
        }

    leap = int(resp.leap)
    leap_map = {0: "no_warning", 1: "add_second", 2: "del_second", 3: "alarm"}
    stratum = int(resp.stratum)
    # poll is log2 seconds in RFC5905
    try:
        poll_s = float(2 ** int(resp.poll))
    except (TypeError, ValueError, OverflowError):
        poll_s = None

    root_delay_s = float(resp.root_delay) if resp.root_delay is not None else None
    root_dispersion_s = float(resp.root_dispersion) if resp.root_dispersion is not None else None
    delay_s = float(resp.delay) if resp.delay is not None else None
    offset_s = float(resp.offset) if resp.offset is not None else None

    ref_id = getattr(resp, "ref_id", None)
    if hasattr(ref_id, "decode"):
        try:
            ref_id = ref_id.decode("ascii", errors="replace")
        except Exception:
            ref_id = str(ref_id)
    ref_id = str(ref_id) if ref_id is not None else None

    now = datetime.now(tz=timezone.utc)
    sync_ok = stratum < 16 and offset_s is not None
    meta = {
        "mode": "remote_server",
        "probe_name": f"ntp-{host}-{port}",
        "target_host": host,
        "target_port": port,
        "sync_status": "synchronized" if sync_ok else "unsynchronized",
        "leap_status": leap_map.get(leap, str(leap)),
        "stratum": stratum,
        "reachability": None,
        "offset_last_s": offset_s,
        "delay_s": delay_s,
        "jitter_s": None,
        "dispersion_s": None,
        "root_delay_s": root_delay_s,
        "root_dispersion_s": root_dispersion_s,
        "poll_interval_s": poll_s,
        "reference_id": ref_id,
        "observation_source": "ntplib",
        "collection_host": "",
        "additional_metadata": {"version": getattr(resp, "version", None)},
    }

    row: dict[str, Any] = {
        "time": now.isoformat(),
        "phase_offset_s": offset_s,
        "delay_s": delay_s,
        "stratum": float(stratum),
        "root_delay_s": root_delay_s,
        "root_dispersion_s": root_dispersion_s,
        "poll_interval_s": poll_s,
        "sync_health": 1.0 if sync_ok else 0.0,
    }
    for k in list(row.keys()):
        if row[k] is None:
            del row[k]

    return {
        "format_version": 1,
        "probe_id": f"remote-{host}-{port}",
        "probe_ip": host,
        "metadata": meta,
        "series": [row],
    }

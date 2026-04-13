"""Parse local NTP client tooling output into a normalized snapshot dict."""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

_CMD_TIMEOUT = 8.0


def _run(cmd: list[str]) -> Optional[str]:
    """Run command; return stdout or None if missing/failed."""
    bin0 = cmd[0]
    if shutil.which(bin0) is None:
        return None
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_CMD_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug(f"ntp local: command {cmd!r} failed: {e}")
        return None
    if proc.returncode != 0:
        logger.debug(f"ntp local: {cmd!r} exit {proc.returncode}: {proc.stderr!r}")
        return None
    return proc.stdout or ""


def _parse_chronyc_tracking(text: str) -> dict[str, Any]:
    """Parse `chronyc tracking` key: value output."""
    out: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip().lower().replace(" ", "_")
        val = rest.strip()
        out[key] = val

    offset_s: Optional[float] = None
    jitter_s: Optional[float] = None
    stratum: Optional[int] = None
    ref = None

    # Last offset     : +0.000000123 seconds
    m = re.search(r"last offset\s*:\s*([+-]?[\d.eE+-]+)\s*seconds?", text, re.I)
    if m:
        try:
            offset_s = float(m.group(1))
        except ValueError:
            pass
    m = re.search(r"rms offset\s*:\s*([+-]?[\d.eE+-]+)\s*seconds?", text, re.I)
    if m:
        try:
            jitter_s = float(m.group(1))
        except ValueError:
            pass
    m = re.search(r"stratum\s*:\s*(\d+)", text, re.I)
    if m:
        try:
            stratum = int(m.group(1))
        except ValueError:
            pass
    m = re.search(r"reference id\s*:\s*(\S+)(?:\s*\(([^)]+)\))?", text, re.I)
    if m:
        ref = m.group(2) or m.group(1)

    sync_status = "unsynchronized"
    if "normal" in text.lower() or offset_s is not None:
        sync_status = "tracking"

    return {
        "raw_tracking": out,
        "offset_s": offset_s,
        "jitter_s": jitter_s,
        "stratum": stratum,
        "reference_id": ref,
        "sync_status": sync_status,
        "observation_source": "chronyc_tracking",
    }


def _parse_chronyc_sources(text: str) -> dict[str, Any]:
    """Parse `chronyc sources` for reach and selected source."""
    reach: Optional[int] = None
    selected: Optional[str] = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("MS") or line.startswith("="):
            continue
        # ^* or ^+ prefix indicates selected/accepted
        if line.startswith("*") or line.startswith("+"):
            parts = line.split()
            if len(parts) >= 7:
                try:
                    reach = int(parts[5], 8) if parts[5].startswith("0") else int(parts[5])
                except ValueError:
                    try:
                        reach = int(parts[5])
                    except ValueError:
                        pass
                selected = parts[1]
            break
        # Fallback: last column often reach (octal)
        parts = line.split()
        if len(parts) >= 7 and parts[0] in ("^*", "^+", "*", "+"):
            # already handled
            pass
    if reach is None:
        # Try any line with 377 octal style
        m = re.search(r"\b([0-7]{3})\b", text)
        if m:
            try:
                reach = int(m.group(1), 8)
            except ValueError:
                pass

    return {
        "reachability": reach,
        "selected_source": selected,
        "observation_source": "chronyc_sources",
    }


def _parse_ntpq(text: str) -> dict[str, Any]:
    """Parse `ntpq -p` / `ntpq -pn` output."""
    offset_s: Optional[float] = None
    delay_s: Optional[float] = None
    jitter_s: Optional[float] = None
    stratum: Optional[int] = None
    reach: Optional[int] = None
    ref = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("remote") or line.startswith("="):
            continue
        if line.startswith("*") or line.startswith("+") or line.startswith("-"):
            parts = line.split()
            # remote refid st t when poll reach delay offset jitter
            if len(parts) >= 10:
                try:
                    stratum = int(parts[2])
                except ValueError:
                    pass
                try:
                    delay_s = float(parts[7]) / 1000.0  # ms -> s
                    offset_s = float(parts[8]) / 1000.0
                    jitter_s = float(parts[9]) / 1000.0
                except (ValueError, IndexError):
                    pass
                try:
                    reach = int(parts[6], 8) if parts[6].startswith("0") else int(parts[6])
                except ValueError:
                    try:
                        reach = int(parts[6])
                    except ValueError:
                        pass
                ref = parts[1]
            break

    return {
        "offset_s": offset_s,
        "delay_s": delay_s,
        "jitter_s": jitter_s,
        "stratum": stratum,
        "reachability": reach,
        "reference_id": ref,
        "sync_status": "synced" if offset_s is not None else "unknown",
        "observation_source": "ntpq",
    }


def _parse_timedatectl(text: str) -> dict[str, Any]:
    """Parse `timedatectl status` / `show-timesync --all`."""
    sync = None
    for line in text.splitlines():
        low = line.lower()
        if "system clock synchronized" in low or "ntp synchronized" in low:
            if "yes" in low:
                sync = True
            elif "no" in low:
                sync = False
    sync_status = "unknown"
    if sync is True:
        sync_status = "synchronized"
    elif sync is False:
        sync_status = "unsynchronized"

    return {
        "sync_status": sync_status,
        "observation_source": "timedatectl",
    }


def _parse_systemctl_show(text: str) -> dict[str, Any]:
    """Parse `systemctl show` / `systemctl status` for systemd-timesyncd."""
    active = None
    for line in text.splitlines():
        if line.strip().lower().startswith("activestate="):
            active = line.split("=", 1)[1].strip().lower() == "active"
            break
    if active is None and "active (running)" in text.lower():
        active = True
    sync_status = "unknown"
    if active is True:
        sync_status = "service_active"
    elif active is False:
        sync_status = "service_inactive"

    return {"sync_status": sync_status, "observation_source": "systemctl_timesyncd"}


def _merge_int(a: Optional[int], b: Optional[int]) -> Optional[int]:
    return a if a is not None else b


def _merge_float(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return a if a is not None else b


def collect_local_snapshot(
    probe_id: str,
    probe_ip: str,
    probe_name: str,
    collection_host: str,
) -> dict[str, Any]:
    """
    Run the local fallback chain and return a snapshot document (metadata + one series row).

    probe_ip: IP used in ProbeKey (e.g. 127.0.0.1 for local).
    """
    merged: dict[str, Any] = {
        "mode": "local_host",
        "probe_name": probe_name,
        "target_host": "",
        "target_port": 0,
        "sync_status": "unknown",
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
        "observation_source": "none",
        "collection_host": collection_host,
    }
    extras: dict[str, Any] = {}

    t = _run(["chronyc", "tracking"])
    if t:
        p = _parse_chronyc_tracking(t)
        extras["chronyc_tracking"] = p.get("raw_tracking", {})
        merged["offset_last_s"] = _merge_float(merged["offset_last_s"], p.get("offset_s"))
        merged["jitter_s"] = _merge_float(merged["jitter_s"], p.get("jitter_s"))
        merged["stratum"] = _merge_int(merged["stratum"], p.get("stratum"))
        merged["reference_id"] = p.get("reference_id") or merged["reference_id"]
        merged["sync_status"] = p.get("sync_status", merged["sync_status"])
        merged["observation_source"] = p.get("observation_source", merged["observation_source"])

    t = _run(["chronyc", "sources", "-v"]) or _run(["chronyc", "sources"])
    if t:
        p = _parse_chronyc_sources(t)
        merged["reachability"] = _merge_int(merged["reachability"], p.get("reachability"))
        if p.get("selected_source"):
            merged["reference_id"] = merged["reference_id"] or p["selected_source"]
        merged["observation_source"] = p.get("observation_source", merged["observation_source"])

    if merged["offset_last_s"] is None and merged["stratum"] is None:
        t = _run(["ntpq", "-pn"]) or _run(["ntpq", "-p"])
        if t:
            p = _parse_ntpq(t)
            merged["offset_last_s"] = _merge_float(merged["offset_last_s"], p.get("offset_s"))
            merged["delay_s"] = _merge_float(merged["delay_s"], p.get("delay_s"))
            merged["jitter_s"] = _merge_float(merged["jitter_s"], p.get("jitter_s"))
            merged["stratum"] = _merge_int(merged["stratum"], p.get("stratum"))
            merged["reachability"] = _merge_int(merged["reachability"], p.get("reachability"))
            merged["reference_id"] = merged["reference_id"] or p.get("reference_id")
            merged["sync_status"] = p.get("sync_status", merged["sync_status"])
            merged["observation_source"] = p.get("observation_source", merged["observation_source"])

    t = _run(["timedatectl", "show-timesync", "--all"]) or _run(["timedatectl", "status"])
    if t:
        p = _parse_timedatectl(t)
        if merged["sync_status"] == "unknown":
            merged["sync_status"] = p.get("sync_status", merged["sync_status"])
        merged["observation_source"] = p.get("observation_source", merged["observation_source"])
        extras["timedatectl"] = t[:2000]

    t = _run(["systemctl", "show", "systemd-timesyncd", "--property=ActiveState"])
    if not t:
        t = _run(["systemctl", "status", "systemd-timesyncd", "--no-pager"])
    if t:
        p = _parse_systemctl_show(t)
        if merged["sync_status"] == "unknown":
            merged["sync_status"] = p.get("sync_status", merged["sync_status"])
        merged["observation_source"] = p.get("observation_source", merged["observation_source"])
        extras["systemctl"] = t[:2000]

    now = datetime.now(tz=timezone.utc)
    row: dict[str, Any] = {
        "time": now.isoformat(),
        "phase_offset_s": merged["offset_last_s"],
        "delay_s": merged["delay_s"],
        "jitter_s": merged["jitter_s"],
        "stratum": float(merged["stratum"]) if merged["stratum"] is not None else None,
        "reachability": float(merged["reachability"]) if merged["reachability"] is not None else None,
        "dispersion_s": merged["dispersion_s"],
        "root_delay_s": merged["root_delay_s"],
        "root_dispersion_s": merged["root_dispersion_s"],
        "poll_interval_s": merged["poll_interval_s"],
        "sync_health": 1.0 if merged["sync_status"] in ("tracking", "synchronized", "synced") else 0.0,
    }

    for k in list(row.keys()):
        if row[k] is None:
            del row[k]

    meta = {k: v for k, v in merged.items() if v is not None}
    meta["additional_metadata"] = extras

    return {
        "format_version": 1,
        "probe_id": probe_id,
        "probe_ip": probe_ip,
        "metadata": meta,
        "series": [row],
    }

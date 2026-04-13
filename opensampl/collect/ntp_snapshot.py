"""Write NTP JSON snapshots in the format expected by :class:`opensampl.vendors.ntp.NtpProbe`."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def snapshot_filename(probe_ip: str, probe_id: str, ts: datetime | None = None) -> str:
    """Build canonical snapshot filename (UTC timestamp)."""
    ts = ts or datetime.now(tz=timezone.utc)
    ip_part = probe_ip.replace(".", "-")
    return f"ntp_{ip_part}_{probe_id}_{ts.strftime('%Y%m%dT%H%M%SZ')}.json"


def write_snapshot(doc: dict[str, Any], output_dir: str | os.PathLike[str]) -> str:
    """Serialize *doc* to *output_dir* using :func:`snapshot_filename`."""
    from pathlib import Path

    out = Path(os.fspath(output_dir))
    out.mkdir(parents=True, exist_ok=True)
    name = snapshot_filename(doc["probe_ip"], doc["probe_id"])
    path = out / name
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return str(path)

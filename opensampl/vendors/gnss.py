"""GPS/GNSS probe collection and parser support."""

from __future__ import annotations

import json
import subprocess
import textwrap
from datetime import datetime, timezone
from io import StringIO
from typing import TYPE_CHECKING, Any

import click
import pandas as pd
import yaml
from pydanclick import from_pydantic
from pydantic import Field

from opensampl.load_data import load_probe_metadata
from opensampl.metrics import METRICS
from opensampl.mixins.collect import CollectMixin
from opensampl.references import REF_TYPES
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import VENDORS, ProbeKey

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class GnssProbe(BaseProbe, CollectMixin):
    """Collect and load GPS/GNSS fixes exposed by a local or remote gpsd."""

    vendor = VENDORS.GNSS

    class CollectConfig(CollectMixin.CollectConfig):
        """
                Options passed to ``gpspipe``.

        Attributes:
            probe_id: stable probe_id slug (defaults to gpsd)
            ip_address: Host or IP address for Probe (default '127.0.0.1')
            gpsd_port: Port for gpsd (default 2947)
            output_dir: When provided, will save collected data as a file to provided directory. Filename will be
                automatically generated as GnssProbe_{host}_{probe_id}_{timestamp}.txt
            load: Whether to load collected data directly to the database
            duration: Maximum JSON reports to request from gpspipe
            timeout: Timeout in seconds for gpspipe (default 15

        """

        ip_address: str = "127.0.0.1"
        probe_id: str = "gpsd"
        gpsd_port: int = Field(2947, ge=1, le=65535)
        duration: int = Field(10, ge=1, description="Maximum JSON reports to request from gpspipe")
        timeout: float = Field(15.0, gt=0)

    @classmethod
    def get_collect_cli_options(cls) -> list[Callable]:
        """Expose gpsd-oriented names while retaining standard collection fields."""
        return [
            from_pydantic(cls.CollectConfig, rename={"ip_address": "host", "duration": "samples"}),
            click.pass_context,
        ]

    def __init__(self, input_file: str | Path, **kwargs: Any):
        """Initialize the collection config method."""
        super().__init__(input_file=input_file, **kwargs)

    def process_metadata(self) -> dict[str, Any]:
        """Read the YAML comment header written by :meth:`create_file_content`."""
        if not self.metadata_parsed:
            header: list[str] = []
            with self.input_file.open() as stream:
                for line in stream:
                    if not line.startswith("#"):
                        break
                    header.append(line[2:] if line.startswith("# ") else line[1:])
            self.metadata = yaml.safe_load("".join(header)) or {}
            self.probe_key = ProbeKey(
                ip_address=str(self.metadata.get("gpsd_host", "127.0.0.1")),
                probe_id=str(self.metadata.get("probe_id", None)),
            )
            self.metadata_parsed = True
        return self.metadata

    def process_time_data(self) -> None:
        """Load fix-health samples from a collected artifact."""
        frame = pd.read_csv(self.input_file, comment="#")
        self.process_metadata()
        if frame.empty:
            return
        self.send_data(frame[["time", "value"]], metric=METRICS.SYNC_HEALTH, reference_type=REF_TYPES.GNSS)

    @staticmethod
    def _reports(stdout: str) -> list[dict[str, Any]]:
        reports = []
        for line in stdout.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                reports.append(value)
        return reports

    @classmethod
    def collect(cls, collect_config: CollectConfig) -> CollectMixin.CollectArtifact:
        """Run ``gpspipe`` and turn TPV/SKY reports into a bounded collection."""
        command = [
            "gpspipe",
            "-w",
            "-n",
            str(collect_config.duration),
            f"{collect_config.ip_address}:{collect_config.gpsd_port}",
        ]
        try:
            result = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                timeout=collect_config.timeout,
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("GNSS collection requires 'gpspipe' from the gpsd clients package") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"gpspipe collection timed out after {collect_config.timeout:g} seconds") from exc
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or "gpspipe failed").strip()
            raise RuntimeError(f"gpspipe collection failed: {message}") from exc

        reports = cls._reports(result.stdout)
        tpv = [report for report in reports if report.get("class") == "TPV"]
        sky = [report for report in reports if report.get("class") == "SKY"]
        if not tpv:
            raise RuntimeError("gpspipe returned no TPV fix reports")

        latest = tpv[-1]
        latest_sky = sky[-1] if sky else {}
        satellites = latest_sky.get("satellites") or []
        used = sum(bool(satellite.get("used")) for satellite in satellites if isinstance(satellite, dict))
        mode = int(latest.get("mode") or 0)
        rows = []
        for report in tpv:
            stamp = report.get("time") or datetime.now(tz=timezone.utc).isoformat()
            rows.append({"time": stamp, "value": 1.0 if int(report.get("mode") or 0) >= 2 else 0.0})

        metadata = {
            "probe_id": collect_config.probe_id,
            "gpsd_host": collect_config.ip_address,
            "gpsd_port": collect_config.gpsd_port,
            "device": latest.get("device"),
            "driver": next((r.get("driver") for r in reports if r.get("class") == "DEVICE"), None),
            "fix_mode": mode,
            "satellites_visible": len(satellites),
            "satellites_used": used,
            "latitude": latest.get("lat"),
            "longitude": latest.get("lon"),
            "altitude": latest.get("altHAE", latest.get("alt")),
            "additional_metadata": {"source": "gpspipe", "reports": len(reports)},
        }
        data = cls.DataArtifact(value=pd.DataFrame(rows), metric=METRICS.SYNC_HEALTH, reference_type=REF_TYPES.GNSS)
        return cls.CollectArtifact(
            data=[data],
            probe_key=ProbeKey(ip_address=collect_config.ip_address, probe_id=collect_config.probe_id),
            metadata=metadata,
        )

    @classmethod
    def create_file_content(cls, collected: CollectMixin.CollectArtifact) -> str:
        """Serialize metadata as YAML comments followed by metric CSV."""
        buffer = StringIO()
        buffer.write(textwrap.indent(yaml.safe_dump(collected.metadata, sort_keys=False), "# "))
        buffer.write("\n")
        frame = collected.data[0].value if collected.data else pd.DataFrame(columns=["time", "value"])
        frame.to_csv(buffer, index=False)
        return buffer.getvalue()

    @classmethod
    def load_metadata(cls, probe_key: ProbeKey, metadata: dict) -> None:
        """Load this probe's metadata."""
        load_probe_metadata(vendor=cls.vendor, probe_key=probe_key, data=metadata)

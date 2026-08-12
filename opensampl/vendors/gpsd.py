"""GPSD probe collection and parser support."""

from __future__ import annotations

import json
import math
import subprocess
import textwrap
from datetime import datetime, timezone
from io import StringIO
from typing import TYPE_CHECKING, Any, ClassVar

import click
import pandas as pd
import yaml
from pydanclick import from_pydantic
from pydantic import Field

from opensampl.load_data import load_probe_metadata
from opensampl.metrics import METRICS, MetricType
from opensampl.mixins.collect import CollectMixin
from opensampl.references import REF_TYPES
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import VENDORS, ProbeKey

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class GPSDProbe(BaseProbe, CollectMixin):
    """Collect and load reports for one receiver exposed by a GPSD daemon."""

    vendor = VENDORS.GPSD
    TPV_METRICS: ClassVar[dict[str, MetricType]] = {
        "mode": METRICS.SYNC_HEALTH,
        "altHAE": METRICS.ALTITUDE_HAE,
        "altMSL": METRICS.ALTITUDE_MSL,
        "ant": METRICS.ANTENNA_STATUS,
        "antPwr": METRICS.ANTENNA_POWER_STATUS,
        "climb": METRICS.CLIMB_RATE,
        "clockbias": METRICS.CLOCK_BIAS,
        "clockdrift": METRICS.CLOCK_DRIFT,
        "datum": METRICS.DATUM,
        "depth": METRICS.DEPTH,
        "dgpsAge": METRICS.DGPS_AGE,
        "dgpsSta": METRICS.DGPS_STATION,
        "ecefx": METRICS.ECEF_X,
        "ecefy": METRICS.ECEF_Y,
        "ecefz": METRICS.ECEF_Z,
        "ecefpAcc": METRICS.ECEF_POSITION_ERROR,
        "ecefvx": METRICS.ECEF_VELOCITY_X,
        "ecefvy": METRICS.ECEF_VELOCITY_Y,
        "ecefvz": METRICS.ECEF_VELOCITY_Z,
        "ecefvAcc": METRICS.ECEF_VELOCITY_ERROR,
        "epc": METRICS.CLIMB_ERROR,
        "epd": METRICS.TRACK_ERROR,
        "eph": METRICS.HORIZONTAL_POSITION_ERROR,
        "eps": METRICS.SPEED_ERROR,
        "ept": METRICS.PHASE_OFFSET,
        "epx": METRICS.LONGITUDE_ERROR,
        "epy": METRICS.LATITUDE_ERROR,
        "epv": METRICS.VERTICAL_ERROR,
        "geoidSep": METRICS.GEOID_SEPARATION,
        "jam": METRICS.JAMMING_INDICATOR,
        "lat": METRICS.LATITUDE,
        "leapseconds": METRICS.LEAP_SECONDS,
        "lon": METRICS.LONGITUDE,
        "magtrack": METRICS.MAGNETIC_TRACK,
        "magvar": METRICS.MAGNETIC_VARIATION,
        "relD": METRICS.RELATIVE_POSITION_DOWN,
        "relE": METRICS.RELATIVE_POSITION_EAST,
        "relN": METRICS.RELATIVE_POSITION_NORTH,
        "sep": METRICS.SPHERICAL_POSITION_ERROR,
        "speed": METRICS.SPEED,
        "status": METRICS.FIX_STATUS,
        "temp": METRICS.RECEIVER_TEMPERATURE,
        "track": METRICS.TRACK,
        "velD": METRICS.VELOCITY_DOWN,
        "velE": METRICS.VELOCITY_EAST,
        "velN": METRICS.VELOCITY_NORTH,
        "wanglem": METRICS.WIND_ANGLE_MAGNETIC,
        "wangler": METRICS.WIND_ANGLE_RELATIVE,
        "wanglet": METRICS.WIND_ANGLE_TRUE,
        "wspeedr": METRICS.WIND_SPEED_RELATIVE,
        "wspeedt": METRICS.WIND_SPEED_TRUE,
        "wtemp": METRICS.WATER_TEMPERATURE,
    }

    class CollectConfig(CollectMixin.CollectConfig):
        """Options passed to ``gpspipe`` for a single GPSD device."""

        gpsd_host: str = "127.0.0.1"
        gpsd_port: int = Field(2947, ge=1, le=65535)
        device: str = Field(min_length=1)
        duration: int = Field(10, ge=1, description="Maximum JSON reports to request from gpspipe")
        timeout: float = Field(15.0, gt=0)

    @classmethod
    def get_collect_cli_options(cls) -> list[Callable]:
        """Expose GPSD-oriented collection option names."""
        return [
            from_pydantic(
                cls.CollectConfig,
                exclude=("ip_address", "probe_id"),
                rename={"duration": "samples"},
                extra_options={"device": {"required": True}},
            ),
            click.pass_context,
        ]

    def __init__(self, input_file: str | Path, **kwargs: Any):
        """Initialize a GPSD artifact parser."""
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
            device = self.metadata.get("device")
            if not device:
                raise ValueError("GPSD artifact metadata is missing a device")
            self.probe_key = ProbeKey(
                ip_address=str(self.metadata.get("gpsd_host", "127.0.0.1")),
                probe_id=str(device),
            )
            self.metadata_parsed = True
        return self.metadata

    def process_time_data(self) -> None:
        """Load all supported TPV metric samples from a collected artifact."""
        frame = pd.read_csv(self.input_file, comment="#")
        self.process_metadata()
        if frame.empty:
            return
        for field, values in frame.groupby("metric", sort=False):
            metric = self.TPV_METRICS.get(str(field))
            if metric is None:
                continue
            self.send_data(values[["time", "value"]], metric=metric, reference_type=REF_TYPES.GNSS)

    @staticmethod
    def _reports(stdout: str) -> list[dict[str, Any]]:
        """Parse complete JSON-object lines, ignoring non-JSON GPSD output."""
        reports = []
        for line in stdout.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                reports.append(value)
        return reports

    @staticmethod
    def _server_argument(host: str, port: int, device: str) -> str:
        """Build GPSD's ``server:port:device`` selector, including IPv6 brackets."""
        normalized_host = host
        if ":" in host and not host.startswith("["):
            normalized_host = f"[{host}]"
        return f"{normalized_host}:{port}:{device}"

    @staticmethod
    def _normalize_tpv_value(field: str, metric: MetricType, value: Any) -> Any:
        """Validate and convert one GPSD value to its metric representation."""
        if field == "datum":
            return metric.convert_to_type(value)
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("TPV metric value is not finite")
        if field == "mode":
            return 1.0 if int(numeric_value) >= 2 else 0.0
        return metric.convert_to_type(value)

    @classmethod
    def _tpv_artifacts(cls, reports: list[dict[str, Any]], captured_at: str) -> list[CollectMixin.DataArtifact]:
        """Coalesce partial TPV epochs and export one artifact per supported field."""
        epochs: dict[str, dict[str, Any]] = {}
        for report in reports:
            stamp = str(report.get("time") or captured_at)
            epoch = epochs.setdefault(stamp, {})
            for field, metric in cls.TPV_METRICS.items():
                if field not in report:
                    continue
                try:
                    epoch[field] = cls._normalize_tpv_value(field, metric, report[field])
                except (TypeError, ValueError):
                    continue

        artifacts = []
        for field, metric in cls.TPV_METRICS.items():
            rows = []
            for stamp, values in epochs.items():
                if field not in values:
                    continue
                rows.append({"time": stamp, "value": values[field]})
            if rows:
                artifacts.append(
                    cls.DataArtifact(
                        value=pd.DataFrame(rows),
                        metric=metric,
                        reference_type=REF_TYPES.GNSS,
                    )
                )
        return artifacts

    @classmethod
    def collect(cls, collect_config: CollectConfig) -> CollectMixin.CollectArtifact:
        """Run ``gpspipe`` and turn the selected device's TPV reports into metrics."""
        command = [
            "gpspipe",
            "-w",
            "-n",
            str(collect_config.duration),
            cls._server_argument(collect_config.gpsd_host, collect_config.gpsd_port, collect_config.device),
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
            raise RuntimeError("GPSD collection requires 'gpspipe' from the gpsd clients package") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"gpspipe collection timed out after {collect_config.timeout:g} seconds") from exc
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or "gpspipe failed").strip()
            raise RuntimeError(f"gpspipe collection failed: {message}") from exc

        captured_at = datetime.now(tz=timezone.utc).isoformat()
        reports = cls._reports(result.stdout)
        tpv = [
            report
            for report in reports
            if report.get("class") == "TPV" and report.get("device") in (None, collect_config.device)
        ]
        if not tpv:
            raise RuntimeError(f"gpspipe returned no TPV reports for device {collect_config.device!r}")

        matching_sky = [
            report
            for report in reports
            if report.get("class") == "SKY" and report.get("device") in (None, collect_config.device)
        ]
        latest_sky = matching_sky[-1] if matching_sky else {}
        satellites = latest_sky.get("satellites") or []
        used = sum(bool(satellite.get("used")) for satellite in satellites if isinstance(satellite, dict))
        driver = next(
            (
                report.get("driver")
                for report in reversed(reports)
                if report.get("class") == "DEVICE" and report.get("path") == collect_config.device
            ),
            None,
        )
        metadata = {
            "gpsd_host": collect_config.gpsd_host,
            "gpsd_port": collect_config.gpsd_port,
            "device": collect_config.device,
            "driver": driver,
            "satellites_visible": len(satellites),
            "satellites_used": used,
            "additional_metadata": {
                "source": "gpspipe",
                "reports": len(reports),
                "tpv_reports": len(tpv),
            },
        }
        return cls.CollectArtifact(
            data=cls._tpv_artifacts(tpv, captured_at),
            probe_key=ProbeKey(ip_address=collect_config.gpsd_host, probe_id=collect_config.device),
            metadata=metadata,
        )

    @classmethod
    def create_file_content(cls, collected: CollectMixin.CollectArtifact) -> str:
        """Serialize metadata and all TPV metric artifacts into one CSV stream."""
        metric_fields = {metric.name: field for field, metric in cls.TPV_METRICS.items()}
        frames = []
        for artifact in collected.data:
            field = metric_fields.get(artifact.metric.name)
            if field is None:
                continue
            frame = artifact.value.copy()
            frame["metric"] = field
            frames.append(frame)

        buffer = StringIO()
        buffer.write(textwrap.indent(yaml.safe_dump(collected.metadata, sort_keys=False), "# "))
        buffer.write("\n")
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["time", "value", "metric"])
        frame.to_csv(buffer, index=False)
        return buffer.getvalue()

    @classmethod
    def load_metadata(cls, probe_key: ProbeKey, metadata: dict) -> None:
        """Load metadata for the selected GPSD device."""
        load_probe_metadata(vendor=cls.vendor, probe_key=probe_key, data=metadata)

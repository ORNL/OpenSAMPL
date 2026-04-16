"""Probe implementation for NTP vendor"""

from __future__ import annotations

import contextlib
import random
import re
import shutil
import socket
import subprocess
import textwrap
import time
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Callable, ClassVar, Literal, TypeVar

import click
import numpy as np
import pandas as pd
import psycopg2.errors
import requests
import yaml
from loguru import logger
from pydanclick import from_pydantic
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from opensampl.load_data import load_probe_metadata
from opensampl.metrics import METRICS, MetricType
from opensampl.mixins.collect import CollectMixin
from opensampl.mixins.random_data import RandomDataMixin
from opensampl.references import REF_TYPES, ReferenceType
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import VENDORS, ProbeKey

T = TypeVar("T")


def _merge(a: T | None, b: T | None) -> T | None:
    return a if a is not None else b


class NTPCollector(BaseModel):
    """Base class for NTP Collector, for specific implementations to inherit."""

    mode: ClassVar[Literal["remote", "local"]]
    metric_map: ClassVar[dict[str, MetricType]] = {
        "phase_offset_s": METRICS.PHASE_OFFSET,
        "delay_s": METRICS.NTP_DELAY,
        "jitter_s": METRICS.NTP_JITTER,
        "stratum": METRICS.NTP_STRATUM,
        "reachability": METRICS.NTP_REACHABILITY,
        "dispersion_s": METRICS.NTP_DISPERSION,
        "root_delay_s": METRICS.NTP_ROOT_DELAY,
        "root_dispersion_s": METRICS.NTP_ROOT_DISPERSION,
        "poll_interval_s": METRICS.NTP_POLL_INTERVAL,
        "sync_health": METRICS.NTP_SYNC_HEALTH,
    }

    target_host: str

    sync_status: str = Field("unknown")
    sync_health: float | None = Field(None, json_schema_extra={"metric": True})

    stratum: float | None = Field(None, json_schema_extra={"metric": True})
    reachability: int | None = Field(None, json_schema_extra={"metric": True})
    offset_s: float | None = Field(None, serialization_alias="phase_offset_s", json_schema_extra={"metric": True})
    delay_s: float | None = Field(None, json_schema_extra={"metric": True})
    jitter_s: float | None = Field(None, json_schema_extra={"metric": True})
    reference_id: str | None = None
    observation_sources: list[str] = Field(default_factory=list)
    collection_id: str
    collection_ip: str
    probe_id: str | None = None

    extras: dict = Field(default_factory=dict, serialization_alias="additional_metadata")
    model_config = ConfigDict(serialize_by_alias=True)

    def collect(self):
        """Collect a single NTP Reading"""
        raise NotImplementedError

    def export_data(self) -> list[CollectMixin.DataArtifact]:
        """
        Export the data from the NTP Collection to a list of DataArtifacts

        Each distinct metric type will get it's own data artifact
        """
        now = datetime.now(tz=timezone.utc)
        include_list = {
            f
            for f, field_info in type(self).model_fields.items()
            if field_info.json_schema_extra and field_info.json_schema_extra.get("metric", False)
        }
        reference_type, compound_reference = self.determine_reference()
        metric_values = self.model_dump(include=include_list, exclude_none=True)

        artifacts: list[CollectMixin.DataArtifact] = []
        for m, v in metric_values.items():
            metric = self.metric_map.get(m, None)
            if metric is None:
                metric = MetricType(
                    name=m,
                    description=f"Automatically generated metric type for {m}",
                    value_type=object,
                    unit="unknown",
                )
                logger.warning(f"Generated new metric type for {m}")
            value = pd.DataFrame([(now, v)], columns=["time", "value"])
            value["time"] = pd.to_datetime(value["time"])

            artifacts.append(
                CollectMixin.DataArtifact(
                    metric=metric, reference_type=reference_type, compound_reference=compound_reference, value=value
                )
            )
        return artifacts

    def export_metadata(self) -> dict[str, Any]:
        """Export the metadata from the NTP Collection to a dict"""
        include_list = {
            f
            for f, field_info in type(self).model_fields.items()
            if not field_info.json_schema_extra or not field_info.json_schema_extra.get("metric", False)
        }
        meta = self.model_dump(include=include_list, exclude_none=True)
        meta["mode"] = self.mode
        return meta

    def export(self) -> CollectMixin.CollectArtifact:
        """Export the data + metadata for the NTP Collection to a CollectArtifact"""
        meta = self.export_metadata()

        artifacts: list[CollectMixin.DataArtifact] = self.export_data()

        return CollectMixin.CollectArtifact(data=artifacts, metadata=meta)

    @classmethod
    def invert_metric_map(cls) -> dict[str, str]:
        """Invert metric map to go from MetricType.name to string"""
        return {v.name: k for k, v in cls.metric_map.items()}

    def determine_reference(self) -> tuple[ReferenceType, None | dict[str, Any]]:
        """Get the reference type and compound reference details"""
        return REF_TYPES.PROBE, {"ip_address": self.collection_ip, "probe_id": self.collection_id}


class NTPLocalCollector(NTPCollector):
    """Collector model for taking NTP readings from local device"""

    mode: ClassVar[Literal["remote", "local"]] = "local"

    @staticmethod
    def _run(cmd: list[str], timeout: float = 8.0) -> str | None:
        """Run command; return stdout or None if missing/failed."""
        bin0 = cmd[0]
        if shutil.which(bin0) is None:
            logger.debug(f"ntp local: command {bin0!r} not found")
            return None
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as e:
            logger.debug(f"ntp local: command {cmd!r} failed: {e}")
            return None
        if proc.returncode != 0:
            logger.debug(f"ntp local: {cmd!r} exit {proc.returncode}: {proc.stderr!r}")
            return None
        logger.debug(f"ntp local: {cmd!r} exit {proc.stdout}")
        return proc.stdout or ""

    def _parse_chronyc_tracking(self, text: str) -> None:
        """Parse `chronyc tracking` key: value output."""
        out: dict[str, Any] = {}
        for l in text.splitlines():
            line = l.strip()
            if not line or ":" not in line:
                continue
            key, _, rest = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            val = rest.strip()
            out[key] = val

        # Last offset     : +0.000000123 seconds
        m = re.search(r"last offset\s*:\s*([+-]?[\d.eE+-]+)\s*seconds?", text, re.IGNORECASE)
        if m:
            with contextlib.suppress(ValueError):
                self.offset_s = _merge(self.offset_s, (m.group(1)))

        m = re.search(r"rms offset\s*:\s*([+-]?[\d.eE+-]+)\s*seconds?", text, re.IGNORECASE)
        if m:
            with contextlib.suppress(ValueError):
                self.jitter_s = _merge(self.jitter_s, float(m.group(1)))

        m = re.search(r"stratum\s*:\s*(\d+)", text, re.IGNORECASE)
        if m:
            with contextlib.suppress(ValueError):
                self.stratum = _merge(self.stratum, int(m.group(1)))

        m = re.search(r"reference id\s*:\s*(\S+)(?:\s*\(([^)]+)\))?", text, re.IGNORECASE)
        if m:
            self.reference_id = (m.group(2) or m.group(1)) or self.reference_id

        self.sync_status = "unsynchronized"
        if "normal" in text.lower() or self.offset_s is not None:
            self.sync_status = "tracking"
        self.extras["chronyc_raw_tracking"] = out
        self.observation_sources.append("chronyc_tracking")

    def _parse_chronyc_sources(self, text: str) -> None:
        """Parse `chronyc sources` for reach and selected source."""
        reach: int | None = None
        selected: str | None = None
        for l in text.splitlines():
            line = l.strip()
            if not line or line.startswith(("MS", "=")):
                continue
            # ^* or ^+ prefix indicates selected/accepted
            if line.startswith(("*", "+")):
                parts = line.split()
                if len(parts) >= 7:
                    try:
                        reach = int(parts[5], 8) if parts[5].startswith("0") else int(parts[5])
                    except ValueError:
                        with contextlib.suppress(ValueError):
                            reach = int(parts[5])
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
                with contextlib.suppress(ValueError):
                    reach = int(m.group(1), 8)

        self.reachability = self.reachability or reach
        self.reference_id = self.reference_id or selected
        self.observation_sources.append("chronyc_sources")

    def _parse_ntpq(self, text: str) -> None:
        """Parse `ntpq -p` / `ntpq -pn` output."""
        offset_s: float | None = None
        delay_s: float | None = None
        jitter_s: float | None = None
        stratum: int | None = None
        reach: int | None = None
        ref = None
        for l in text.splitlines():
            line = l.strip()
            if not line or line.startswith(("remote", "=")):
                continue
            if line.startswith(("*", "+", "-")):
                parts = line.split()
                # remote refid st t when poll reach delay offset jitter
                if len(parts) >= 10:
                    with contextlib.suppress(ValueError):
                        stratum = int(parts[2])

                    try:
                        delay_s = float(parts[7]) / 1000.0  # ms -> s
                        offset_s = float(parts[8]) / 1000.0
                        jitter_s = float(parts[9]) / 1000.0
                    except (ValueError, IndexError):
                        pass
                    try:
                        reach = int(parts[6], 8) if parts[6].startswith("0") else int(parts[6])
                    except ValueError:
                        with contextlib.suppress(ValueError):
                            reach = int(parts[6])

                    ref = parts[1]
                break
        sync_status = "synced" if offset_s is not None else "unknown"

        self.offset_s = self.offset_s or offset_s
        self.delay_s = self.delay_s or delay_s
        self.jitter_s = self.jitter_s or jitter_s
        self.stratum = self.stratum or stratum
        self.reachability = self.reachability or reach
        self.reference_id = self.reference_id or ref
        self.sync_status = sync_status or self.sync_status
        self.observation_sources.append("ntpq")

    def _parse_timedatectl(self, text: str) -> None:
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

        if self.sync_status == "unknown":
            self.sync_status = sync_status or self.sync_status
        self.observation_sources.append("timedatectl")
        self.extras["timedatectl"] = text[:2000]

    def _parse_systemctl_show(self, text: str) -> None:
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

        if self.sync_status == "unknown":
            self.sync_status = sync_status or self.sync_status
        self.extras["systemctl"] = text[:2000]
        self.observation_sources.append("systemctl_timesyncd")

    def collect(self):
        """Collect local NTP readings using various tools"""
        t = self._run(["chronyc", "tracking"])
        if t:
            self._parse_chronyc_tracking(t)

        t = self._run(["chronyc", "sources", "-v"]) or self._run(["chronyc", "sources"])
        if t:
            self._parse_chronyc_sources(t)

        if self.offset_s is None and self.stratum is None:
            t = self._run(["ntpq", "-pn"]) or self._run(["ntpq", "-p"])
            if t:
                self._parse_ntpq(t)

        t = self._run(["timedatectl", "show-timesync", "--all"]) or self._run(["timedatectl", "status"])
        if t:
            self._parse_timedatectl(t)

        t = self._run(["systemctl", "show", "systemd-timesyncd", "--property=ActiveState"])
        if not t:
            t = self._run(["systemctl", "status", "systemd-timesyncd", "--no-pager"])

        if t:
            self._parse_systemctl_show(t)

        if not self.observation_sources:
            self.observation_sources = ["none"]

        self.sync_health = 1.0 if self.sync_status in ("tracking", "synchronized", "synced") else 0.0

        if self.probe_id is None:
            self.probe_id = "ntp-local"


class NTPRemoteCollector(NTPCollector):
    """Collector model for taking readings from remote NTP Server."""

    mode: ClassVar[Literal["remote", "local"]] = "remote"

    target_port: int
    timeout: float = 3.0

    root_delay_s: float | None = Field(None, json_schema_extra={"metric": True})
    root_dispersion_s: float | None = Field(None, json_schema_extra={"metric": True})
    poll_interval_s: float | None = Field(None, json_schema_extra={"metric": True})
    leap_status: str = "unknown"

    def configure_failure(self, e: Exception) -> None:
        """Set all metric and metadata values to reflect failure to connect"""
        self.sync_status = "unreachable"
        self.sync_health = 0
        self.extras["error"] = str(e)
        self.observation_sources.append("ntplib")
        self.observation_sources.append("error")

    def _estimate_jitter_s(self) -> None:
        """
        Single NTP client response does not include RFC5905 peer jitter (that needs multiple samples).

        Emit a conservative positive bound from round-trip delay and root dispersion so downstream
        ``NTP Jitter`` metrics and dashboards have a value; chrony/ntpq local paths still supply
        true jitter when available.
        """
        if self.delay_s is None and self.root_dispersion_s is None:
            return
        d = float(self.delay_s) if self.delay_s is not None else 0.0
        r = float(self.root_dispersion_s) if self.root_dispersion_s is not None else 0.0
        est = 0.05 * d + 0.25 * r
        if est > 0:
            self.jitter_s = est
        return

    def collect(self):
        """Collect readings from a single ping against a remote NTP server."""
        try:
            import ntplib  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "Remote NTP collection requires the 'ntplib' package (install opensampl[collect])."
            ) from e
        client = ntplib.NTPClient()
        try:
            resp = client.request(self.target_host, port=self.target_port, version=3, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"NTP request to {self.target_host}:{self.target_port} failed: {e}")
            self.configure_failure(e)
            return
        leap = int(resp.leap)
        leap_map = {0: "no_warning", 1: "add_second", 2: "del_second", 3: "alarm"}
        self.leap_status = leap_map.get(leap, str(leap))

        stratum = int(resp.stratum)

        try:
            self.poll_interval_s = float(2 ** int(resp.poll))
        except (TypeError, ValueError, OverflowError):
            logger.debug("No poll interval determined")

        self.root_delay_s = float(resp.root_delay) if resp.root_delay is not None else None
        self.root_dispersion_s = float(resp.root_dispersion) if resp.root_dispersion is not None else None
        self.delay_s = float(resp.delay) if resp.delay is not None else None
        self.offset_s = float(resp.offset) if resp.offset is not None else None

        ref_id = getattr(resp, "ref_id", None)
        if hasattr(ref_id, "decode"):
            try:
                ref_id = ref_id.decode("ascii", errors="replace")
            except Exception:
                ref_id = str(ref_id)
        self.reference_id = str(ref_id) if ref_id is not None else None

        sync_ok = stratum < 16 and self.offset_s is not None
        self.observation_sources.append("ntplib")
        self.sync_status = "synchronized" if sync_ok else "unsynchronized"
        self.sync_health = 1.0 if sync_ok else 0.0
        self._estimate_jitter_s()

        self.extras["version"] = getattr(resp, "version", None)

        if self.probe_id is None:
            self.probe_id = f"remote:{self.target_port}"


def collect_ip_factory() -> str:
    """Get ip address for collection host using socket (default to 127.0.0.1)"""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # doesn't actually send data
        v = s.getsockname()[0]
    except Exception:
        v = "127.0.0.1"
    finally:
        if s:
            s.close()
    return v


def collect_id_factory() -> str:
    """Get humanreadable host name for collection host using socket (default to collection-host)"""
    try:
        return socket.gethostname() or "collection-host"
    except Exception:
        return "collection-host"


class NtpProbe(BaseProbe, CollectMixin, RandomDataMixin):
    """Probe parser for NTP vendor data files"""

    vendor = VENDORS.NTP

    class CollectConfig(CollectMixin.CollectConfig):
        """
        Configuration for Collecting NTP Readings

        Attributes:
            probe_id: stable probe_id slug (e.g. local-chrony)
            ip_address: Host or IP address for Probe (default '127.0.0.1')
            port: UDP port for remote mode (use high ports for lab mocks)
            output_dir: When provided, will save collected data as a file to provided directory. Filename will be
                automatically generated as NTP_{ip_address}_{probe_id}_{vendor}_{timestamp}.txt
            load: Whether to load collected data directly to the database
            duration: Number of seconds to collect data for
            mode: Collect remote or local NTP. Default is 'local'.
            interval: Seconds between samples; 0 = single sample and exit
            duration: Samples to collect when interval > 0
            timeout: UDP request timeout for remote mode(seconds) default: 3.0
            collection_ip: Override for the IP address of device collecting readings. Will attempt to resolve a local
                network IP using socket and fall back to '127.0.0.1'
            collection_id: Override for the Probe ID of the device collecting readings. Will attempt to resolve using
                socket.gethostname and fall back to 'collection-host'

        """

        ip_address: str = "127.0.0.1"
        port: int | None = None
        mode: Literal["remote", "local"] = "local"
        interval: float = 0.0
        duration: int = 1
        timeout: float = 3.0
        collection_ip: str = Field(default_factory=collect_ip_factory)
        collection_id: str = Field(default_factory=collect_id_factory)

    @classmethod
    def get_collect_cli_options(cls) -> list[Callable]:
        """Get the decorators to generate collection options for CLI"""
        return [
            from_pydantic(cls.CollectConfig, rename={"ip_address": "host", "duration": "count"}),
            click.pass_context,
        ]

    class RandomDataConfig(RandomDataMixin.RandomDataConfig):
        """Random NTP-like test data."""

        base_value: float = Field(
            default_factory=lambda: random.uniform(-1e-4, 1e-4),
            description="random.uniform(-1e-4, 1e-4)",
        )
        noise_amplitude: float = Field(
            default_factory=lambda: random.uniform(1e-9, 1e-7),
            description="random.uniform(1e-9, 1e-7)",
        )
        drift_rate: float = Field(
            default_factory=lambda: random.uniform(-1e-12, 1e-12),
            description="random.uniform(-1e-12, 1e-12)",
        )

    def __init__(self, input_file: str):
        """Initialize NtpProbe from input file"""
        super().__init__(input_file)
        self.collection_probe = None

    def process_metadata(self) -> dict:
        """
        Parse and return probe metadata from input file.

        Returns:
            dict with metadata field names as keys

        """
        if not self.metadata_parsed:
            header_lines = []
            with self.input_file.open() as f:
                for line in f:
                    if line.startswith("#"):
                        header_lines.append(line[2:])
                    else:
                        break

            header_str = "".join(header_lines)
            self.metadata = yaml.safe_load(header_str)
            self.collection_probe = ProbeKey(
                ip_address=self.metadata.get("collection_ip"), probe_id=self.metadata.get("collection_id")
            )
            load_probe_metadata(vendor=self.vendor, probe_key=self.collection_probe, data={"reference": True})
            self.probe_key = ProbeKey(
                ip_address=self.metadata.get("target_host"), probe_id=self.metadata.get("probe_id")
            )
            self.metadata_parsed = True

        return self.metadata

    @classmethod
    def load_metadata(cls, probe_key: ProbeKey, metadata: dict) -> None:
        """
        Parse and return probe metadata from input file.

        Returns:
            dict with metadata field names as keys

        """
        collection_probe = ProbeKey(ip_address=metadata.get("collection_ip"), probe_id=metadata.get("collection_id"))
        load_probe_metadata(vendor=cls.vendor, probe_key=collection_probe, data={"reference": True})
        load_probe_metadata(vendor=cls.vendor, probe_key=probe_key, data=metadata)

    def process_time_data(self) -> None:
        """
        Parse and load time series data from self.input_file.

        Use either send_time_data (which prefills METRICS.PHASE_OFFSET)
        or send_data and provide alternative METRICS type.
        Both require a df as follows:
            pd.DataFrame with columns:
                - time (datetime64[ns]): timestamp for each measurement
                - value (float64): measured value at each timestamp

        """
        raw_df = pd.read_csv(
            self.input_file,
            comment="#",
        )
        self.process_metadata()

        reference_type = REF_TYPES.PROBE
        grouped_dfs: dict[str, pd.DataFrame] = {
            str(metric): group.reset_index(drop=True) for metric, group in raw_df.groupby("metric")
        }
        for metr, df in grouped_dfs.items():
            metric = NTPCollector.metric_map.get(metr)
            if not metric:
                logger.warning(f"Metric {metr} is not supported for NTP. Will not ingest {len(df)} rows")
                continue
            try:
                self.send_data(
                    data=df,
                    metric=metric,
                    reference_type=reference_type,
                    compound_reference=self.collection_probe.model_dump(),
                )
            except requests.HTTPError as e:
                resp = e.response
                if resp is None:
                    raise
                status_code = resp.status_code
                if status_code == 409:
                    logger.info(f"{metr} against {self.collection_probe} already loaded for time frame, continuing..")
                    continue
                raise
            except IntegrityError as e:
                if isinstance(e.orig, psycopg2.errors.UniqueViolation):  # ty: ignore[unresolved-attribute]
                    logger.info(
                        f"{metr} against {self.collection_probe} already loaded for time "
                        f"frame already loaded for time frame, continuing.."
                    )

    @classmethod
    def collect(cls, collect_config: CollectConfig) -> CollectMixin.CollectArtifact:
        """Collect readings for an NTP probe according to collect_config."""
        collector_overrides = collect_config.model_dump(
            include=["collection_ip", "collection_id", "probe_id"], exclude_none=True
        )

        def collect_once() -> CollectMixin.CollectArtifact:
            collector = None
            if collect_config.mode == "local":
                collector = NTPLocalCollector(target_host=collect_config.ip_address, **collector_overrides)
            elif collect_config.mode == "remote":
                collector = NTPRemoteCollector(
                    target_host=collect_config.ip_address,
                    target_port=collect_config.port,
                    timeout=collect_config.timeout,
                    **collector_overrides,
                )
            if collector is None:
                raise ValueError("Could not determine mode from collect_config")
            collector.collect()

            return collector.export()

        if collect_config.interval <= 0:
            return collect_once()

        artifact = None
        for _ in range(max(collect_config.duration, 1)):
            newer = collect_once()
            if artifact is None:
                artifact = newer
            else:
                artifact.data.extend(newer.data)
                artifact.metadata |= newer.metadata

            time.sleep(collect_config.interval)

        return artifact

    @classmethod
    def create_file_content(cls, collected: CollectMixin.CollectArtifact) -> str:
        """Create the content of a file from the CollectArtifacts"""
        metric_names = NTPCollector.invert_metric_map()
        dfs = []
        for d in collected.data or []:
            df = d.value
            df["metric"] = metric_names.get(d.metric.name, d.metric.name.lower().replace(" ", "_"))
            dfs.append(df)
        value_df = pd.concat(dfs) if dfs else None

        header = yaml.dump(collected.metadata, sort_keys=False)
        header = textwrap.indent(header, prefix="# ")
        buffer = StringIO()
        buffer.write(header)
        buffer.write("\n")

        if value_df is not None:
            # write dataframe
            value_df.to_csv(buffer, index=False)

        return buffer.getvalue()

    @classmethod
    def generate_random_data(
        cls,
        config: RandomDataConfig,
        probe_key: ProbeKey,
    ) -> ProbeKey:
        """Generate synthetic NTP-like metrics for testing."""
        cls._setup_random_seed(config.seed)
        logger.info(f"Generating random NTP data for {probe_key}")

        meta = {
            "mode": "random",
            "name": f"Random NTP {probe_key}",
            "target_host": "",
            "target_port": 0,
            "sync_status": "tracking",
            "leap_status": "no_warning",
            "observation_sources": ["random"],
            "additional_metadata": {"test_data": True},
        }
        cls._send_metadata_to_db(probe_key, meta)

        total_seconds = config.duration_hours * 3600
        num_samples = int(total_seconds / config.sample_interval)
        times = []
        metric_maps = {
            "offset": {"metric": METRICS.PHASE_OFFSET, "values": []},
            "delay_s": {"metric": METRICS.NTP_DELAY, "values": []},
            "jitter_s": {"metric": METRICS.NTP_JITTER, "values": []},
            "stratum": {"metric": METRICS.NTP_STRATUM, "values": []},
            "sync_health": {"metric": METRICS.NTP_SYNC_HEALTH, "values": []},
        }

        for i in range(num_samples):
            sample_time = config.start_time + timedelta(seconds=i * config.sample_interval)
            times.append(sample_time)
            time_offset = i * config.sample_interval
            drift_component = config.drift_rate * time_offset
            noise = float(np.random.normal(0, config.noise_amplitude))
            offset = config.base_value + drift_component + noise
            if random.random() < config.outlier_probability:
                offset += float(np.random.normal(0, config.noise_amplitude * config.outlier_multiplier))

            delay_s = 0.02 + abs(0.0001 * random.random())
            jitter_s = abs(float(config.noise_amplitude * 5))
            stratum = 2.0 + (1.0 if random.random() < 0.05 else 0.0)
            sync_health = 1.0
            metric_maps["offset"]["values"].append(offset)
            metric_maps["delay_s"]["values"].append(delay_s)
            metric_maps["jitter_s"]["values"].append(jitter_s)
            metric_maps["stratum"]["values"].append(stratum)
            metric_maps["sync_health"]["values"].append(sync_health)

        for metric in metric_maps.values():
            cls.send_data(
                probe_key=probe_key,
                metric=metric.get("metric"),
                reference_type=REF_TYPES.UNKNOWN,
                data=pd.DataFrame({"time": times, "value": metric.get("values")}),
            )

        logger.info(f"Finished random NTP generation for {probe_key}")
        return probe_key

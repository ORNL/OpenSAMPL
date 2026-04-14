"""Probe implementation for NTP2 vendor"""
import socket

import pandas as pd
import re

from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import ProbeKey, VENDORS
from opensampl.references import REF_TYPES, ReferenceType
from opensampl.mixins.collect import CollectMixin
from typing import Literal, Optional, Any, TypeVar, ClassVar
from pydantic import model_validator, BaseModel, Field, field_serializer, ConfigDict
from pydanclick import from_pydantic
import click
import shutil
import subprocess
from datetime import datetime, timezone
from loguru import logger
from opensampl.metrics import METRICS, MetricType
import json
import yaml
import textwrap
from io import StringIO

T = TypeVar('T')
def _merge(a: T | None, b: T | None) -> T | None:
    return a if a is not None else b

class NTPCollector(BaseModel):
    mode: ClassVar[Literal['remote', 'local']]
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

    sync_status: str = Field("unknown")
    sync_health: float | None = Field(None, json_schema_extra={'metric': True})

    stratum: float | None = Field(None, json_schema_extra={'metric': True})
    reachability: int | None = Field(None, json_schema_extra={'metric': True})
    offset_s: float | None = Field(None, serialization_alias='phase_offset_s', json_schema_extra={'metric': True})
    delay_s: float | None = Field(None, json_schema_extra={'metric': True})
    jitter_s: float | None = Field(None, json_schema_extra={'metric': True})
    reference_id: str | None = None
    observation_sources: list[str] = Field(default_factory=list)
    collection_host: str = Field(default_factory=socket.gethostname)

    extras: dict = Field(default_factory=dict, serialization_alias='additional_metadata')
    model_config = ConfigDict(serialize_by_alias=True)

    def collect(self):
        raise NotImplementedError()

    def determine_reference(self) -> tuple[ReferenceType, Optional[dict[str, Any]]]:
        return REF_TYPES.UNKNOWN, None

    def export_data(self) -> list[CollectMixin.DataArtifact]:
        now = datetime.now(tz=timezone.utc)
        include_list = {f for f, field_info
                        in type(self).model_fields.items()
                        if field_info.json_schema_extra and field_info.json_schema_extra.get('metric', False)}
        reference_type, compound_reference = self.determine_reference()
        metric_values = self.model_dump(include=include_list, exclude_none=True)

        artifacts: list[CollectMixin.DataArtifact] = []
        for m, v in metric_values.items():
            metric = self.metric_map.get(m, None)
            if metric is None:
                metric = MetricType(name=m,
                           description=f'Automatically generated metric type for {m}',
                           value_type=object,
                           unit="unknown")
                logger.warning(f'Generated new metric type for {m}')
            value = pd.DataFrame([(now, v)], columns=['time', 'value'])
            value['time'] = pd.to_datetime(value['time'])

            artifacts.append(CollectMixin.DataArtifact(metric=metric,
                                                       reference_type=reference_type,
                                                       compound_reference=compound_reference,
                                                       value=value))
        return artifacts

    def export_metadata(self) -> dict[str, Any]:
        include_list = {f for f, field_info
                        in type(self).model_fields.items()
                        if not field_info.json_schema_extra or not field_info.json_schema_extra.get('metric', False)}
        meta = self.model_dump(include=include_list, exclude_none=True)
        meta['mode'] = self.mode
        return meta

    def export(self) -> CollectMixin.CollectArtifact:
        meta = self.export_metadata()

        artifacts: list[CollectMixin.DataArtifact] = self.export_data()

        return CollectMixin.CollectArtifact(data=artifacts, metadata=meta)

    @classmethod
    def invert_metric_map(cls):
        return {v.name: k for k, v in cls.metric_map.items()}

class NTPLocalCollector(NTPCollector):
    mode: ClassVar[Literal['remote', 'local']] = 'local'

    @staticmethod
    def _run(cmd: list[str], timeout: float = 8.0) -> Optional[str]:
        """Run command; return stdout or None if missing/failed."""
        bin0 = cmd[0]
        if shutil.which(bin0) is None:
            logger.debug(f"ntp local: command {bin0!r} not found")
            return None
        try:
            proc = subprocess.run(
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
        logger.debug(f'ntp local: {cmd!r} exit {proc.stdout}')
        return proc.stdout or ""

    def _parse_chronyc_tracking(self, text: str) -> None:
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

        # Last offset     : +0.000000123 seconds
        m = re.search(r"last offset\s*:\s*([+-]?[\d.eE+-]+)\s*seconds?", text, re.I)
        if m:
            try:
                self.offset_s = _merge(self.offset_s, (m.group(1)))
            except ValueError:
                pass
        m = re.search(r"rms offset\s*:\s*([+-]?[\d.eE+-]+)\s*seconds?", text, re.I)
        if m:
            try:
                self.jitter_s = _merge(self.jitter_s, float(m.group(1)))
            except ValueError:
                pass
        m = re.search(r"stratum\s*:\s*(\d+)", text, re.I)
        if m:
            try:
                self.stratum = _merge(self.stratum, int(m.group(1)))
            except ValueError:
                pass
        m = re.search(r"reference id\s*:\s*(\S+)(?:\s*\(([^)]+)\))?", text, re.I)
        if m:
            self.reference_id = (m.group(2) or m.group(1)) or self.reference_id

        self.sync_status = "unsynchronized"
        if "normal" in text.lower() or self.offset_s is not None:
            self.sync_status = "tracking"
        self.extras['chronyc_raw_tracking'] = out
        self.observation_sources.append("chronyc_tracking")

    def _parse_chronyc_sources(self, text: str) -> None:
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

        self.reachability = self.reachability or reach
        self.reference_id = self.reference_id or selected
        self.observation_sources.append( "chronyc_sources")

    def _parse_ntpq(self, text: str) -> None:
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

        if self.sync_status == 'unknown':
            self.sync_status = sync_status or self.sync_status
        self.observation_sources.append("timedatectl")
        self.extras['timedatectl'] = text[:2000]

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

        if self.sync_status == 'unknown':
            self.sync_status = sync_status or self.sync_status
        self.extras['systemctl'] = text[:2000]
        self.observation_sources.append("systemctl_timesyncd")

    def collect(self):
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
            self.observation_sources = ['none']

        self.sync_health = 1.0 if self.sync_status in ("tracking", "synchronized", "synced") else 0.0

    def determine_reference(self) -> tuple[ReferenceType, Optional[dict[str, Any]]]:
        if self.reference_id:
            reference_type = REF_TYPES.PROBE
            compound_reference = self.reference_id
        else:
            reference_type = REF_TYPES.UNKNOWN
            compound_reference = None
        return reference_type, compound_reference

class NTPRemoteCollector(NTPCollector):
    mode: ClassVar[Literal['remote', 'local']] = 'remote'

    target_host: str
    target_port: int
    timeout: float = 3.0

    root_delay_s: float | None = Field(None, json_schema_extra={'metric': True})
    root_dispersion_s: float | None = Field(None, json_schema_extra={'metric': True})
    poll_interval_s: float | None = Field(None, json_schema_extra={'metric': True})
    leap_status: str = "unknown"

    def configure_failure(self, e):
        self.sync_status = 'unreachable'
        self.sync_health = 0
        self.extras['error'] = str(e)
        self.observation_sources.append("ntplib")
        self.observation_sources.append("error")

    def _estimate_jitter_s(self) -> None:
        """
        Single NTP client response does not include RFC5905 peer jitter (that needs multiple samples).

        Emit a conservative positive bound from round-trip delay and root dispersion so downstream
        ``NTP Jitter`` metrics and dashboards have a value; chrony/ntpq local paths still supply true jitter when available.
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
        try:
            import ntplib  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "Remote NTP collection requires the 'ntplib' package (install opensampl[collect]).") from e
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
            logger.debug(f'No poll interval determined')

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

        self.extras['version'] = getattr(resp, 'version', None)

class NtpProbe2(BaseProbe, CollectMixin):
    """Probe parser for NTP2 vendor data files"""

    vendor = VENDORS.NTP2

    class CollectConfig(CollectMixin.CollectConfig):
        """
        Attributes:
            probe_id: stable probe_id slug (e.g. local-chrony)
            ip_address: Host or IP address for Probe (default '127.0.0.1')
            port: UDP port for remote mode (use high ports for lab mocks)
            output_dir: When provided, will save collected data as a file to provided directory. Filename will be automatically generated as ntp_{ip_address}_{probe_id}_{ts.strftime('%Y%m%dT%H%M%SZ')}.json
            load: Whether to load collected data directly to the database
            duration: Number of seconds to collect data for
            mode: Collect remote or local NTP. Default is 'local'.
            interval: Seconds between samples; 0 = single sample and exit
            duration: Samples to collect when interval > 0
            timeout: UDP request timeout for remote mode(seconds) default: 3.0
        """
        ip_address: str = '127.0.0.1'
        port: Optional[int] = None
        mode: Literal['remote', 'local'] = 'local'
        interval: float = 0.0
        duration: int = 1
        timeout: float = 3.0

    @classmethod
    def get_collect_cli_options(cls):
        return [
            from_pydantic(cls.CollectConfig, rename={'ip_address': 'host'}),
            click.pass_context,
        ]

    def __init__(self, input_file: str, **kwargs):
        """Initialize NtpProbe2 from input file"""
        super().__init__(input_file)
        # TODO: parse self.input_file to extract self.probe_key
        # self.probe_key = ProbeKey(probe_id=..., ip_address=...)

    def process_metadata(self) -> dict:
        """
        Parse and return probe metadata from input file.

        Expected metadata fields:
		['mode',
		 'probe_name',
		 'target_host',
		 'target_port',
		 'sync_status',
		 'leap_status',
		 'stratum',
		 'reachability',
		 'offset_s',
		 'delay_s',
		 'jitter_s',
		 'dispersion_s',
		 'root_delay_s',
		 'root_dispersion_s',
		 'poll_interval_s',
		 'reference_id',
		 'observation_source',
		 'collection_host',
		 'additional_metadata']

        Returns:
            dict with metadata field names as keys
        """
        # TODO: implement metadata parsing
        # return {
        #     "field_name": value,
        #     ...
        # }
        raise NotImplementedError

    def process_time_data(self) -> pd.DataFrame:
        """
        Parse and load time series data from self.input_file.

        Use either send_time_data (which prefills METRICS.PHASE_OFFSET)
        or send_data and provide alternative METRICS type.
        Both require a df as follows:
            pd.DataFrame with columns:
                - time (datetime64[ns]): timestamp for each measurement
                - value (float64): measured value at each timestamp


        """
        # TODO: implement time data parsing and call self.send_time_data(df, reference_type)
        #                                       or self.send_data(df, metric_type, reference_type)
        # df = pd.DataFrame({"time": [...], "value": [...]})
        # self.send_time_data(df, reference_type=...)

        # Ensure the format it is reading in matches that in save_to_file
        raise NotImplementedError


    @classmethod
    def collect(cls, collect_config: CollectConfig) -> CollectMixin.CollectArtifact:
        """
            Create a collect artifact defined as follows
            class CollectArtifact(BaseModel):
                data: pd.DataFrame
                metric: MetricType = METRICS.UNKNOWN
                reference_type: ReferenceType = REF_TYPES.UNKNOWN
                compound_reference: Optional[dict[str, Any]] = None
                probe_key: Optional[ProbeKey] = None
                metadata: Optional[dict] = Field(default_factory=dict)

            on a collect_config.load, the metadata and data will be loaded into db.

            define logic for the save_to_file as well.
        """
        collector = None
        if collect_config.mode == 'local':
            collector = NTPLocalCollector()
        elif collect_config.mode == 'remote':
            collector = NTPRemoteCollector(target_host=collect_config.ip_address,
                                           target_port=collect_config.port,
                                           timeout=collect_config.timeout)
        if collector is None:
            raise ValueError('Could not determine mode from collect_config')
        collector.collect()

        return collector.export()

    @classmethod
    def create_file_content(cls, collected: CollectMixin.CollectArtifact) -> str:
        single_reference = collected.single_reference
        first_data = next(iter(collected.data or []), None)
        if not single_reference:
            collected.metadata['reference'] = 'varied'
        elif first_data and first_data.compound_reference:
            collected.metadata['reference'] = json.dumps(collected.single_reference)

        metric_names = NTPCollector.invert_metric_map()
        dfs = []
        for d in collected.data or []:
            df = d.value
            df['metric'] = metric_names.get(d.metric.name, d.metric.name.lower().replace(' ', '_'))
            if not single_reference:
                df['reference'] = json.dumps(d.compound_reference)
            dfs.append(df)
        value_df = pd.concat(dfs) if dfs else None

        header = yaml.dump(collected.metadata, sort_keys=False)
        header = textwrap.indent(header, prefix='# ')
        buffer = StringIO()
        buffer.write(header)
        buffer.write('\n')

        if value_df is not None:
            # write dataframe
            value_df.to_csv(buffer, index=False)

        return buffer.getvalue()





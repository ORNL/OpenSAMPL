"""Probe implementation for NTP2 vendor"""

import pandas as pd
import re

from pandas.conftest import datetime64_dtype

from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import ProbeKey, VENDORS
from opensampl.references import REF_TYPES
from opensampl.mixins.collect import CollectMixin
from typing import Literal, Optional, Any, TypeVar
from pydantic import model_validator, BaseModel, Field, field_serializer
from pydanclick import from_pydantic
import click
import shutil
import subprocess
from datetime import datetime, timezone
from loguru import logger
from opensampl.metrics import METRICS


T = TypeVar('T')
def _merge(a: T | None, b: T | None) -> T | None:
    return a if a is not None else b


class NtpProbe2(BaseProbe, CollectMixin):
    """Probe parser for NTP2 vendor data files"""

    vendor = VENDORS.NTP2

    metric_map = {
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

    class NTPMetadata(BaseModel):
        mode: Literal['remote', 'local']

        target_host: str = ""
        target_port: int = 0

        sync_status: str = Field("unknown", serialization_alias='sync_health')
        leap_status: str = "unknown"
        stratum: int | None = None
        reachability: int | None = None
        offset_last_s: float | None = Field(None, serialization_alias='phase_offset_s')
        delay_s: float | None = None
        jitter_s: float | None = None
        dispersion_s: float | None = None
        root_delay_s: float | None = None
        root_dispersion_s: float | None = None
        poll_interval_s: float | None = None
        reference_id: str | None = None
        observation_sources: list[str] = Field(default_factory=list)
        collection_host: str | None = None

        extras: dict = Field(default_factory=dict, serialization_alias='additional_metadata')

        def parse_chronyc_tracking(self, text: str) -> None:
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
                    self.offset_last_s = _merge(self.offset_last_s, (m.group(1)))
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
            if "normal" in text.lower() or self.offset_last_s is not None:
                self.sync_status = "tracking"
            self.extras['chronyc_raw_tracking'] = out
            self.observation_sources.append("chronyc_tracking")

        def parse_chronyc_sources(self, text: str) -> None:
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

        def parse_ntpq(self, text: str) -> None:
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

            self.offset_last_s = self.offset_last_s or offset_s
            self.delay_s = self.delay_s or delay_s
            self.jitter_s = self.jitter_s or jitter_s
            self.stratum = self.stratum or stratum
            self.reachability = self.reachability or reach
            self.reference_id = self.reference_id or ref
            self.sync_status = sync_status or self.sync_status
            self.observation_sources.append("ntpq")

        def parse_timedatectl(self, text: str) -> None:
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

        def parse_systemctl_show(self, text: str) -> None:
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
		 'offset_last_s',
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

    @staticmethod
    def _run(cmd: list[str], timeout: float=8.0) -> Optional[str]:
        """Run command; return stdout or None if missing/failed."""
        bin0 = cmd[0]
        if shutil.which(bin0) is None:
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
        return proc.stdout or ""

    def collect_local(self, collect_config: CollectConfig) -> CollectMixin.CollectArtifact:
        merged = self.NTPMetadata(mode='local', probe_name=collect_config.probe_id)
        t = self._run(["chronyc", "tracking"])
        if t:
            merged.parse_chronyc_tracking(t)

        t = self._run(["chronyc", "sources", "-v"]) or self._run(["chronyc", "sources"])
        if t:
            merged.parse_chronyc_sources(t)

        if merged.offset_last_s is None and merged.stratum is None:
            t = self._run(["ntpq", "-pn"]) or self._run(["ntpq", "-p"])
            if t:
                merged.parse_ntpq(t)

        t = self._run(["timedatectl", "show-timesync", "--all"]) or self._run(["timedatectl", "status"])
        if t:
            merged.parse_timedatectl(t)

        t = self._run(["systemctl", "show", "systemd-timesyncd", "--property=ActiveState"])
        if not t:
            t = self._run(["systemctl", "status", "systemd-timesyncd", "--no-pager"])

        if t:
            merged.parse_systemctl_show(t)

        if not merged.observation_sources:
            merged.observation_source = ['none']

        now = datetime.now(tz=timezone.utc)



        row = merged.model_dump(
            include={'offset_last_s', 'delay_s', 'jitter_s', 'stratum', 'reachability', 'dispersion_s',
                     'root_delay_s', 'root_dispersion_s', 'poll_interval_s'})
        row['sync_health'] = 1.0 if merged.sync_status in ("tracking", "synchronized", "synced") else 0.0
        meta = merged.model_dump(exclude_none=True)
        if merged.reference_id:
            reference_type = REF_TYPES.PROBE
            compound_reference = merged.reference_id
        else:
            reference_type = REF_TYPES.UNKNOWN
            compound_reference = None

        artifacts: list[CollectMixin.DataArtifact] = []
        for k, v in row.items():
            value = pd.DataFrame([(now, v)], columns=['time', 'value'], dtype={'time': datetime64_dtype})
            metric = self.metric_map.get(k, None)
            if not metric:
                logger.warning(f'No metric mapping found for {k}')
                continue
            artifacts.append(CollectMixin.DataArtifact(metric=metric,
                                                       reference_type=reference_type,
                                                       compound_reference=compound_reference,
                                                       value=value))

        return CollectMixin.CollectArtifact(data=artifacts, metadata=meta)


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
        # TODO: implement the logic for creating a CollectArtifact, as above.
        #

        raise NotImplementedError

    @classmethod
    def create_file_content(cls, collected: CollectMixin.CollectArtifact) -> str:
        # TODO: Create the str content for an output file. Ensure readable by parse functions & that required metadata is available
        #  Filename will be automatically generated as {ip_address}_{probe_id}_{vendor}_{timestamp}.txt and saved to directory provided by cli
        raise NotImplementedError






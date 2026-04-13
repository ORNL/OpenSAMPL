"""NTP clock probe: JSON snapshot files from local tooling or remote NTP queries."""

from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from loguru import logger
from pydantic import Field

from opensampl.metrics import METRICS
from opensampl.references import REF_TYPES
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import VENDORS, ProbeKey

# Filename: ntp_<ip_with_dashes>_<probe_id>_<YYYYMMDDTHHMMSSZ>.json  (IPv4 uses dashes, e.g. 127-0-0-1)
_FILE_RE = re.compile(
    r"^ntp_(?P<ip>[0-9A-Za-z.-]+)_(?P<probe_id>[a-zA-Z0-9-]+)_(?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})T"
    r"(?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})Z\.json$"
)


def _dashed_ip_to_address(ip_part: str) -> str:
    """Turn 127-0-0-1 into 127.0.0.1; leave hostnames unchanged."""
    if re.match(r"^[\d-]+$", ip_part) and ip_part.count("-") == 3:
        return ip_part.replace("-", ".")
    return ip_part


class NtpProbe(BaseProbe):
    """Load NTP snapshots from JSON files produced by ``opensampl-collect ntp`` or tests."""

    vendor = VENDORS.NTP
    file_pattern: ClassVar = _FILE_RE

    class RandomDataConfig(BaseProbe.RandomDataConfig):
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

    def __init__(self, input_file: str | Path, **kwargs: Any):
        """Load JSON snapshot; optionally override ``ProbeKey`` from ``probe_id`` / ``probe_ip`` in the document."""
        super().__init__(input_file=input_file, **kwargs)
        self._doc: dict[str, Any] = {}
        raw = Path(input_file).read_text(encoding="utf-8")
        self._doc = json.loads(raw)
        fk = self._doc.get("probe_id")
        fa = self._doc.get("probe_ip")
        if isinstance(fk, str) and isinstance(fa, str):
            self.probe_key = ProbeKey(probe_id=fk, ip_address=fa)
        else:
            self.probe_key, _ = self.parse_file_name(Path(input_file))

    @classmethod
    def filter_files(cls, files: list[Path]) -> list[Path]:
        """Keep only JSON files matching :attr:`file_pattern`."""
        return [f for f in files if cls.file_pattern.fullmatch(f.name)]

    @classmethod
    def parse_file_name(cls, file_name: Path) -> tuple[ProbeKey, datetime]:
        """
        Parse ``ntp_<ip>_<probe_id>_<utc_ts>.json`` into probe key and file timestamp.

        IPv4 addresses are written with dashes between octets (``127-0-0-1``).
        """
        m = cls.file_pattern.fullmatch(file_name.name)
        if not m:
            raise ValueError(f"NTP snapshot file name not recognized: {file_name.name}")
        ip = _dashed_ip_to_address(m.group("ip"))
        probe_id = m.group("probe_id")
        ts = datetime(
            int(m.group("y")),
            int(m.group("mo")),
            int(m.group("d")),
            int(m.group("h")),
            int(m.group("mi")),
            int(m.group("s")),
            tzinfo=timezone.utc,
        )
        return ProbeKey(probe_id=probe_id, ip_address=ip), ts

    def process_metadata(self) -> dict[str, Any]:
        """Return vendor metadata row for ``ntp_metadata``."""
        meta = dict(self._doc.get("metadata") or {})
        # Drop keys not in ORM (extra safety)
        allowed = {
            "mode",
            "probe_name",
            "target_host",
            "target_port",
            "sync_status",
            "leap_status",
            "stratum",
            "reachability",
            "offset_last_s",
            "delay_s",
            "jitter_s",
            "dispersion_s",
            "root_delay_s",
            "root_dispersion_s",
            "poll_interval_s",
            "reference_id",
            "observation_source",
            "collection_host",
            "additional_metadata",
        }
        meta = {k: v for k, v in meta.items() if k in allowed}
        if "probe_name" not in meta or not meta.get("probe_name"):
            meta["probe_name"] = f"NTP {self.probe_key.probe_id}"
        if "additional_metadata" not in meta:
            meta["additional_metadata"] = {}
        self.metadata_parsed = True
        return meta

    def process_time_data(self) -> pd.DataFrame:
        """Send time series for each metric present in each series row."""
        if not self.metadata_parsed:
            self.process_metadata()

        series = self._doc.get("series") or []
        if not series:
            logger.warning("NTP snapshot has empty series: %s", self.input_file)
            return pd.DataFrame()

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

        for row in series:
            t_raw = row.get("time")
            if t_raw is None:
                continue
            t = pd.to_datetime(t_raw, utc=True)
            for key, mtype in metric_map.items():
                if key not in row:
                    continue
                val = row[key]
                if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                    continue
                df = pd.DataFrame({"time": [t], "value": [float(val)]})
                self.send_data(
                    data=df,
                    metric=mtype,
                    reference_type=REF_TYPES.UNKNOWN,
                )

        return pd.DataFrame()

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
            "mode": "local_host",
            "probe_name": f"Random NTP {probe_key.probe_id}",
            "target_host": "",
            "target_port": 0,
            "sync_status": "tracking",
            "leap_status": "no_warning",
            "stratum": 2,
            "reachability": 377,
            "observation_source": "random",
            "collection_host": "",
            "additional_metadata": {"test_data": True},
        }
        cls._send_metadata_to_db(probe_key, meta)

        total_seconds = config.duration_hours * 3600
        num_samples = int(total_seconds / config.sample_interval)

        for i in range(num_samples):
            sample_time = config.start_time + timedelta(seconds=i * config.sample_interval)
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

            cls.send_data(
                probe_key=probe_key,
                data=pd.DataFrame({"time": [sample_time], "value": [offset]}),
                metric=METRICS.PHASE_OFFSET,
                reference_type=REF_TYPES.UNKNOWN,
            )
            cls.send_data(
                probe_key=probe_key,
                data=pd.DataFrame({"time": [sample_time], "value": [delay_s]}),
                metric=METRICS.NTP_DELAY,
                reference_type=REF_TYPES.UNKNOWN,
            )
            cls.send_data(
                probe_key=probe_key,
                data=pd.DataFrame({"time": [sample_time], "value": [jitter_s]}),
                metric=METRICS.NTP_JITTER,
                reference_type=REF_TYPES.UNKNOWN,
            )
            cls.send_data(
                probe_key=probe_key,
                data=pd.DataFrame({"time": [sample_time], "value": [stratum]}),
                metric=METRICS.NTP_STRATUM,
                reference_type=REF_TYPES.UNKNOWN,
            )
            cls.send_data(
                probe_key=probe_key,
                data=pd.DataFrame({"time": [sample_time], "value": [sync_health]}),
                metric=METRICS.NTP_SYNC_HEALTH,
                reference_type=REF_TYPES.UNKNOWN,
            )

        logger.info(f"Finished random NTP generation for {probe_key}")
        return probe_key

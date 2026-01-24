from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Literal

import pandas as pd

from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import ProbeKey, VendorType
from opensampl.references import REF_TYPES, ReferenceType


Backend = Literal["chrony", "ntpd", "timesyncd"]


@dataclass(frozen=True)
class NtpSample:
    backend: Backend
    offset_seconds: float
    raw: str
    reference: Optional[str] = None  # e.g. server/peer id if available
    stratum: Optional[int] = None


class NtpProbe(BaseProbe):
    """
    Probe that reads local clock offset from chrony/ntpd/systemd-timesyncd and reports into OpenSAMPL.
    - process_metadata(): returns dict for metadata table
    - process_time_data(): returns DataFrame with columns [time, value] where value is offset in seconds
    """

    vendor = VendorType(
        name="NTP",
        parser_class="NtpProbe",
        parser_module="ntp",
        metadata_table="ntp_metadata",      # <-- create this table (or point at your real one)
        metadata_orm="NtpMetadata",         # <-- create ORM (or point at your real one)
    )

    def __init__(
        self,
        probe_key: ProbeKey,
        *,
        reference_type: ReferenceType = REF_TYPES.UNKNOWN,
        compound_reference: Optional[dict[str, Any]] = None,
        prefer: Optional[list[Backend]] = None,
        chunk_size: Optional[int] = None,
        input_file: str = "-",  # BaseProbe expects an input_file; we don't actually use it here
    ):
        super().__init__(input_file=input_file)
        self.probe_key = probe_key
        self.reference_type = reference_type
        self.compound_reference = compound_reference or {}
        self.prefer = prefer or ["chrony", "ntpd", "timesyncd"]
        self.chunk_size = chunk_size

    # OpenSAMPL-required overrides
    def process_metadata(self) -> dict:
        sample = self._collect_best()
        return {
            "probe_id": self.probe_key.probe_id,
            "ip_address": self.probe_key.ip_address,
            "collector_backend": sample.backend,
            "collector_reference": sample.reference,
            "collector_stratum": sample.stratum,
            "collector_last_seen_utc": datetime.now(timezone.utc).isoformat(),
        }

    def process_time_data(self) -> pd.DataFrame:
        sample = self._collect_best()
        now = datetime.now(timezone.utc)
        # OpenSAMPL METRICS.PHASE_OFFSET is "Difference in seconds..." (unit="s")
        # and BaseProbe expects df columns: time (datetime64[ns]), value (float64). :contentReference[oaicite:2]{index=2}
        return pd.DataFrame({"time": [now], "value": [float(sample.offset_seconds)]})

    def run_once(self, *, send_metadata: bool = True, send_time: bool = True) -> None:
        if send_metadata and not getattr(self, "metadata_parsed", False):
            self.send_metadata()          # implemented by BaseProbe :contentReference[oaicite:3]{index=3}
            self.metadata_parsed = True

        if send_time:
            df = self.process_time_data()
            # send_time_data -> send_data(metric=PHASE_OFFSET) :contentReference[oaicite:4]{index=4}
            self.send_time_data(
                data=df,
                reference_type=self.reference_type,
                compound_reference={
                    **self.compound_reference,
                    "ntp_backend": self._detected_backend or None,
                },
            )

    @property
    def _detected_backend(self) -> Optional[Backend]:
        return getattr(self, "__detected_backend", None)

    @_detected_backend.setter
    def _detected_backend(self, v: Optional[Backend]) -> None:
        setattr(self, "__detected_backend", v)

    def _collect_best(self) -> NtpSample:
        last_err: Optional[Exception] = None
        for backend in self.prefer:
            try:
                if backend == "chrony" and self._has("chronyc"):
                    s = self._collect_chrony()
                elif backend == "ntpd" and self._has("ntpq"):
                    s = self._collect_ntpd()
                elif backend == "timesyncd" and self._has("timedatectl"):
                    s = self._collect_timesyncd()
                else:
                    continue

                self._detected_backend = s.backend
                return s
            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(f"No working NTP collector found. Last error: {last_err!r}")

    @staticmethod
    def _has(cmd: str) -> bool:
        return shutil.which(cmd) is not None

    @staticmethod
    def _run(cmd: list[str], timeout_s: int = 3) -> str:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        out = (p.stdout or "").strip()
        if p.returncode != 0:
            raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{out}")
        return out

    # ---- chrony: `chronyc tracking`
    def _collect_chrony(self) -> NtpSample:
        raw = self._run(["chronyc", "tracking"])
        # Example fields (vary by version):
        #   Reference ID    : 1A2B3C4D (server)
        #   Stratum         : 2
        #   Last offset     : +0.000000123 seconds
        #   System time     : 0.000000456 seconds fast of NTP time
        ref = self._m(raw, r"^Reference ID\s*:\s*(.+)$", flags=re.M)
        stratum = self._mi(raw, r"^Stratum\s*:\s*(\d+)\s*$", flags=re.M)

        # Prefer "System time" because it’s explicit about fast/slow.
        off = self._mf(raw, r"^System time\s*:\s*([+-]?\d+(?:\.\d+)?)\s+seconds\s+(fast|slow)\s+of\s+NTP\s+time",
                       flags=re.M)
        if off is not None:
            val, fastslow = off
            offset = float(val)
            if fastslow.lower() == "slow":
                offset = -abs(offset)
            else:
                offset = abs(offset)
            return NtpSample(backend="chrony", offset_seconds=offset, raw=raw, reference=ref, stratum=stratum)

        # Fallback: "Last offset : +X seconds"
        last = self._mf1(raw, r"^Last offset\s*:\s*([+-]?\d+(?:\.\d+)?)\s+seconds", flags=re.M)
        if last is None:
            raise ValueError(f"chronyc tracking: could not parse offset\n{raw}")
        return NtpSample(backend="chrony", offset_seconds=float(last), raw=raw, reference=ref, stratum=stratum)

    # ---- ntpd: `ntpq -c rv`
    def _collect_ntpd(self) -> NtpSample:
        raw = self._run(["ntpq", "-c", "rv"])
        # Typical line contains comma-separated key=val:
        # ... offset=0.123, sys_jitter=..., stratum=2, ...
        offset = self._mf1(raw, r"(?:^|,)\s*offset=([+-]?\d+(?:\.\d+)?)", flags=0)
        stratum = self._mi(raw, r"(?:^|,)\s*stratum=(\d+)", flags=0)
        if offset is None:
            raise ValueError(f"ntpq -c rv: could not parse offset\n{raw}")
        return NtpSample(backend="ntpd", offset_seconds=float(offset), raw=raw, reference=None, stratum=stratum)

    # ---- systemd-timesyncd: `timedatectl show-timesync --all`
    def _collect_timesyncd(self) -> NtpSample:
        raw = self._run(["timedatectl", "show-timesync", "--all"])
        # Properties can include:
        #   ServerName=...
        #   Stratum=...
        #   OffsetUSec=...
        server = self._m(raw, r"^ServerName=(.*)$", flags=re.M)
        stratum = self._mi(raw, r"^Stratum=(\d+)\s*$", flags=re.M)

        # OffsetUSec is microseconds; sign may appear depending on systemd version.
        off_us = self._mf1(raw, r"^OffsetUSec=([+-]?\d+)\s*$", flags=re.M)
        if off_us is None:
            # check if "OffsetNSec" is exposed
            off_ns = self._mf1(raw, r"^OffsetNSec=([+-]?\d+)\s*$", flags=re.M)
            if off_ns is None:
                raise ValueError(f"timedatectl show-timesync: could not parse OffsetUSec/OffsetNSec\n{raw}")
            offset = float(off_ns) / 1e9
        else:
            offset = float(off_us) / 1e6

        return NtpSample(backend="timesyncd", offset_seconds=offset, raw=raw, reference=server, stratum=stratum)

    # Small regex helpers
    @staticmethod
    def _m(text: str, pat: str, flags: int = 0) -> Optional[str]:
        m = re.search(pat, text, flags)
        return m.group(1).strip() if m else None

    @staticmethod
    def _mi(text: str, pat: str, flags: int = 0) -> Optional[int]:
        s = NtpProbe._m(text, pat, flags)
        return int(s) if s is not None else None

    @staticmethod
    def _mf1(text: str, pat: str, flags: int = 0) -> Optional[float]:
        s = NtpProbe._m(text, pat, flags)
        return float(s) if s is not None else None

    @staticmethod
    def _mf(text: str, pat: str, flags: int = 0) -> Optional[tuple[float, str]]:
        m = re.search(pat, text, flags)
        if not m:
            return None
        return float(m.group(1)), m.group(2).strip()

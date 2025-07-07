"""ADVA clock implementation"""

import gzip
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO, Union

import pandas as pd

from opensampl.references import REF_TYPES
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import VENDORS, ProbeKey


class AdvaProbe(BaseProbe):
    """ADVA Probe Object"""

    timestamp: datetime
    start_time: datetime
    vendor = VENDORS.ADVA

    def __init__(self, input_file: Union[str, Path]):
        """Initialize AdvaProbe object give input_file and determines probe identity from filename"""
        super().__init__(input_file=input_file)
        self.probe_key, self.timestamp = self.parse_file_name(self.input_file)

    @classmethod
    def parse_file_name(cls, file_name: Path) -> tuple[ProbeKey, datetime]:
        """
        Parse file name into identifying parts

        Expected format: <ip_address>CLOCK_PROBE-<probe_id>-YYYY-MM-DD-HH-MM-SS.txt.gz
        """
        pattern = (
            r"(?P<ip>\d+\.\d+\.\d+\.\d+)(?P<type>CLOCK_PROBE|PTP_CLOCK_PROBE)"
            r"-(?P<identifier>\d+-\d+)-"
            r"(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)-"
            r"(?P<hour>\d+)-(?P<minute>\d+)-(?P<second>\d+)\.txt(?:\.gz)?"
        )
        match = re.match(pattern, file_name.name)
        if match:
            ip_address = match.group("ip")
            probe_id = match.group("identifier")
            timestamp = (
                f"{match.group('year')}-{match.group('month')}-{match.group('day')} "
                f"{match.group('hour')}:{match.group('minute')}:{match.group('second')}"
            )

            # Convert timestamp to datetime object
            timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").astimezone(tz=timezone.utc)

            return ProbeKey(probe_id=probe_id, ip_address=ip_address), timestamp
        raise ValueError(f"Could not parse file name {file_name} into probe key and timestamp for ADVA probe")

    def _open_file(self) -> Union[TextIO, gzip.GzipFile]:
        """Open the input file, handling both .txt and .txt.gz formats"""
        if self.input_file.name.endswith(".gz"):
            return gzip.open(self.input_file, "rt")
        return self.input_file.open()

    def process_time_data(self) -> None:
        """Process time data from ADVA probe files"""
        compression = "gzip" if self.input_file.name.endswith(".gz") else None

        df = pd.read_csv(
            self.input_file,
            compression=compression,
            header=None,
            comment="#",
            names=["time", "value"],
            dtype={"time": "float64", "value": "float64"},
            engine="python",
            sep=r",\s*",
        )
        if not self.metadata_parsed:
            # need to get the probe's start time from the metadata if we do not already have it
            self.process_metadata()

        base_time = pd.Timestamp(self.start_time)
        offsets = pd.to_timedelta(df["time"], unit="s")
        df["time"] = base_time + offsets

        df["value_str"] = df["value"].apply(lambda x: f"{x:.10e}")

        self.send_time_data(data=df, reference_type=REF_TYPES.GNSS)

    def process_metadata(self) -> dict:
        """Process metadata from ADVA probe files"""
        header_to_column = {
            "Adva Direction": "adva_direction",
            "Adva MTIE Mask": "adva_mtie_mask",
            "Adva Mask Margin": "adva_mask_margin",
            "Adva Probe": "adva_probe",
            "Adva Reference": "adva_reference",
            "Adva Reference Expected QL": "adva_reference_expected_ql",
            "Adva Source": "adva_source",
            "Adva Status": "adva_status",
            "Adva Version": "adva_version",
            "Frequency": "frequency",
            "Multiplier": "multiplier",
            "Start": "start",
            "TimeMultiplier": "timemultiplier",
            "Title": "title",
            "Type": "type",
        }
        headers = {}
        freeform_header = {}
        with self._open_file() as f:
            for line in f:
                if not line.startswith("#"):
                    break
                header = line.lstrip("#").strip()
                key, value = header.split(": ")
                if key in header_to_column:
                    headers[header_to_column.get(key)] = value
                else:
                    freeform_header[key] = value
        headers["additional_metadata"] = freeform_header
        self.start_time = datetime.strptime(headers["start"], "%Y/%m/%d %H:%M:%S").astimezone(tz=timezone.utc)
        self.metadata_parsed = True
        return headers

"""ADVA clock implementation"""

import gzip
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, TextIO, Union

import click
import pandas as pd
from loguru import logger
from pydantic import Field

from opensampl.metrics import METRICS
from opensampl.references import REF_TYPES
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import VENDORS, ProbeKey


class AdvaProbe(BaseProbe):
    """ADVA Probe Object"""

    timestamp: datetime
    start_time: datetime
    vendor = VENDORS.ADVA

    file_pattern: ClassVar = re.compile(
        r"(?P<ip>\d+\.\d+\.\d+\.\d+)(?P<type>CLOCK_PROBE|PTP_CLOCK_PROBE)"
        r"-(?P<identifier>\d+-\d+)-"
        r"(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)-"
        r"(?P<hour>\d+)-(?P<minute>\d+)-(?P<second>\d+)\.txt(?:\.gz)?"
    )

    class RandomDataConfig(BaseProbe.RandomDataConfig):
        """Model for storing random data generation configurations as provided by CLI or YAML"""

        # Time series parameters
        base_value: float = Field(
            default_factory=lambda: random.uniform(-1e-6, 1e-6), description="random.uniform(-1e-6, 1e-6)"
        )
        noise_amplitude: float = Field(
            default_factory=lambda: random.uniform(1e-9, 1e-8), description="random.uniform(1e-9, 1e-8)"
        )
        drift_rate: float = Field(
            default_factory=lambda: random.uniform(-1e-12, 1e-12), description="random.uniform(-1e-12, 1e-12)"
        )

    @classmethod
    def get_random_data_cli_options(cls) -> list:
        """Return vendor-specific random data generation options."""
        base_options = super().get_random_data_cli_options()
        vendor_options = [
            click.option(
                "--probe-id",
                type=str,
                help=(
                    "The probe_id you want the random data to show up under. "
                    "Randomly generated for each probe if left empty; incremented if multiple probes"
                ),
            ),
        ]
        return base_options + vendor_options

    def __init__(self, input_file: Union[str, Path]):
        """Initialize AdvaProbe object give input_file and determines probe identity from filename"""
        super().__init__(input_file=input_file)
        self.probe_key, self.timestamp = self.parse_file_name(self.input_file)

    @classmethod
    def filter_files(cls, files: list[Path]) -> list[Path]:
        """Filter the files found in the input directory when loading to those which match the regex"""
        return [f for f in files if cls.file_pattern.fullmatch(f.name)]

    @classmethod
    def parse_file_name(cls, file_name: Path) -> tuple[ProbeKey, datetime]:
        """
        Parse file name into identifying parts

        Expected format: <ip_address>CLOCK_PROBE-<probe_id>-YYYY-MM-DD-HH-MM-SS.txt.gz
        """
        match = re.match(cls.file_pattern, file_name.name)
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

    @classmethod
    def generate_random_data(
        cls,
        config: RandomDataConfig,
        probe_key: ProbeKey,
    ) -> ProbeKey:
        """
        Generate random ADVA probe test data and send it directly to the database.

        Args:
            probe_key: Probe key to use (generated if None)
            config: RandomDataConfig with parameters specifying how to generate data

        Returns:
            ProbeKey: The probe key used for the generated data

        """
        cls._setup_random_seed(config.seed)

        logger.info(f"Generating random ADVA data for {probe_key}")

        # Generate and send metadata
        metadata = {
            "adva_source": "RANDOM GENERATION",
            "title": f"Test ADVA Clock Probe {probe_key.probe_id}",
            "type": "PHASE",
            "additional_metadata": {"test_data": True, "random_generation_config": config.model_dump()},
        }

        cls._send_metadata_to_db(probe_key, metadata)

        # Generate time series using base class helper
        df = config.generate_time_series()

        # Send data to database
        cls.send_data(
            probe_key=probe_key,
            data=df,
            metric=METRICS.PHASE_OFFSET,
            reference_type=REF_TYPES.GNSS,
        )

        logger.info(f"Successfully generated {config.duration_hours}h of random ADVA data for {probe_key}")
        return probe_key

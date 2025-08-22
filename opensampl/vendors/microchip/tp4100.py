"""MicrochipTP4100 clock Parser implementation"""

import random
from pathlib import Path
from typing import ClassVar, Optional, Union

import click
import pandas as pd
import yaml
from loguru import logger
from pydantic import Field

from opensampl.metrics import METRICS
from opensampl.references import REF_TYPES
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import VENDORS, ProbeKey


class MicrochipTP4100Probe(BaseProbe):
    """MicrochipTP4100 Probe Object"""

    vendor = VENDORS.MICROCHIP_TP4100
    MEASUREMENTS: ClassVar = {
        "time-error (ns)": METRICS.PHASE_OFFSET,
    }
    REFERENCES: ClassVar = {"GNSS": REF_TYPES.GNSS}

    class RandomDataConfig(BaseProbe.RandomDataConfig):
        """Model for storing random data generation configurations as provided by CLI or YAML"""

        # Time series parameters
        base_value: Optional[float] = Field(
            default_factory=lambda: random.uniform(-5e-7, 5e-7), description="random.uniform(-5e-7, 5e-7)"
        )
        noise_amplitude: Optional[float] = Field(
            default_factory=lambda: random.uniform(1e-8, 5e-8), description="random.uniform(1e-8, 5e-8)"
        )
        drift_rate: Optional[float] = Field(
            default_factory=lambda: random.uniform(-1e-10, 1e-10), description="random.uniform(-1e-10, 1e-10)"
        )

        metric_type: str = "time-error (ns)"
        reference_type: str = "GNSS"

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
        """Initialize MicrochipTP4100 object given input_file and determines probe identity from file headers"""
        super().__init__(input_file=input_file)
        self.header = self.get_header()
        self.probe_key = ProbeKey(
            ip_address=self.header.get("host"), probe_id=self.header.get("probe_id", None) or "1-1"
        )

    def get_header(self) -> dict:
        """Retrieve the yaml formatted header information from the input file loaded into a dict"""
        header_lines = []
        with self.input_file.open() as f:
            for line in f:
                if line.startswith("#"):
                    header_lines.append(line[2:])
                else:
                    break

        header_str = "".join(header_lines)
        return {k.strip().lower(): v for k, v in yaml.safe_load(header_str).items()}

    @classmethod
    def filter_files(cls, files: list[Path]) -> list[Path]:
        """Filter the files found in input directory to only take .csv and .txt"""
        return [x for x in files if any(x.name.endswith(ext) for ext in (".csv", ".txt"))]

    def process_time_data(self) -> None:
        """
        Process time series data from the input file.

        Returns:
            pd.DataFrame: DataFrame with columns:
                - time (datetime64[ns]): timestamp for each measurement
                - value (float64): measured value at each timestamp

        """
        collection_method = self.header.get("method", "")
        try:
            df = pd.read_csv(
                self.input_file,
                delimiter=", " if collection_method == "download_file" else ",",
                comment="#",
                engine="python",
            )
        except pd.errors.EmptyDataError as e:
            raise ValueError(f"No data in {self.input_file}") from e

        if len(df) == 0:
            raise ValueError(f"No data in {self.input_file}")

        header_metric = self.header.get("metric").lower()  # We want a value error raised if it's not in there at all
        metric = self.MEASUREMENTS.get(header_metric, None)

        if metric is None:
            logger.warning(f"Metric type {header_metric} not configured for MicrochipTWST; skipping upload")
            return

        if len(df.columns) < 2:
            raise ValueError("Expected at at least 2 columns in the CSV")
        df.columns = ["time", "value", *df.columns[2:]]

        if "(ns)" in header_metric:
            df["value"] = df["value"].apply(lambda x: float(x) / 1e9)

        if collection_method == "download_file":
            df["time"] = pd.to_datetime(df["time"], format="%Y-%m-%d,%H:%M:%S", utc=True)

        header_ref = self.header.get("reference").upper()
        reference = self.REFERENCES.get(header_ref, None)
        if reference is None:
            logger.warning(
                f"Reference type {header_ref} not configured for MicrochipTWST. Setting reference as unknown."
            )
            reference = REF_TYPES.UNKNOWN

        self.send_data(data=df, metric=metric, reference_type=reference)

    def process_metadata(self) -> dict:
        """
        Process metadata from the input file.

        Returns:
            dict: Dictionary mapping table names to ORM objects

        """
        return {"additional_metadata": self.header, "model": "TP 4100"}

    @classmethod
    def generate_random_data(
        cls,
        config: RandomDataConfig,
        probe_key: ProbeKey,
    ) -> ProbeKey:
        """
        Generate random TP4100 test data and send it directly to the database.

        Args:
            probe_key: Probe key to use (generated if None)
            config: RandomDataConfig with parameters specifying how to generate data

        Returns:
            ProbeKey: The probe key used for the generated data

        """
        cls._setup_random_seed(config.seed)

        logger.info(f"Generating random TP4100 data for {probe_key}")

        # Generate metadata header similar to real TP4100 files
        metadata_header = {
            "title": f"Test TP4100 Performance Monitor {probe_key.probe_id}",
            "test_data": True,
            "random_generation_config": config.model_dump(),
        }

        # Generate and send metadata
        metadata = {"additional_metadata": metadata_header, "model": "TP 4100"}

        cls._send_metadata_to_db(probe_key, metadata)

        # Generate time series using base class helper (in nanoseconds, then convert)
        df = config.generate_time_series()

        # Determine metric and reference types
        metric = cls.MEASUREMENTS.get(config.metric_type.lower(), METRICS.PHASE_OFFSET)
        reference = cls.REFERENCES.get(config.reference_type.upper(), REF_TYPES.GNSS)

        # Send data to database
        cls.send_data(
            probe_key=probe_key,
            data=df,
            metric=metric,
            reference_type=reference,
        )

        logger.info(f"Successfully generated {config.duration_hours}h of random TP4100 data for {probe_key}")
        return probe_key

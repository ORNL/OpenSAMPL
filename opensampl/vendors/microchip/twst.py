"""Microchip TWST clock Parser implementation"""

import random
import re
from datetime import timedelta
from pathlib import Path
from typing import ClassVar, Optional, Union

import click
import numpy as np
import pandas as pd
import psycopg2.errors
import requests
import yaml
from loguru import logger
from pydantic import Field
from sqlalchemy.exc import IntegrityError

from opensampl.load_data import load_probe_metadata
from opensampl.metrics import METRICS
from opensampl.references import REF_TYPES
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import VENDORS, ProbeKey


class MicrochipTWSTProbe(BaseProbe):
    """MicrochipTWST Probe Object"""

    vendor = VENDORS.MICROCHIP_TWST
    MEASUREMENTS: ClassVar = {"meas:offset": METRICS.PHASE_OFFSET, "tracking:ebno": METRICS.EB_NO}

    class RandomDataConfig(BaseProbe.RandomDataConfig):
        """Model for storing random data generation configurations as provided by CLI or YAML"""

        # Time series parameters
        base_value: Optional[float] = Field(
            default_factory=lambda: random.uniform(-1e-8, 1e-8), description="random.uniform(-1e-8, 1e-8)"
        )
        noise_amplitude: Optional[float] = Field(
            default_factory=lambda: random.uniform(1e-10, 1e-9), description="random.uniform(1e-10, 1e-9)"
        )
        drift_rate: Optional[float] = Field(
            default_factory=lambda: random.uniform(-1e-12, 1e-12), description="random.uniform(-1e-12, 1e-12)"
        )

        ebno_base_value: Optional[float] = Field(
            default_factory=lambda: random.uniform(10.0, 20.0), description="random.uniform(10.0, 20.0)"
        )
        ebno_noise_amplitude: Optional[float] = Field(
            default_factory=lambda: random.uniform(0.5, 2.0), description="random.uniform(0.5, 2.0)"
        )
        ebno_drift_rate: Optional[float] = Field(
            default_factory=lambda: random.uniform(-0.01, 0.01), description="random.uniform(-0.01, 0.01)"
        )

        num_channels: int = Field(4)

        probe_id: str = "modem"

        def generate_ebno_time_series(self):
            """Given the settings of this particular RandomDataConfig, generate random Eb/No Data"""
            total_seconds = self.duration_hours * 3600
            num_samples = int(total_seconds / self.sample_interval)

            time_points = []
            values = []
            for i in range(num_samples):
                sample_time = self.start_time + timedelta(seconds=i * self.sample_interval)
                time_points.append(sample_time)

                # Generate value with drift and noise
                time_offset = i * self.sample_interval
                drift_component = self.ebno_drift_rate * time_offset
                noise_component = np.random.normal(0, self.ebno_noise_amplitude)
                value = self.ebno_base_value + drift_component + noise_component

                # Add occasional outliers for realism
                if random.random() < self.outlier_probability:
                    value += np.random.normal(0, self.ebno_noise_amplitude * self.outlier_multiplier)

                values.append(value)

            return pd.DataFrame({"time": time_points, "value": values})

    @classmethod
    def get_random_data_cli_options(cls) -> list:
        """Return vendor-specific random data generation options."""
        base_options = super().get_random_data_cli_options()
        vendor_options = [
            click.option(
                "--num-channels",
                type=int,
                help=(
                    f"Number of remote channels to generate data for "
                    f"(default: {cls.RandomDataConfig.model_fields.get('num_channels').default})"
                ),
            ),
            click.option(
                "--ebno-base-value",
                type=float,
                help=(
                    f"Base value for Eb/No measurements "
                    f"(default = {cls.RandomDataConfig.model_fields.get('base_value').description!s})"
                ),
            ),
            click.option(
                "--ebno-noise-amplitude",
                type=float,
                help=(
                    f"Noise amplitude/standard deviation for Eb/No measurements "
                    f"(default = {cls.RandomDataConfig.model_fields.get('noise_amplitude').description!s})"
                ),
            ),
            click.option(
                "--ebno-drift-rate",
                type=float,
                help=(
                    f"Linear drift rate per second for Eb/No measurements "
                    f"(default = {cls.RandomDataConfig.model_fields.get('drift_rate').description!s})"
                ),
            ),
        ]
        return vendor_options + base_options

    def __init__(self, input_file: Union[str, Path]):
        """Initialize MicrochipTWST object give input_file and determines probe identity from filename"""
        super().__init__(input_file=input_file)
        self.header = self.get_header()
        self.probe_key = ProbeKey(probe_id="modem", ip_address=self.header["local"]["ip"])

    def process_time_data(self) -> None:
        """Process time series data from the input file."""
        df = pd.read_csv(
            self.input_file,
            comment="#",
        )
        measurement_suffix = "|".join(map(re.escape, self.MEASUREMENTS.keys()))
        pattern = rf"chan:\d+:{measurement_suffix}$"
        df_mask = df["reading"].str.contains(pattern)
        included_rows = df_mask.sum()
        excluded_rows = len(df) - included_rows
        logger.info(f"Included {included_rows}/{len(df)} rows, Excluded {excluded_rows}/{len(df)} rows")
        df = df[df_mask].copy()

        df.rename(columns={"timestamp": "time"}, inplace=True)
        df["channel"] = df["reading"].str.extract(r"chan:(\d+)").astype(int)
        df["measurement"] = df["reading"].str.extract(r"chan:\d+:(.*)")

        grouped_dfs = {
            (chan, meas): group.reset_index(drop=True)
            for (chan, meas), group in df.groupby(["channel", "measurement"])  # ty: ignore[not-iterable]
        }

        for key, df in grouped_dfs.items():
            logger.debug(f"Loading: {key}")
            channel, measurement = key
            compound_key = {"ip_address": self.probe_key.ip_address, "probe_id": f"chan:{channel}"}

            metric = self.MEASUREMENTS.get(measurement)
            if not metric:
                raise ValueError(f"Unknown metrics type {measurement}")

            try:
                self.send_data(data=df, metric=metric, reference_type=REF_TYPES.PROBE, compound_reference=compound_key)
            except requests.HTTPError as e:
                resp = e.response
                if resp is None:
                    raise
                status_code = resp.status_code
                if status_code == 409:
                    logger.info(f"(chan, meas)={key} already loaded for time frame, continuing..")
                    continue
                raise
            except IntegrityError as e:
                if isinstance(e.orig, psycopg2.errors.UniqueViolation):  # ty: ignore[unresolved-attribute]
                    logger.info(f"Chan: meas={key} already loaded for time frame, continuing..")

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
        return yaml.safe_load(header_str)

    def process_metadata(self) -> dict:
        """
        Process metadata from the input file.

        Returns:
            dict: Dictionary mapping table names to ORM objects

        """
        for chan, info in self.header.get("remotes").items():
            # TODO: we will have to make sure channel 1 is the same probe somehow
            remote_probe_key = ProbeKey(ip_address=self.probe_key.ip_address, probe_id=f"chan:{chan}")
            load_probe_metadata(
                vendor=self.vendor, probe_key=remote_probe_key, data={"additional_metadata": info, "model": "ATS 6502"}
            )
        modem_data = self.header.get("local")
        self.metadata_parsed = True
        return {"additional_metadata": modem_data, "model": "ATS 6502"}

    @classmethod
    def _generate_random_probe_key(cls, gen_config: RandomDataConfig, probe_index: int) -> ProbeKey:
        if gen_config.probe_ip is not None:
            ip_address = cls._generate_random_ip()
        elif probe_index > 0:
            ip_address = f"{gen_config.probe_ip}.{probe_index}"
        else:
            ip_address = str(gen_config.probe_ip)

        return ProbeKey(probe_id="modem", ip_address=ip_address)

    @classmethod
    def generate_random_data(
        cls,
        config: RandomDataConfig,
        probe_key: ProbeKey,
    ) -> ProbeKey:
        """
        Generate random TWST modem test data and send it directly to the database.

        Args:
            probe_key: Probe key to use (generated if None)
            config: RandomDataConfig with parameters specifying how to generate data

        Returns:
            ProbeKey: The probe key used for the generated data

        """
        cls._setup_random_seed(config.seed)

        logger.info(f"Generating random TWST data for {probe_key}")

        # Generate and send metadata for main modem
        main_metadata = {
            "additional_metadata": {
                "sid": f"STATION_{random.choice('ABCDEFGH')}",
                "prn": random.randint(100, 999),
                "ip": probe_key.ip_address,
                "test_data": True,
                "random_generation_config": config.model_dump(),
            },
            "model": "ATS 6502",
        }

        cls._send_metadata_to_db(probe_key, main_metadata)

        # Generate and send metadata for remote channels
        for channel in range(1, config.num_channels + 1):
            remote_probe_key = ProbeKey(ip_address=probe_key.ip_address, probe_id=f"chan:{channel}")
            remote_metadata = {
                "additional_metadata": {
                    "rx_channel": f"ch{channel}",
                    "sid": f"STATION_{random.choice('ABCDEFGH')}",
                    "prn": random.randint(100, 999),
                    "test_data": True,
                    "random_generation_config": config.model_dump(),
                },
                "model": "ATS 6502",
            }
            cls._send_metadata_to_db(remote_probe_key, remote_metadata)

            for measurement, metric in cls.MEASUREMENTS.items():
                logger.debug(f"Generating data for channel {channel}, measurement {measurement}")

                # Generate time series using base class helper
                df = (
                    config.generate_time_series()
                    if measurement == "meas:offset"
                    else config.generate_ebno_time_series()
                )

                # Send data with compound reference for the channel
                compound_key = {"ip_address": probe_key.ip_address, "probe_id": f"chan:{channel}"}
                cls.send_data(
                    probe_key=probe_key,
                    data=df,
                    metric=metric,
                    reference_type=REF_TYPES.PROBE,
                    compound_reference=compound_key,
                )

        logger.info(f"Successfully generated {config.duration_hours}h of random TWST data for {probe_key}")
        return probe_key

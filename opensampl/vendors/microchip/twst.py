"""Microchip TWST clock Parser implementation"""

import re
from pathlib import Path
from typing import ClassVar, Union

import pandas as pd
import psycopg2.errors
import requests
import yaml
from loguru import logger
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

"""MicrochipTP4100 clock Parser implementation"""

from pathlib import Path
from typing import ClassVar, Union

import pandas as pd
import yaml
from loguru import logger

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

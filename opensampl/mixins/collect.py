"""Tools for adding data collection functionality to probes"""

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import pandas as pd
from loguru import logger
from pydanclick import from_pydantic
from pydantic import BaseModel, ConfigDict, Field

from opensampl.load_data import load_probe_metadata
from opensampl.metrics import METRICS, MetricType
from opensampl.references import REF_TYPES, ReferenceType
from opensampl.vendors.constants import ProbeKey


class CollectMixin(ABC):
    """Mixin to add data collection capabilities to a probe class"""

    class DataArtifact(BaseModel):
        """Model for a single metric type of collected data"""

        value: pd.DataFrame
        metric: MetricType = METRICS.UNKNOWN
        reference_type: ReferenceType = REF_TYPES.UNKNOWN
        compound_reference: dict[str, Any] | None = None
        model_config = ConfigDict(arbitrary_types_allowed=True)

    class CollectArtifact(BaseModel):
        """Model for a single probe's collected data"""

        data: list["CollectMixin.DataArtifact"]
        probe_key: ProbeKey | None = None
        metadata: dict | None = Field(default_factory=dict)
        model_config = ConfigDict(arbitrary_types_allowed=True)

        @property
        def single_reference(self):
            """All individual data artifacts use the same reference"""
            if len(self.data) <= 1:
                return True
            return len({json.dumps(x.compound_reference, sort_keys=True) for x in self.data or []}) == 1

        @property
        def single_reference_type(self) -> bool:
            """All individual data artifacts use the same reference type"""
            if len(self.data) <= 1:
                return True
            return len({x.reference_type.name for x in self.data or []}) == 1

    class CollectConfig(BaseModel):
        """
        Configuration for collecting data

        Attributes:
            output_dir: When provided, will save collected data as a file to provided directory.
                Filename will be automatically generated as {vendor}_{ip_address}_{probe_id}_{vendor}_{timestamp}.txt
            load: Whether to load collected data directly to the database
            duration: Number of seconds to collect data for

        """

        output_dir: Path | None = None
        load: bool = False
        duration: int = 300

        ip_address: str = "127.0.0.1"
        probe_id: str = "1-1"

    @classmethod
    def collect_help_str(cls) -> str:
        """Help string for use in the collect CLI."""
        return (
            f"Collect data readings for {cls.__name__}\n\n"
            "Can collect data to a directory (using --output-dir), straight into the database (--load), or both"
        )

    @classmethod
    def get_collect_cli_options(cls) -> list[Callable]:
        """Return the click options/arguments for collecting probe data."""
        return [
            from_pydantic(cls.CollectConfig),
            click.pass_context,
        ]

    @classmethod
    def get_collect_cli_command(cls) -> Callable:
        """
        Create a click command that handles data collection

        Returns
        -------
            A click CLI command that collects probe data

        """

        def make_command(f: Callable) -> Callable:
            for option in reversed(cls.get_collect_cli_options()):
                f = option(f)
            return click.command(name=cls.vendor.name.lower(), help=cls.collect_help_str())(f)

        def collect_callback(
            ctx: click.Context,  # noqa: ARG001
            collect_config: CollectMixin.CollectConfig,
        ) -> None:
            """Load probe data from file or directory."""
            try:
                cls._collect_and_save(collect_config)

            except Exception as e:
                logger.exception(f"Error: {e!s}")
                raise click.Abort(f"Error: {e!s}") from e

        return make_command(collect_callback)

    @classmethod
    def _collect_and_save(cls, collect_config: CollectConfig) -> None:
        data: CollectMixin.CollectArtifact = cls.collect(collect_config)
        if data.probe_key is None:
            data.probe_key = ProbeKey(ip_address=collect_config.ip_address, probe_id=collect_config.probe_id)
        if collect_config.load:
            cls.load_metadata(probe_key=data.probe_key, metadata=data.metadata)

            for art in data.data:
                cls.send_data(
                    data=art.value,
                    metric=art.metric,
                    reference_type=art.reference_type,
                    compound_reference=art.compound_reference,
                    probe_key=data.probe_key,
                )
        if collect_config.output_dir:
            file_content = cls.create_file_content(data)
            collect_config.output_dir.mkdir(parents=True, exist_ok=True)
            now_stamp = datetime.now(tz=timezone.utc).timestamp()
            output = collect_config.output_dir / f"{cls.vendor.parser_class}_{data.probe_key!r}_{now_stamp}.txt"
            output.write_text(file_content)

    @classmethod
    def filter_files(cls, files: list[Path]) -> list[Path]:
        """Filter the files found in the input directory when loading this vendor's data files"""
        return [f for f in files if f.name.startswith(f"{cls.vendor.parser_class}_") and f.suffix == ".txt"]

    @classmethod
    def load_metadata(cls, probe_key: ProbeKey, metadata: dict) -> None:
        """
        Load provided metadata associated with given probe_key

        Distinct from BaseProbe.parse_metadata because it is a class method without access to self.input_file
        """
        load_probe_metadata(vendor=cls.vendor, probe_key=probe_key, data=metadata)

    @classmethod
    @abstractmethod
    def collect(cls, collect_config: CollectConfig) -> CollectArtifact:
        """Collect data and output CollectArtifact using collect_config"""
        pass

    @classmethod
    @abstractmethod
    def create_file_content(cls, collect_artifact: CollectArtifact) -> str:
        """Given a CollectArtifact, create the str content for a file"""
        pass

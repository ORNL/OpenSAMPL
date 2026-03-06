from abc import ABC, abstractmethod
import click
from typing import Any, Callable, ClassVar, Optional, TypeVar, Union

import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field, ConfigDict
from pydanclick import from_pydantic
from pathlib import Path

from opensampl.load_data import load_probe_metadata
from opensampl.metrics import MetricType, METRICS
from opensampl.references import ReferenceType, REF_TYPES
from opensampl.vendors.constants import ProbeKey
from datetime import datetime, timezone


class CollectMixin(ABC):
    class CollectArtifact(BaseModel):
        data: pd.DataFrame
        metric: MetricType = METRICS.UNKNOWN
        reference_type: ReferenceType = REF_TYPES.UNKNOWN
        compound_reference: Optional[dict[str, Any]] = None
        probe_key: Optional[ProbeKey] = None
        metadata: Optional[dict] = Field(default_factory=dict)
        model_config = ConfigDict(arbitrary_types_allowed=True)

    class CollectConfig(BaseModel):
        """
        # TODO make sure one of load or output provided
        Attributes:
            output_dir: When provided, will save collected data as a file to provided directory. Filename will be automatically generated as {ip_address}_{probe_id}_{vendor}_{timestamp}.txt
            load: Whether to load collected data directly to the database
            duration: Number of seconds to collect data for
        """
        output_dir: Optional[Path] = None
        load: bool = False
        duration: int = 300

        ip_address: str = '127.0.0.1'
        probe_id: str = '1-1'

    @classmethod
    @property
    def collect_help_str(cls) -> str:
        """Defines the help string for use in the CLI."""
        return (
            f"Collect data readings for {cls.__name__}\n\n"
            "Can collect data to a directory (using --output-dir), straight into the database (--load), or both"
        )

    @classmethod
    def get_collect_cli_options(cls):
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
            return click.command(name=cls.vendor.name.lower(), help=cls.collect_help_str)(f)

        def collect_callback(ctx: click.Context, collect_config: CollectMixin.CollectConfig) -> None:
            """Load probe data from file or directory."""
            try:
                cls._collect_and_save(collect_config)

            except Exception as e:
                logger.error(f"Error: {e!s}")
                raise click.Abort(f"Error: {e!s}") from e

        return make_command(collect_callback)

    @classmethod
    def _collect_and_save(cls, collect_config: CollectConfig) -> None:
        data: CollectMixin.CollectArtifact = cls.collect(collect_config)
        if data.probe_key is None:
            data.probe_key = ProbeKey(ip_address=collect_config.ip_address,
                                      probe_id=collect_config.probe_id,)
        if collect_config.load:
            load_probe_metadata(
                vendor=cls.vendor,
                probe_key=data.probe_key,
                data=data.metadata,
            )
            cls.send_data(
                data=data.data,
                metric=data.metric,
                reference_type=data.reference_type,
                compound_reference=data.compound_reference,
                probe_key=data.probe_key,
            )
        if collect_config.output_dir:
            file_content = cls.create_file_content(data)
            collect_config.output_dir.mkdir(parents=True, exist_ok=True)
            now_stamp = datetime.now(tz=timezone.utc).timestamp()
            output = collect_config.output_dir / f'{repr(data.probe_key)}_{now_stamp}.txt'
            output.write_text(file_content)

    @classmethod
    @abstractmethod
    def collect(cls, collect_config: CollectConfig) -> CollectArtifact:
        """Using the provided collect_config, collect data and output CollectArtifact"""
        pass

    @classmethod
    @abstractmethod
    def create_file_content(cls, CollectArtifact: CollectArtifact) -> str:
        """Given a CollectArtifact, create the str content for a file"""
        pass


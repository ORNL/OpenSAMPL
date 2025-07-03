"""Abstract probe Base which provides scaffolding for vendor specific implementation"""

from abc import ABC, abstractmethod
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, ClassVar, Optional, Union

import click
import pandas as pd
import psycopg2.errors
import requests
import requests.exceptions
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm

from opensampl.load_data import load_probe_metadata, load_time_data
from opensampl.metrics import METRICS, MetricType
from opensampl.references import ReferenceType
from opensampl.vendors.constants import ProbeKey, VendorType


class DummyTqdm:
    """Dummy tqdm object which does not print to terminal"""

    def __init__(self, *args: list, **kwargs: dict):
        """Initialize dummy tqdm object"""
        self.args = args
        self.kwargs = kwargs

    def update(self, n: int = 1) -> None:
        """Fake an update call to tqdm."""
        pass

    def close(self) -> None:
        """Close an instance of tqdm."""
        pass


@contextmanager
def dummy_tqdm(*args: list, **kwargs: dict) -> Generator:
    """Create a dummy tqdm object which will not print to terminal"""
    yield DummyTqdm(*args, **kwargs)


class LoadConfig(BaseModel):
    """Model for storing probe loading configurations as provided by CLI"""

    filepath: Path
    archive_dir: Path
    no_archive: bool = False
    metadata: bool = False
    time_data: bool = False
    max_workers: int = 4
    chunk_size: Optional[int] = None
    show_progress: bool = False


class BaseProbe(ABC):
    """BaseProbe abstract object"""

    input_file: Path
    probe_key: ProbeKey
    vendor: ClassVar[VendorType]
    chunk_size: Optional[int] = None
    metadata_parsed: bool = False

    @classmethod
    @property
    def help_str(cls) -> str:
        """Defines the help string for use in the CLI."""
        return (
            f"Processes a file or directory to load {cls.__name__} metadata and/or time series data.\n\n"
            "By default, both metadata and time series data are processed. "
            "If you specify either --metadata or --time-data, only the selected operation(s) will be performed."
        )

    @classmethod
    def get_cli_options(cls) -> list[Callable]:
        """Return the click options/arguments for the probe class."""
        return [
            click.option(
                "--metadata",
                "-m",
                is_flag=True,
                help="Load probe metadata from provided file",
            ),
            click.option(
                "--time-data",
                "-t",
                is_flag=True,
                help="Load time series data from provided file",
            ),
            click.option(
                "--archive-path",
                "-a",
                type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
                help="Override default archive directory path for processed files. Default: ./archive",
            ),
            click.option(
                "--no-archive",
                "-n",
                is_flag=True,
                help="Do not archive processed files when flag provided",
            ),
            click.option(
                "--max-workers",
                "-w",
                type=int,
                default=4,
                help="Maximum number of worker threads when processing directories",
            ),
            click.option(
                "--chunk-size",
                "-c",
                type=int,
                required=False,
                help="How many records to send at a time. If None, sends all at once. default: None",
            ),
            click.option(
                "--show-progress",
                "-p",
                is_flag=True,
                help="If flag provided, show the tqdm progress bar when processing directories. For best experience, "
                "set LOG_LEVEL=ERROR when using this option.",
            ),
            click.argument(
                "filepath",
                type=click.Path(exists=True, path_type=Path),
            ),
            click.pass_context,
        ]

    @classmethod
    def process_single_file(  # noqa: PLR0912, C901
        cls,
        filepath: Path,
        metadata: bool,
        time_data: bool,
        archive_dir: Path,
        no_archive: bool,
        chunk_size: Optional[int] = None,
        pbar: Optional[Union[tqdm, DummyTqdm]] = None,
        **kwargs: dict,
    ) -> None:
        """Process a single file with the given options."""
        try:
            probe = cls(filepath, **kwargs)
            probe.chunk_size = chunk_size
            try:
                if metadata:
                    logger.debug(f"Loading {cls.__name__} metadata from {filepath}")
                    probe.send_metadata()
                    logger.debug(f"Metadata loading complete for {filepath}")
            except requests.exceptions.HTTPError as e:
                resp = e.response
                if resp is None:
                    raise
                status_code = resp.status_code
                if status_code == 409:
                    logger.warning(
                        f"{filepath} violates unique constraint for metadata, implying already loaded.  "
                        f"Will move to archive if archiving is enabled"
                    )
                else:
                    raise

            try:
                if time_data:
                    logger.debug(f"Loading {cls.__name__} time series data from {filepath}")
                    probe.process_time_data()
                    logger.debug(f"Time series data loading complete for {filepath}")
            except requests.exceptions.HTTPError as e:
                resp = e.response
                if resp is None:
                    raise
                status_code = resp.status_code
                if status_code == 409:
                    logger.warning(
                        f"{filepath} violates unique constraint for time data, implying already loaded. "
                        f"Will move to archive if archiving is enabled."
                    )
                else:
                    raise
            except IntegrityError as e:
                if isinstance(e.orig, psycopg2.errors.UniqueViolation):  # ty: ignore[unresolved-attribute]
                    logger.warning(
                        f"{filepath} violates unique constraint for time data, implying already loaded. "
                        f"Will move to archive if archiving is enabled."
                    )

            if not no_archive:
                probe.archive_file(archive_dir)

            if pbar:
                pbar.update(1)

        except Exception as e:
            logger.error(f"Error processing file {filepath}: {e!s}", exc_info=True)
            raise

    def archive_file(self, archive_dir: Path):
        """
        Archive processed probe file

        Puts the file in the archive directory, with year/month/vendor/ipaddress_id hierarchy based on
        date that the file was processed.
        """
        now = datetime.now(tz=timezone.utc)
        archive_path = archive_dir / str(now.year) / f"{now.month:02d}" / self.vendor.name / str(self.probe_key)
        archive_path.mkdir(parents=True, exist_ok=True)
        self.input_file.rename(archive_path / self.input_file.name)

    @classmethod
    def get_cli_command(cls) -> Callable:
        """
        Create a click command that handles both single files and directories.

        Returns
        -------
            A click CLI command that loads and processes probe data.

        """

        def make_command(f: Callable) -> Callable:
            for option in reversed(cls.get_cli_options()):
                f = option(f)
            return click.command(name=cls.vendor.name.lower(), help=cls.help_str)(f)

        def load_callback(ctx: click.Context, **kwargs: dict) -> None:
            """Load probe data from file or directory."""
            try:
                config = cls._extract_load_config(ctx, kwargs)
                cls._prepare_archive(config.archive_dir, config.no_archive)

                if config.filepath.is_file():
                    cls._process_file(config, kwargs)
                elif config.filepath.is_dir():
                    cls._process_directory(config, kwargs)

            except Exception as e:
                logger.error(f"Error: {e!s}")
                raise click.Abort()  # noqa: RSE102,B904

        return make_command(load_callback)

    @classmethod
    def _extract_load_config(cls, ctx: click.Context, kwargs: dict) -> LoadConfig:
        """
        Extract and normalize CLI keyword arguments into a LoadConfig object.

        Args:
        ----
            ctx: Click context object
            kwargs: Dictionary of keyword arguments passed to the CLI command

        Returns:
        -------
            A LoadConfig object with all relevant parameters

        """
        config = LoadConfig(
            filepath=kwargs.pop("filepath"),
            archive_dir=kwargs.pop("archive_path", None) or ctx.obj["conf"].ARCHIVE_PATH,
            metadata=kwargs.pop("metadata", False),
            time_data=kwargs.pop("time_data", False),
            no_archive=kwargs.pop("no_archive", False),
            max_workers=kwargs.pop("max_workers", 4),
            chunk_size=kwargs.pop("chunk_size", None),
            show_progress=kwargs.pop("show_progress", False),
        )

        if not config.metadata and not config.time_data:
            config.metadata = True
            config.time_data = True

        return config

    @classmethod
    def _prepare_archive(cls, archive_dir: Path, no_archive: bool) -> None:
        """
        Create the archive output directory if archiving is enabled.

        Args:
        ----
            archive_dir: Path to the archive output directory
            no_archive: If True, skip creating the archive directory

        """
        if not no_archive:
            archive_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _process_file(cls, config: LoadConfig, extra_kwargs: dict) -> None:
        """
        Process a single probe data file.

        Args:
        ----
            config: LoadConfig object containing file, archive, and processing flags
            extra_kwargs: Additional keyword arguments passed to the processing function

        """
        cls.process_single_file(
            config.filepath,
            config.metadata,
            config.time_data,
            config.archive_dir,
            config.no_archive,
            config.chunk_size,
            **extra_kwargs,
        )

    @classmethod
    def _process_directory(cls, config: LoadConfig, extra_kwargs: dict) -> None:
        """
        Process all files in a directory using a thread pool and optional progress bar.

        Args:
        ----
            config: LoadConfig object containing directory, archive, and processing flags
            extra_kwargs: Additional keyword arguments passed to the processing function

        Raises:
        ------
            Logs and continues on individual thread exceptions, but does not raise

        """
        files = [x for x in config.filepath.iterdir() if x.is_file()]
        logger.info(f"Found {len(files)} files in directory {config.filepath}")
        progress_context = tqdm if config.show_progress else dummy_tqdm

        with progress_context(total=len(files), desc=f"Processing {config.filepath.name}") as pbar:  # noqa: SIM117
            with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                futures = [
                    executor.submit(
                        cls.process_single_file,
                        file,
                        config.metadata,
                        config.time_data,
                        config.archive_dir,
                        config.no_archive,
                        config.chunk_size,
                        pbar=pbar,
                        **extra_kwargs,
                    )
                    for file in files
                ]

                for future in futures:
                    try:
                        future.result()
                    except Exception as e:  # noqa: PERF203
                        logger.error(f"Error in thread: {e!s}")

    @property
    def probe_id(self):
        """Return probe_id of probe"""
        return self.probe_key.probe_id

    @property
    def ip_address(self):
        """Return ip_address of probe"""
        return self.probe_key.ip_address

    def __init__(self, input_file: str):
        """Initialize probe given input file"""
        self.input_file = Path(input_file)

    @abstractmethod
    def process_time_data(self) -> pd.DataFrame:
        """
        Process time series data.

        Returns
        -------
            pd.DataFrame: DataFrame with columns:
                - time (datetime64[ns]): timestamp for each measurement
                - value (float64): measured value at each timestamp

        """

    def send_data(
        self,
        data: pd.DataFrame,
        metric: MetricType,
        reference_type: ReferenceType,
        compound_reference: Optional[dict[str, Any]] = None,
    ):
        """Ingests data into the database"""
        if self.chunk_size:
            for chunk_start in range(0, len(data), self.chunk_size):
                chunk = data.iloc[chunk_start : chunk_start + self.chunk_size]
                load_time_data(
                    probe_key=self.probe_key,
                    metric_type=metric,
                    reference_type=reference_type,
                    data=chunk,
                    compound_key=compound_reference,
                )
        else:
            load_time_data(
                probe_key=self.probe_key,
                metric_type=metric,
                reference_type=reference_type,
                data=data,
                compound_key=compound_reference,
            )

    def send_time_data(
        self, data: pd.DataFrame, reference_type: ReferenceType, compound_reference: Optional[dict[str, Any]] = None
    ):
        """
        Ingests time data into the database

        :param chunk_size: How many records to send at a time. If None, sends all at once. default: None
        :return:
        """
        self.send_data(
            data=data, metric=METRICS.PHASE_OFFSET, reference_type=reference_type, compound_reference=compound_reference
        )

    @abstractmethod
    def process_metadata(self) -> dict:
        """
        Process metadata

        Returns
        -------
            Dict[str, Any] which is for some or all of the metadata fields for the specific vendor

        """

    def send_metadata(self):
        """Send metadata to database"""
        metadata = self.process_metadata()
        load_probe_metadata(vendor=self.vendor, probe_key=self.probe_key, data=metadata)

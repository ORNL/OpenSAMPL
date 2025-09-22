"""Abstract probe Base which provides scaffolding for vendor specific implementation"""

import random
import shutil
from abc import ABC, abstractmethod
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, ClassVar, Optional, TypeVar, Union

import click
import numpy as np
import pandas as pd
import psycopg2.errors
import requests
import requests.exceptions
import yaml
from loguru import logger
from pydantic import BaseModel, ValidationInfo, field_serializer, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm

from opensampl.load_data import load_probe_metadata, load_time_data
from opensampl.metrics import METRICS, MetricType
from opensampl.references import ReferenceType
from opensampl.vendors.constants import ProbeKey, VendorType

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class dualmethod:  # noqa: N801
    """
    Allows a method to be called both as an instance method and as a class method with the same function definition.

    When called on an instance, the first argument will be the instance.
    When called on the class, the first argument will be the class itself.

    Example:
        ```python
        class MyClass:
            @dualmethod
            def greet(self_or_cls, name: str = "World"):
                if isinstance(self_or_cls, MyClass):
                    print(f"Instance says: Hello {name}")
                else:
                    print(f"Class says: Hello {name}")


        # Can be called on class
        MyClass.greet("Alice")  # Class says: Hello Alice

        # Can be called on instance
        obj = MyClass()
        obj.greet("Bob")  # Instance says: Hello Bob
        ```

    """

    def __init__(self, func: F) -> None:
        """
        Initialize the dualmethod descriptor.

        Args:
            func: The function to be wrapped as a dual method

        """
        self.func: F = func
        self.__doc__: Optional[str] = func.__doc__
        fname = getattr(func, "__name__", None)
        self.__name__: str = fname
        self.__qualname__: str = getattr(func, "__qualname__", fname)

    def __get__(self, obj: Optional[T], cls: type[T]) -> Callable[..., Any]:
        """
        Descriptor protocol method that returns the appropriate bound method.

        Args:
            obj: The instance from which the method is being accessed (None for class access)
            cls: The class that owns the method

        Returns:
            A wrapper function that calls the original function with either the
            instance or class as the first argument

        """

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.func(obj if obj is not None else cls, *args, **kwargs)

        # Preserve function metadata
        wrapper.__name__ = self.__name__
        wrapper.__doc__ = self.__doc__
        wrapper.__qualname__ = self.__qualname__

        return wrapper


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

    class RandomDataConfig(BaseModel):
        """Model for storing random data generation configurations as provided by CLI or YAML"""

        # General configuration
        num_probes: int = 1
        duration_hours: float = 1.0
        seed: Optional[int] = None

        # Time series parameters
        sample_interval: float = 1

        base_value: float
        noise_amplitude: float
        drift_rate: float
        outlier_probability: float = 0.01
        outlier_multiplier: float = 10.0

        # Start time (computed at runtime if None)
        start_time: Optional[datetime] = None

        probe_id: Union[str, None] = None
        probe_ip: Optional[str] = None

        @classmethod
        def _generate_random_ip(cls) -> str:
            """Generate a random IP address."""
            ip_parts = [random.randint(1, 254) for _ in range(4)]
            return ".".join(map(str, ip_parts))

        @model_validator(mode="after")
        def define_start_time(self):
            """If start_time is None at the end of validation,"""
            if self.start_time is None:
                self.start_time = datetime.now(tz=timezone.utc) - timedelta(hours=self.duration_hours)
            return self

        @field_validator("*", mode="before")
        @classmethod
        def replace_none_with_default(cls, v: Any, info: ValidationInfo) -> Any:
            """If field provided with None replace with default"""
            if v is None and info.field_name != "start_time":
                field_info = cls.model_fields.get(info.field_name)
                # fall back to the field default
                return field_info.default_factory() if field_info.default_factory else field_info.default
            return v

        @field_serializer("start_time")
        def start_time_to_str(self, start_time: datetime) -> str:
            """Convert start_time to string when dumping the model"""
            return start_time.strftime("%Y/%m/%d %H:%M:%S")

        def generate_time_series(self):
            """Generate a realistic time series with drift, noise, and occasional outliers."""
            total_seconds = self.duration_hours * 3600
            num_samples = int(total_seconds / self.sample_interval)

            time_points = []
            values = []
            for i in range(num_samples):
                sample_time = self.start_time + timedelta(seconds=i * self.sample_interval)
                time_points.append(sample_time)

                # Generate value with drift and noise
                time_offset = i * self.sample_interval
                drift_component = self.drift_rate * time_offset
                noise_component = np.random.normal(0, self.noise_amplitude)
                value = self.base_value + drift_component + noise_component

                # Add occasional outliers for realism
                if random.random() < self.outlier_probability:
                    value += np.random.normal(0, self.noise_amplitude * self.outlier_multiplier)

                values.append(value)

            return pd.DataFrame({"time": time_points, "value": values})

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
    def get_random_data_cli_options(cls) -> list[Callable]:
        """Return the click options for random data generation."""
        return [
            click.option(
                "--config",
                "-c",
                type=click.Path(exists=True, path_type=Path),
                help="YAML configuration file for random data generation settings",
            ),
            click.option(
                "--num-probes",
                type=int,
                default=1,
                help=(
                    f"Number of probes to generate data for "
                    f"(default={cls.RandomDataConfig.model_fields.get('num_probes').default})"
                ),
            ),
            click.option(
                "--duration",
                type=float,
                help=(
                    f"Duration of data in hours "
                    f"(default={cls.RandomDataConfig.model_fields.get('duration_hours').default})"
                ),
            ),
            click.option(
                "--seed",
                type=int,  # type: ignore[attr-defined]
                help=(
                    f"Random seed for reproducible results "
                    f"(default={cls.RandomDataConfig.model_fields.get('seed').default})"
                ),
            ),
            click.option(
                "--sample-interval",
                type=float,
                help=(
                    f"Sample interval in seconds "
                    f"(default={cls.RandomDataConfig.model_fields.get('sample_interval').default})"
                ),
            ),
            click.option(
                "--base-value",
                type=float,
                help=(
                    f"Base value for time offset measurements "
                    f"(default = {cls.RandomDataConfig.model_fields.get('base_value').description!s})"
                ),
            ),
            click.option(
                "--noise-amplitude",
                type=float,
                help=(
                    f"Noise amplitude/standard deviation for time offset measurements "
                    f"(default = {cls.RandomDataConfig.model_fields.get('noise_amplitude').description!s})"
                ),
            ),
            click.option(
                "--drift-rate",
                type=float,
                help=(
                    f"Linear drift rate per second for time offset measurements "
                    f"(default = {cls.RandomDataConfig.model_fields.get('drift_rate').description!s})"
                ),
            ),
            click.option(
                "--outlier-probability",
                type=float,
                default=0.01,
                help=(
                    f"Probability of outliers per sample "
                    f"(default = {cls.RandomDataConfig.model_fields.get('outlier_probability').default!s})"
                ),
            ),
            click.option(
                "--outlier-multiplier",
                type=float,
                default=10.0,
                help=(
                    f"Multiplier for outlier noise amplitude "
                    f"(default = {cls.RandomDataConfig.model_fields.get('outlier_multiplier').default!s})"
                ),
            ),
            click.option(
                "--probe-ip",
                type=str,
                help=(
                    "The ip_address you want the random data to show up under. "
                    "Randomly generated for each probe if left empty"
                ),
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
        shutil.move(str(self.input_file), str(archive_path / self.input_file.name))

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
                raise click.Abort(f"Error: {e!s}") from e

        return make_command(load_callback)

    @classmethod
    def get_random_data_cli_command(cls) -> Callable:
        """
        Create a click command that generates random test data.

        Returns
        -------
            A click CLI command that generates random test data for this probe type.

        """

        def make_command(f: Callable) -> Callable:
            # Add vendor-specific options first, then base options
            options = cls.get_random_data_cli_options()

            for option in reversed(options):
                f = option(f)
            return click.command(name=cls.vendor.name.lower(), help=f"Generate random test data for {cls.__name__}")(f)

        def random_data_callback(ctx: click.Context, **kwargs: dict) -> None:  # noqa: ARG001
            """Generate random test data for this probe type."""
            try:
                gen_config = cls._extract_random_data_config(kwargs)
                probe_keys = []
                for i in range(gen_config.num_probes):
                    # Use different seeds for each probe if seed is provided
                    probe_config = gen_config.model_copy(deep=True)
                    if probe_config.seed is not None:
                        probe_config.seed += i

                    probe_key = cls._generate_random_probe_key(probe_config, i)

                    logger.info(f"Generating data for {cls.__name__} probe {i + 1}/{gen_config.num_probes}")
                    probe_key = cls.generate_random_data(probe_config, probe_key=probe_key)
                    probe_keys.append(probe_key)

                # Print summary
                click.echo(f"\n=== Generated {len(probe_keys)} {cls.__name__} probes ===")
                for probe_key in probe_keys:
                    click.echo(f"  - {probe_key}")

                logger.info("Random test data generation completed successfully")

            except Exception as e:
                logger.exception(f"Failed to generate test data: {e}")
                raise click.Abort(f"Failed to generate test data: {e}") from e

        return make_command(random_data_callback)

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
    def _extract_random_data_config(cls, kwargs: dict) -> RandomDataConfig:
        """
        Extract and normalize CLI keyword arguments into a RandomDataConfig object.

        Args:
        ----
            kwargs: Dictionary of keyword arguments passed to the CLI command

        Returns:
        -------
            A RandomDataConfig object with all relevant parameters

        """
        # Load configuration from YAML file if provided
        config_file = kwargs.pop("config", None)
        if config_file:
            config_data = cls._load_yaml_config(config_file)
            # Merge config file data with CLI arguments (CLI args take precedence)
            for key, value in config_data.items():
                if kwargs.get(key) is None:  # Only use config value if CLI arg not provided
                    kwargs[key] = value
            logger.info(f"Loaded configuration from {config_file}")

        return cls.RandomDataConfig(**kwargs)

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
    def filter_files(cls, files: list[Path]) -> list[Path]:
        """Filter the files found in the input directory when loading this vendor's data files"""
        return files

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
        files = cls.filter_files(files)
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

    @dualmethod
    def send_data(
        self,
        data: pd.DataFrame,
        metric: MetricType,
        reference_type: ReferenceType,
        compound_reference: Optional[dict[str, Any]] = None,
        probe_key: Optional[ProbeKey] = None,
    ) -> None:
        """Ingests data into the database"""
        if isinstance(self, BaseProbe):
            probe_key = self.probe_key

        if probe_key is None:
            raise ValueError("send data must be called with probe_key if used as class method")

        if self.chunk_size:
            for chunk_start in range(0, len(data), self.chunk_size):
                chunk = data.iloc[chunk_start : chunk_start + self.chunk_size]
                load_time_data(
                    probe_key=probe_key,
                    metric_type=metric,
                    reference_type=reference_type,
                    data=chunk,
                    compound_key=compound_reference,
                )
        else:
            load_time_data(
                probe_key=probe_key,
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

    @classmethod
    def _setup_random_seed(cls, seed: Optional[int]) -> None:
        """Set up random seed for reproducible data generation."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    @classmethod
    def _generate_random_ip(cls) -> str:
        """Generate a random IP address."""
        ip_parts = [random.randint(1, 254) for _ in range(4)]
        return ".".join(map(str, ip_parts))

    @classmethod
    def _generate_time_series(
        cls,
        start_time: datetime,
        duration_hours: float,
        sample_interval_seconds: float,
        base_value: float,
        noise_amplitude: float,
        drift_rate: float = 0.0,
        outlier_probability: float = 0.01,
        outlier_multiplier: float = 10.0,
    ) -> pd.DataFrame:
        """
        Generate a realistic time series with drift, noise, and occasional outliers.

        Args:
            start_time: Start timestamp for the data
            duration_hours: Duration of data in hours
            sample_interval_seconds: Time between samples in seconds
            base_value: Base value around which to generate data
            noise_amplitude: Standard deviation of random noise
            drift_rate: Linear drift rate per second
            outlier_probability: Probability of outliers per sample
            outlier_multiplier: Multiplier for outlier noise amplitude

        Returns:
            DataFrame with 'time' and 'value' columns

        """
        total_seconds = duration_hours * 3600
        num_samples = int(total_seconds / sample_interval_seconds)

        time_points = []
        values = []

        for i in range(num_samples):
            sample_time = start_time + timedelta(seconds=i * sample_interval_seconds)
            time_points.append(sample_time)

            # Generate value with drift and noise
            time_offset = i * sample_interval_seconds
            drift_component = drift_rate * time_offset
            noise_component = np.random.normal(0, noise_amplitude)
            value = base_value + drift_component + noise_component

            # Add occasional outliers for realism
            if random.random() < outlier_probability:
                value += np.random.normal(0, noise_amplitude * outlier_multiplier)

            values.append(value)

        return pd.DataFrame({"time": time_points, "value": values})

    @classmethod
    def _load_yaml_config(cls, config_path: Path) -> dict[str, Any]:
        """
        Load YAML configuration file for random data generation.

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            Dictionary containing configuration parameters

        """
        try:
            with config_path.open() as f:
                config_data = yaml.safe_load(f)
        except FileNotFoundError as e:
            raise ValueError(f"Configuration file not found: {config_path}") from e
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration file {config_path}: {e}") from e
        except Exception as e:
            raise ValueError(f"Error loading configuration file {config_path}: {e}") from e
        else:
            # Validate that it's a dictionary
            if not isinstance(config_data, dict):
                raise TypeError(f"Configuration file {config_path} must contain a YAML dictionary")

            logger.debug(f"Loaded YAML config from {config_path}: {config_data}")
            return config_data

    @classmethod
    def _send_metadata_to_db(cls, probe_key: ProbeKey, metadata: dict) -> None:
        """Send metadata to the database."""
        load_probe_metadata(vendor=cls.vendor, probe_key=probe_key, data=metadata)
        logger.debug(f"Sent metadata for probe {probe_key}")

    @classmethod
    @abstractmethod
    def generate_random_data(
        cls,
        config: RandomDataConfig,
        probe_key: ProbeKey,
    ) -> ProbeKey:
        """
        Generate random test data and send it directly to the database.

        Args:
            probe_key: Probe key to use (generated if None)
            config: RandomDataConfig with parameters specifying how to generate data

        Returns:
            ProbeKey: The probe key used for the generated data

        """

    @classmethod
    def _generate_random_probe_key(cls, gen_config: RandomDataConfig, probe_index: int) -> ProbeKey:
        ip_address = str(gen_config.probe_ip) if gen_config.probe_ip is not None else cls._generate_random_ip()

        if gen_config.probe_id is None:
            probe_id = f"{1 + probe_index}"
        elif isinstance(gen_config.probe_id, str):
            probe_suffix = f"-{probe_index}" if probe_index > 0 else ""
            probe_id = f"{gen_config.probe_id}{probe_suffix}"

        return ProbeKey(probe_id=probe_id, ip_address=ip_address)

    def send_metadata(self):
        """Send metadata to database"""
        metadata = self.process_metadata()
        load_probe_metadata(vendor=self.vendor, probe_key=self.probe_key, data=metadata)

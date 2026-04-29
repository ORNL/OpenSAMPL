"""Tools for adding random data generation functionality to probes"""

import random
from abc import abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click
import numpy as np
import pandas as pd
import yaml
from loguru import logger
from pydantic import BaseModel, ValidationInfo, field_serializer, field_validator, model_validator

from opensampl.vendors.constants import ProbeKey


class RandomDataMixin:
    """Mixin for adding random data generation functionality to probes"""

    class RandomDataConfig(BaseModel):
        """Model for storing random data generation configurations as provided by CLI or YAML"""

        # General configuration
        num_probes: int = 1
        duration_hours: float = 1.0
        seed: int | None = None

        # Time series parameters
        sample_interval: float = 1

        base_value: float
        noise_amplitude: float
        drift_rate: float
        outlier_probability: float = 0.01
        outlier_multiplier: float = 10.0

        # Start time (computed at runtime if None)
        start_time: datetime | None = None

        probe_id: str | None = None
        probe_ip: str | None = None

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
                default=cls.RandomDataConfig.model_fields.get("num_probes").default,
                show_default=True,
                help=("Number of probes to generate data for"),
            ),
            click.option(
                "--duration",
                type=float,
                default=cls.RandomDataConfig.model_fields.get("duration_hours").default,
                show_default=True,
                help=("Duration of data in hours"),
            ),
            click.option(
                "--seed",
                show_default=True,
                default=cls.RandomDataConfig.model_fields.get("seed").default,
                type=int,  # type: ignore[attr-defined]
                help=("Random seed for reproducible results"),
            ),
            click.option(
                "--sample-interval",
                type=float,
                show_default=True,
                default=cls.RandomDataConfig.model_fields.get("sample_interval").default,
                help=("Sample interval in seconds "),
            ),
            click.option(
                "--base-value",
                type=float,
                show_default=True,
                default=cls.RandomDataConfig.model_fields.get("base_value").description,
                help=("Base value for time offset measurements"),
            ),
            click.option(
                "--noise-amplitude",
                type=float,
                show_default=True,
                default=cls.RandomDataConfig.model_fields.get("noise_amplitude").description,
                help=("Noise amplitude/standard deviation for time offset measurements "),
            ),
            click.option(
                "--drift-rate",
                type=float,
                show_default=True,
                default=cls.RandomDataConfig.model_fields.get("drift_rate").description,
                help=("Linear drift rate per second for time offset measurements "),
            ),
            click.option(
                "--outlier-probability",
                type=float,
                show_default=True,
                default=cls.RandomDataConfig.model_fields.get("outlier_probability").default,
                help=("Probability of outliers per sample "),
            ),
            click.option(
                "--outlier-multiplier",
                type=float,
                default=cls.RandomDataConfig.model_fields.get("outlier_multiplier").default,
                show_default=True,
                help=("Multiplier for outlier noise amplitude "),
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
    def _setup_random_seed(cls, seed: int | None) -> None:
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

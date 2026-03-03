from abc import ABC, abstractmethod
import click
from typing import Any, Callable, ClassVar, Optional, TypeVar, Union
from loguru import logger
from pydantic import BaseModel, Field
from pydanclick import from_pydantic
from pathlib import Path

class CollectMixin(ABC):
    class CollectConfig(BaseModel):
        """

        Attributes:
            output_dir: When provided, will save collected data as a file to provided directory. Filename will be automatically generated as {ip_address}_{probe_id}_{vendor}_{timestamp}
            load: Whether to load collected data directly to the database
            duration: Number of seconds to collect data for
        """
        output_dir: Optional[Path] = None
        load: bool = False
        duration: int = 300

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
                print(ctx.obj)
                print(collect_config)

            except Exception as e:
                logger.error(f"Error: {e!s}")
                raise click.Abort(f"Error: {e!s}") from e

        return make_command(collect_callback)

    @abstractmethod
    def collect(self):
        pass

    @abstractmethod
    def save_to_file(self):
        pass



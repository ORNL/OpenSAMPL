"""
Define the command line interface for openSAMPL.

The openSAMPL CLI package is a click based command line interface for the openSAMPL package. It provides a way to
interact with the database and load data into it.
"""

import json
import os
import sys
from pathlib import Path
from typing import Literal, Optional, Union

import click
import yaml
from dotenv import find_dotenv
from loguru import logger

from opensampl.config.base import BaseConfig as CLIConfig
from opensampl.db.orm import get_table_names
from opensampl.load_data import create_new_tables, write_to_table
from opensampl.vendors.constants import VENDORS

BANNER = r"""

                        ____    _    __  __ ____  _
  ___  _ __   ___ _ __ / ___|  / \  |  \/  |  _ \| |
 / _ \| '_ \ / _ \ '_ \\___ \ / _ \ | |\/| | |_) | |
| (_) | |_) |  __/ | | |___) / ___ \| |  | |  __/| |___
 \___/| .__/ \___|_| |_|____/_/   \_\_|  |_|_|   |_____|
      |_|
    tools for processing clock data
"""


def load_config(env_file: Optional[str] = None) -> CLIConfig:
    """
    Load the configuration settings

    Either from provided env_file, OPENSAMPL_ENV_FILE environment variable, or from the dotenv file found through
    loaddotenv's find_dotenv

    Args:
        env_file: str

    Returns:
        BaseSettings model

    """
    if not env_file:
        env_file = os.getenv("OPENSAMPL_ENV_FILE", None)

    if not env_file:
        dotenv_file = find_dotenv()
        env_file = dotenv_file
    else:
        env_file = str(Path(env_file).resolve())

    return CLIConfig(_env_file=env_file)


class CaseInsensitiveGroup(click.Group):
    """Defines Click group options as case-insensitive. By default, click groups are case-sensitive."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:  # noqa: ARG002
        """Normalize command name to lower case"""
        cmd_name = cmd_name.lower()
        # Match against lowercased command names
        for name, cmd in self.commands.items():
            if name.lower() == cmd_name:
                return cmd
        return None


@click.group()
@click.option("--env-file", type=click.Path(exists=True), help="Path to the file with configuration settings defined")
@click.pass_context
def cli(ctx: click.Context, env_file: str):
    """CLI utility for openSAMPL"""
    ctx.ensure_object(dict)
    conf = load_config(env_file)
    ctx.obj["conf"] = conf

    logger.configure(handlers=[{"sink": sys.stderr, "level": conf.LOG_LEVEL.upper()}])


@cli.command(name="init")
def init():
    """
    Initialize the database.

    Creates all tables as defined in the opensampl.db.orm file.
    This is not required if you are using `opensampl-server`, as that is done as part of that initialization of the db.
    """
    logger.debug("Initializing database")
    create_new_tables()


@cli.group()
@click.pass_context
def config(ctx: click.Context):
    """View and manage environment variables used by openSAMPL"""


@config.command()
@click.pass_context
def file(ctx: click.Context):
    """Show the path to the env file used by openSAMPL"""
    conf = ctx.obj["conf"]
    click.echo(conf.env_file)


@config.command()
@click.option("--explain", "-e", is_flag=True, help="Include descriptions of the variables")
@click.option("--var", "-v", help="Specify a single variable to display")
@click.pass_context
def show(ctx: click.Context, explain: bool, var: str):
    """
    Display current environment variable configurations.

    Examples
    --------
        opensampl config show  # Show all variables and their values
        opensampl config show --explain  # Show all variables with descriptions
        opensampl config show --var BACKEND_URL  # Show specific variable
        opensampl config show -e -v BACKEND_URL  # Show specific variable with description

    """
    conf = ctx.obj["conf"]
    logger.debug(f"loaded env_file: {conf.env_file}")
    if var:
        # Filter to specific variable if requested
        vars_to_show = [var] if conf.get_by_name(var) else None
        if not vars_to_show:
            click.echo(f"Error: Environment variable '{var}' not found", err=True)
            return
    else:
        vars_to_show = list(conf.model_fields.keys())

    from tabulate import tabulate

    # Create a list of dictionaries for the DataFrame
    data = []
    for env_var in vars_to_show:
        row = {
            "Variable": env_var,
            "Value": getattr(conf, env_var),
        }
        if explain:
            row.update({"Description": conf.model_fields.get(env_var).description})
        data.append(row)
    maxcolwidths = [None, None, 40] if explain else [None, None]
    click.echo(tabulate(data, headers="keys", tablefmt="simple", maxcolwidths=maxcolwidths))


@config.command("set")
@click.argument("name")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, name: str, value: str):
    """
    Set the value of an environment variable.

    Note that this will only work if the variable is set in the .env file, if it is a true environment variable the
    change will not persist.

    Examples
    --------
        opensampl config set BACKEND_URL http://localhost:8000

    """
    conf = ctx.obj["conf"]

    conf.set_by_name(name=name, value=value)


@cli.group(cls=CaseInsensitiveGroup)
def load():
    """Load data into database"""


for vendor in VENDORS.all():
    load.add_command(vendor.get_parser().get_cli_command(), name=vendor.name)


def path_or_string(value: str) -> Union[dict, list]:
    """Get content from a file or use the string directly"""
    # Get content - either from file or use the string directly
    content = value
    try:
        path = Path(value)
        if path.exists() and path.is_file():
            content = path.read_text()
    except Exception:  # noqa: S110
        # If any error occurs during path handling, treat as raw string
        pass

    # Try parsing as YAML
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as yaml_err:
        # If YAML parsing fails, try JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError as json_err:
            # If both parsing attempts fail, raise an error
            raise click.BadParameter(
                f"Could not parse input as YAML or JSON.\nYAML error: {yaml_err}\nJSON error: {json_err}"
            ) from json_err


@load.command("table")
@click.option(
    "--if-exists",
    "-i",
    type=click.Choice(["update", "error", "replace", "ignore"]),
    default="update",
    help="How to handle conflicts with existing entries",
)
@click.argument("table_name", type=click.Choice(get_table_names()))
@click.argument("filepath", type=path_or_string)
def table_load(
    filepath: Union[dict, list], table_name: str, if_exists: Literal["update", "error", "replace", "ignore"]
):
    r"""
    Perform a Table load into the database.

        Load data directly into a database table. Format can be yaml or json. Can be a list of dictionaries or a single
        dictionary.

        You do not have to specify schema, is assumed to be castdb.
    \n\n
        The --if-exists option controls how to handle conflicts:\n
            - update: Only update fields that are provided and non-default (default)\n
            - error: Raise an error if entry exists\n
            - replace: Replace all non-primary-key fields with new values\n
            - ignore: Skip if entry exists\n

        Example:\n
            cli.py table load locations data.json\n
            cli.py table load probe_metadata metadata.yaml\n
    """
    try:
        if isinstance(filepath, list):
            for row in filepath:
                write_to_table(table=table_name, data=row, if_exists=if_exists)
        else:
            write_to_table(table_name, filepath, if_exists=if_exists)
        click.echo(f"Successfully wrote data to table {table_name}")
    except Exception as e:
        click.echo(f"Error writing to table: {e!s}", err=True)
        raise click.Abort()  # noqa: RSE102,B904


@cli.command(name="create")
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--update-db",
    "-u",
    is_flag=True,
    help="Update the database with the new probe type",
)
def create_probe_command(config_path: Path, update_db: bool):
    """Create a new probe type with scaffolding, based on a config file."""
    from opensampl.create.create_vendor import VendorConfig

    vendor_config = VendorConfig.from_config_file(config_path)
    vendor_config.create()
    if update_db:
        create_new_tables()


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        logger.exception(f"Error: {e!s}")
        raise

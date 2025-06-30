"""
Define the command line interface for openSAMPL.

The openSAMPL CLI package is a click based command line interface for the openSAMPL package. It provides a way to
interact with the database and load data into it.
"""

import json
import sys
from pathlib import Path
from typing import Literal, Optional, Union

import click
import yaml
from dotenv import find_dotenv, load_dotenv
from loguru import logger

from opensampl.constants import ENV_VARS
from opensampl.db.orm import Base
from opensampl.helpers.config_manager import ConfigManager
from opensampl.helpers.env import set_env
from opensampl.load_data import create_new_tables, write_to_table
from opensampl.vendors.constants import VENDOR_MAP, get_vendor_parser

BANNER = r"""

                        ____    _    __  __ ____  _
  ___  _ __   ___ _ __ / ___|  / \  |  \/  |  _ \| |
 / _ \| '_ \ / _ \ '_ \\___ \ / _ \ | |\/| | |_) | |
| (_) | |_) |  __/ | | |___) / ___ \| |  | |  __/| |___
 \___/| .__/ \___|_| |_|____/_/   \_\_|  |_|_|   |_____|
      |_|
    tools for processing clock data
"""

env_file = find_dotenv()
load_dotenv()
level = str(ENV_VARS.LOG_LEVEL.get_value())
logger.configure(handlers=[{"sink": sys.stderr, "level": level.upper()}])


class CaseInsensitiveGroup(click.Group):
    """Defines Click group options as case-insensitive. By default, click groups are case-sensitive."""

    def get_command(self, ctx, cmd_name: str) -> Optional[click.Command]:  # noqa: ARG002,ANN001
        """Normalize command name to lower case"""
        cmd_name = cmd_name.lower()
        # Match against lowercased command names
        for name, cmd in self.commands.items():
            if name.lower() == cmd_name:
                return cmd
        return None


def get_table_names():
    """Get all table names from the ORM in opensampl.db.orm"""
    return [table.name for table in Base.metadata.sorted_tables]


@click.group()
def cli():
    """CLI utility for openSAMPL"""


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
def config():
    """View and manage environment variables used by openSAMPL"""


@config.command()
def file():
    """Show the path to the env file used by openSAMPL"""
    click.echo(env_file)


@config.command()
@click.option("--explain", "-e", is_flag=True, help="Include descriptions of the variables")
@click.option("--var", "-v", help="Specify a single variable to display")
def show(explain: bool, var: str):
    """
    Display current environment variable configurations.

    Examples
    --------
        opensampl config show  # Show all variables and their values
        opensampl config show --explain  # Show all variables with descriptions
        opensampl config show --var BACKEND_URL  # Show specific variable
        opensampl config show -e -v BACKEND_URL  # Show specific variable with description

    """
    logger.debug(f"loaded env_file: {env_file}")
    if var:
        # Filter to specific variable if requested
        vars_to_show = [v for v in ENV_VARS.all() if v.name == var]
        if not vars_to_show:
            click.echo(f"Error: Environment variable '{var}' not found", err=True)
            return
    else:
        vars_to_show = ENV_VARS.all()

    from tabulate import tabulate

    # Create a list of dictionaries for the DataFrame
    data = []
    for env_var in vars_to_show:
        row = {
            "Variable": env_var.name,
            "Value": str(env_var.get_value()),
        }
        if explain:
            row.update({"Description": env_var.description})
        data.append(row)
    maxcolwidths = [None, None, 40] if explain else [None, None]
    click.echo(tabulate(data, headers="keys", tablefmt="simple", maxcolwidths=maxcolwidths))


@config.command("set")
@click.argument("name")
@click.argument("value")
def config_set(name: str, value: str):
    """
    Set the value of an environment variable.

    Note that this will only work if the variable is set in the .env file, if it is a true environment variable the
    change will not persist.

    Examples
    --------
        opensampl config set BACKEND_URL http://localhost:8000

    """
    set_env(name=name, value=value)


@config.command("set-config")
@click.argument("name")
@click.argument("value")
def config_set_config(name: str, value: str):
    """
    Set a configuration value in the openSAMPL configuration file.

    This sets values in either $HOME/.config/opensampl/config or /etc/opensampl/config
    depending on which exists. User config takes precedence over system config.

    Examples
    --------
        opensampl config set-config SYSTEMD_SERVICE_NAME my-opensampl
        opensampl config set-config SYSTEMD_USER opensampl

    """
    config_manager = ConfigManager()
    config_manager.set_config_value(name, value)
    click.echo(f"Set {name}={value} in {config_manager.get_config_path()}")


@config.command("get-config")
@click.argument("name")
def config_get_config(name: str):
    """
    Get a configuration value from the openSAMPL configuration file.

    Examples
    --------
        opensampl config get-config SYSTEMD_SERVICE_NAME

    """
    config_manager = ConfigManager()
    value = config_manager.get_config_value(name)
    if value is not None:
        click.echo(value)
    else:
        click.echo(f"Configuration '{name}' not found", err=True)


@config.command("show-config")
def config_show_config():
    """
    Show all configuration values from the openSAMPL configuration file.

    Examples
    --------
        opensampl config show-config

    """
    config_manager = ConfigManager()
    config = config_manager.read_config()

    if not config:
        click.echo("No configuration found")
        return

    from tabulate import tabulate

    data = [{"Variable": key, "Value": value} for key, value in config.items()]
    click.echo(tabulate(data, headers="keys", tablefmt="simple"))


@cli.group(cls=CaseInsensitiveGroup)
def load():
    """Load data into database"""


for probe_name in VENDOR_MAP:
    load.add_command(get_vendor_parser(probe_name).get_cli_command(), name=probe_name)


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
    from opensampl.helpers.create_vendor import VendorConfig

    vendor_config = VendorConfig.from_config_file(config_path)
    vendor_config.create()
    if update_db:
        create_new_tables()


@cli.command()
@click.option(
    "--service-name",
    default="opensampl",
    help="Name for the systemd service",
)
@click.option(
    "--user",
    default="opensampl",
    help="User to run the systemd service as",
)
@click.option(
    "--working-directory",
    type=click.Path(path_type=Path),
    default="/opt/opensampl",
    help="Working directory for the systemd service",
)
@click.option(
    "--uninstall",
    is_flag=True,
    help="Uninstall the systemd service instead of installing it",
)
def register(service_name: str, user: str, working_directory: Path, uninstall: bool):
    """
    Register openSAMPL as a systemd service.

    This command creates and installs a systemd service for openSAMPL that will
    automatically start the server on boot. The service can be configured via
    configuration files in $HOME/.config/opensampl/ or /etc/opensampl/.

    Examples
    --------
        sudo opensampl register
        sudo opensampl register --service-name my-opensampl --user myuser
        sudo opensampl register --uninstall

    """
    config_manager = ConfigManager()

    if uninstall:
        if config_manager.uninstall_systemd_service(service_name):
            click.echo(f"Successfully uninstalled systemd service '{service_name}'")
        else:
            click.echo("Failed to uninstall systemd service", err=True)
            raise click.Abort()
    elif config_manager.install_systemd_service(service_name, user, working_directory):
        click.echo(f"Successfully registered systemd service '{service_name}'")
    else:
        click.echo("Failed to register systemd service", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()

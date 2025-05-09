"""CLI interface for openSAMPL-server"""

from __future__ import annotations

import importlib.resources as pkg_resources
import os
import shlex
import subprocess
import sys

import click
from dotenv import load_dotenv
from loguru import logger

from opensampl.helpers.env import set_env
from opensampl.server import check_command


def get_default_env():
    """Get the default env file's absolute path regardless of where opensampl-server call originates"""
    with pkg_resources.path("opensampl.server", "default.env") as path:
        return str(path)


BANNER = r"""
                        ____    _    __  __ ____  _
  ___  _ __   ___ _ __ / ___|  / \  |  \/  |  _ \| |
 / _ \| '_ \ / _ \ '_ \\___ \ / _ \ | |\/| | |_) | |
| (_) | |_) |  __/ | | |___) / ___ \| |  | |  __/| |___
 \___/| .__/ \___|_| |_|____/_/_ _\_\_|  |_|_|  _|_____|
      |_|            / __|/ _ | '__\ \ / / _ | '__|
                     \__ |  __| |   \ V |  __| |
                     |___/\___|_|    \_/ \___|_|
    tools for viewing and storing clock data
"""


def get_compose_command():
    """Detect the available docker-compose command."""
    if check_command(["docker-compose", "--version"]):
        return "docker-compose"
    if check_command(["docker", "compose", "--version"]):
        return "docker compose"
    raise ImportError("Neither 'docker compose' nor 'docker-compose' is installed. Please install Docker Compose.")


def get_cast_compose_file():
    """Get the fully qualified path to the docker-compose.yaml file included inside the package."""
    try:
        filename = "docker-compose.yaml"
        with pkg_resources.path("opensampl.server", filename) as path:
            return str(path)
    except ImportError:
        click.echo("Error: docker-compose.yaml file not found in package.", error=True)
        sys.exit(1)


def build_docker_compose_base(env_file: click.Path | str) -> list:
    """Build the docker compose command, including env file and compose file"""
    compose_command = get_compose_command()
    compose_file = get_cast_compose_file()
    command = shlex.split(compose_command)
    command.extend(["--env-file", env_file, "-f", compose_file])
    return command


@click.group()
def cli():
    """Command line interface for the opensampl server."""


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, readable=True),
    default=get_default_env(),
    help="Path to the .env file to use.",
)
@click.argument("extra_args", nargs=-1)
def up(env_file: click.Path | str, extra_args: list):
    """Start the opensampl server. Configures the local environment to use the backend"""
    load_dotenv(env_file)

    command = build_docker_compose_base(env_file)
    command.extend(["up", "-d"])

    if extra_args:
        command.extend(extra_args)

    logger.debug(f"Running: {command}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603

    for line in process.stdout:
        print(line, end="")  # noqa: T201 Print each line as it arrives

    process.wait()

    set_env(name="BACKEND_URL", value="http://localhost:8015")
    set_env(name="ROUTE_TO_BACKEND", value="true")
    set_env(
        name="DATABASE_URL",
        value=f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@localhost:5415/{os.getenv('POSTGRES_DB')}",
    )
    if os.getenv("USE_API_KEY", "false") == "true":
        set_env(name="API_KEY", value=os.getenv("API_KEYS", "").split(",")[0].strip())

    click.echo('See grafana interface at "http://localhost:3015"')


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, readable=True),
    default=get_default_env(),
    help="Path to the .env file to use.",
)
@click.argument("extra_args", nargs=-1)
def down(env_file: click.Path, extra_args: list) -> None:
    """Stop the opensampl server."""
    command = build_docker_compose_base(env_file)
    command.extend(["down"])
    if extra_args:
        command.extend(extra_args)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603

    for line in process.stdout:
        print(line, end="")  # noqa: T201 Print each line as it arrives

    process.wait()


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, readable=True),
    default=get_default_env(),
    help="Path to the .env file to use.",
)
def logs(env_file: click.Path) -> None:
    """Show the logs from the opensampl server."""
    command = build_docker_compose_base(env_file)
    command.extend(["logs", "-f"])
    subprocess.run(command, check=True)  # noqa: S603


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, readable=True),
    default=get_default_env(),
    help="Path to the .env file to use.",
)
def ps(env_file: click.Path) -> None:
    """Docker compose ps of the opensampl server"""
    command = build_docker_compose_base(env_file)
    command.extend(["ps"])
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603

    for line in process.stdout:
        print(line, end="")  # noqa: T201 Print each line as it arrives

    process.wait()


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, readable=True),
    default=get_default_env(),
    help="Path to the .env file to use.",
)
@click.argument("run-commands", nargs=-1)
def run(env_file: click.Path, run_commands: list) -> None:
    """Run command: add anything you would after docker compose run"""
    command = build_docker_compose_base(env_file)
    logger.info(run_commands)
    command.extend(["run", "--rm"])
    command.extend(list(run_commands))
    logger.info(command)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603

    for line in process.stdout:
        print(line, end="")  # noqa: T201  Print each line as it arrives

    process.wait()


if __name__ == "__main__":
    cli()

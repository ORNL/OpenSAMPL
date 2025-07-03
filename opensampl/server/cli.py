"""CLI interface for openSAMPL-server"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TextIO, cast

import click
from dotenv import find_dotenv
from loguru import logger

from opensampl.config.server import ServerConfig


def load_config(env_file: str | None = None) -> ServerConfig:
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

    return ServerConfig(_env_file=env_file)  # ty: ignore[unknown-argument]


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


@click.group()
@click.option(
    "--env-file", type=click.Path(exists=True), help="Path to the file with cli configuration settings defined"
)
@click.pass_context
def cli(ctx: click.Context, env_file: str):
    """Command line interface for the opensampl server."""
    ctx.ensure_object(dict)
    conf = load_config(env_file)
    ctx.obj["conf"] = conf

    logger.configure(handlers=[{"sink": sys.stderr, "level": conf.LOG_LEVEL.upper()}])


@cli.command()
@click.pass_context
@click.argument("extra_args", nargs=-1)
def up(ctx: click.Context, extra_args: list):
    """Start the opensampl server. Configures the local environment to use the backend"""
    config = ctx.obj["conf"]

    config.BACKEND_URL = "http://localhost:8015"
    config.ROUTE_TO_BACKEND = True
    config.DATABASE_URL = config.get_db_url()
    if str(config.docker_env_values.get("USE_API_KEY", "false")).lower == "true":
        config.API_KEY = config.docker_env_values.get("API_KEYS", "").split(",")[0].strip()

    command = config.build_docker_compose_base()
    command.extend(["up", "-d"])

    if extra_args:
        command.extend(extra_args)

    logger.debug(f"Running: {command}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603
    stdout = cast("TextIO", process.stdout)
    if stdout:
        for line in stdout:
            print(line, end="")  # noqa: T201 Print each line as it arrives
    process.wait()

    config.save_config()

    if not extra_args or "grafana" in extra_args:
        click.echo('See grafana interface at "http://localhost:3015"')


@cli.command()
@click.pass_context
@click.argument("extra_args", nargs=-1)
def down(ctx: click.Context, extra_args: list) -> None:
    """Stop the opensampl server."""
    config = ctx.obj["conf"]
    command = config.build_docker_compose_base()
    command.extend(["down"])
    if extra_args:
        command.extend(extra_args)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603
    stdout = cast("TextIO", process.stdout)
    if stdout:
        for line in stdout:
            print(line, end="")  # noqa: T201 Print each line as it arrives

    process.wait()


@cli.command()
@click.pass_context
def logs(ctx: click.Context) -> None:
    """Show the logs from the opensampl server."""
    config = ctx.obj["conf"]
    command = config.build_docker_compose_base()
    command.extend(["logs", "-f"])
    subprocess.run(command, check=True)  # noqa: S603


@cli.command()
@click.pass_context
def ps(ctx: click.Context) -> None:
    """Docker compose ps of the opensampl server"""
    config = ctx.obj["conf"]
    command = config.build_docker_compose_base()
    click.echo(command)
    command.extend(["ps"])
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603
    stdout = cast("TextIO", process.stdout)
    if stdout:
        for line in stdout:
            print(line, end="")  # noqa: T201 Print each line as it arrives
    process.wait()


@cli.command()
@click.pass_context
@click.argument("run-commands", nargs=-1)
def run(ctx: click.Context, run_commands: list) -> None:
    """Run command: add anything you would after docker compose run"""
    config = ctx.obj["conf"]
    command = config.build_docker_compose_base()
    logger.info(run_commands)
    command.extend(["run", "--rm"])
    command.extend(list(run_commands))
    logger.info(command)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603
    stdout = cast("TextIO", process.stdout)
    if stdout:
        for line in stdout:
            print(line, end="")  # noqa: T201  Print each line as it arrives

    process.wait()


if __name__ == "__main__":
    cli()

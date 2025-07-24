"""
CLI version 2 interface for openSAMPL-server

This script provides a CLI interface using Click for openSAMPL-server which is a wrapper around
docker compose commands. It provides the correct docker-compose.yaml file and needed .env file for all of the
standard docker-compose commands.
"""

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
 / _ \| '_ \ / _ \ '_ \___ \ / _ \ | |\/| | |_) | |
| (_) | |_) |  __/ | | |___) / ___ \| |  | |  __/| |___
 \___/| .__/ \___|_| |_|____/_/_ _\_\_|  |_|_|  _|_____|
      |_|            / __|/ _ | '__\ \ / / _ | '__|
                     \__ |  __| |   \ V |  __| |
                     |___/\___|_|    \_/ \___|_|
    tools for viewing and storing clock data
"""


@click.command(context_settings={"ignore_unknown_options": True})
@click.option(
    "--env-file", type=click.Path(exists=True), help="Path to the file with cli configuration settings defined"
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def cli(env_file: str, args: tuple):
    """
    Command line interface for the opensampl server.

    If you wish to skip this help, and get direct docker compose help instead, run as opensampl-server2 -- {commands};
    for example: opensampl-server2 -- --help to get the docker compose help text
    """
    conf = load_config(env_file)
    logger.configure(handlers=[{"sink": sys.stderr, "level": conf.LOG_LEVEL.upper()}])

    # Build and execute the docker compose command
    command = conf.build_docker_compose_base()
    if args:
        command.extend(args)

    logger.debug(f"Running: {command}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603
    stdout = cast("TextIO", process.stdout)
    if stdout:
        for line in stdout:
            print(line, end="")  # noqa: T201 Print each line as it arrives
    process.wait()

    # Post-command actions
    if args and args[0] == "up":
        if "grafana" in args or len(args) == 1:
            click.echo('See grafana interface at "http://localhost:3015"')
            # Special handling for 'up' command
        if "backend" in args or len(args) == 1:
            conf.BACKEND_URL = "http://localhost:8015"
            conf.ROUTE_TO_BACKEND = True
            conf.DATABASE_URL = conf.get_db_url()
            if str(conf.docker_env_values.get("USE_API_KEY", "false")).lower == "true":
                conf.API_KEY = conf.docker_env_values.get("API_KEYS", "").split(",")[0].strip()

            conf.save_config()


if __name__ == "__main__":
    cli()

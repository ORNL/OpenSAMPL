"""
Pydantic BaseSettings Object used to access and set the openSAMPL-server configuration options.

This module provides the main configuration class for openSAMPL-server, handling environment variables,
configuration validation, and settings management.
"""

import shlex
from importlib.resources import as_file, files
from pathlib import Path
from types import ModuleType
from typing import Any, Union

from dotenv import dotenv_values, set_key
from loguru import logger
from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

import opensampl.server
from opensampl.config.base import BaseConfig
from opensampl.server import check_command


def get_resolved_resource_path(pkg: Union[str, ModuleType], relative_path: str) -> str:
    """Retrieve the resolved path to a resource in a package."""
    resource = files(pkg).joinpath(relative_path)
    with as_file(resource) as real_path:
        return str(real_path.resolve())


class ServerConfig(BaseConfig):
    """Configuration specific to server-side CLI operations."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="OPENSAMPL_SERVER__")

    COMPOSE_FILE: str = Field(default="", description="Fully resolved path to the Docker Compose file.")

    DOCKER_ENV_FILE: str = Field(default="", description="Fully resolved path to the Docker .env file.")

    docker_env_values: dict[str, Any] = Field(default_factory=dict, init=False)

    @property
    def _ignore_in_set(self) -> list[str]:
        """The fields to ignore when setting the configuration."""
        ignored = super()._ignore_in_set.copy()
        ignored.extend(["docker_env_values"])

        # Don't save compose file or docker env file if using defaults
        if get_resolved_resource_path(opensampl.server, "docker-compose.yaml") == self.COMPOSE_FILE:
            ignored.append("COMPOSE_FILE")
        if get_resolved_resource_path(opensampl.server, "default.env") == self.DOCKER_ENV_FILE:
            ignored.append("DOCKER_ENV_FILE")

        return ignored

    @model_validator(mode="after")
    def get_docker_values(self) -> "ServerConfig":
        """Get the values that the docker containers will use on startup"""
        self.docker_env_values = dotenv_values(self.DOCKER_ENV_FILE)
        return self

    @field_validator("COMPOSE_FILE", mode="before")
    @classmethod
    def resolve_compose_file(cls, v: Any) -> str:
        """Resolve the provided compose file for docker to use, or default to the docker-compose.yaml provided"""
        if v == "":
            return get_resolved_resource_path(opensampl.server, "docker-compose.yaml")
        return str(Path(v).expanduser().resolve())

    @field_validator("DOCKER_ENV_FILE", mode="before")
    @classmethod
    def resolve_docker_env_file(cls, v: Any) -> str:
        """Resolve the provided env file for docker containers to use, or default to the default.env provided"""
        if v == "":
            return get_resolved_resource_path(opensampl.server, "default.env")
        return str(Path(v).expanduser().resolve())

    @staticmethod
    def get_compose_command() -> str:
        """Detect the available docker-compose command."""
        if check_command(["docker-compose", "--version"]):
            return "docker-compose"
        if check_command(["docker", "compose", "--version"]):
            return "docker compose"
        raise ImportError("Neither 'docker compose' nor 'docker-compose' is installed. Please install Docker Compose.")

    def build_docker_compose_base(self):
        """Build the docker compose command, including env file and compose file"""
        compose_command = self.get_compose_command()
        command = shlex.split(compose_command)
        command.extend(["--env-file", self.DOCKER_ENV_FILE, "-f", self.COMPOSE_FILE])
        return command

    def set_by_name(self, name: str, value: Any):
        """
        Set setting's value in the env file for current instance.

        Uses env_prefix for ServerConfig-specific fields, base name for inherited fields.
        """
        setting = self.get_by_name(name)
        if setting is None:
            raise ValueError(f"Setting {name} not found")

        # Check if this field is defined in ServerConfig vs inherited from BaseConfig
        server_fields = set(ServerConfig.model_fields.keys()) - set(BaseConfig.model_fields.keys())
        env_key = f"{self.model_config.get('env_prefix', '')}{name}" if name in server_fields else name

        if not self.env_file.is_file():
            logger.info("Env file does not exist. Creating one to save setting.")
            self.env_file.touch()

        set_key(self.env_file, env_key, str(value))

    def get_db_url(self):
        """Return the database URL for the Timescale db that will be created with the docker-compose environment."""
        user = self.docker_env_values.get("POSTGRES_USER")
        password = self.docker_env_values.get("POSTGRES_PASSWORD")
        db = self.docker_env_values.get("POSTGRES_DB")
        if all(x is not None for x in [user, password, db]):
            return f"postgresql://{user}:{password}@localhost:5415/{db}"
        raise ValueError("Database environment variables POSTGRES_USER, POSTGRES_PASSWORD, or POSTGRES_DB are not set.")

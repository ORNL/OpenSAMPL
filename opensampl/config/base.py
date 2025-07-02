"""
Pydantic BaseSettings Object used to access and set the openSAMPL configuration options.

This module provides the main configuration class for openSAMPL, handling environment variables,
configuration validation, and settings management.
"""

from pathlib import Path
from typing import Any, Optional

from dotenv import set_key
from loguru import logger
from pydantic import Field, field_serializer
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    """
    Primary configuration settings for the opensampl cli.

    Handles all configuration options including routing, database connections,
    logging, and API access settings.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_nested_delimiter="__")
    env_file: Path = Field(description="Path to the env file to get variables from.")

    ROUTE_TO_BACKEND: bool = Field(
        False, description="URL of the backend service when routing is enabled", alias="ROUTE_TO_BACKEND"
    )
    BACKEND_URL: Optional[str] = Field(
        None, description="URL of the backend service when routing is enabled", alias="BACKEND_URL"
    )
    DATABASE_URL: Optional[str] = Field(None, description="URL for direct database connections", alias="DATABASE_URL")
    ARCHIVE_PATH: Path = Field(
        Path("archive"),
        description="Default path that files are moved to after they have been processed",
        alias="ARCHIVE_PATH",
    )
    LOG_LEVEL: str = Field("INFO", description="Log level for opensampl cli", alias="LOG_LEVEL")
    API_KEY: Optional[str] = Field(None, description="Access key for interacting with the backend", alias="API_KEY")
    INSECURE_REQUESTS: bool = Field(
        False, description="Allow insecure requests to be made to the backend", alias="INSECURE_REQUESTS"
    )

    @field_serializer("ARCHIVE_PATH")
    def convert_to_str(self, v: Path) -> str:
        """Convert archive path to a string for serialization"""
        return str(v.resolve())

    @property
    def _ignore_in_set(self) -> list[str]:
        """The fields to ignore when setting the configuration."""
        return ["env_file"]

    def __init__(self, **kwargs: Any):
        """
        Record the env file set in object creation before proceeding to super().__init__.

        Required because the default pydantic-settings behavior is not to store the filepath in the object.

        Args:
            **kwargs: Keyword arguments including env_file path configuration.

        """
        _env_file = kwargs.get("_env_file")
        env_file = kwargs.get("env_file")
        if _env_file:
            resolved_env_file = Path(_env_file)
        elif env_file is not None:
            resolved_env_file = Path(env_file)
            kwargs["_env_file"] = env_file
        else:
            fallback = self.model_config.get("env_file")
            resolved_env_file = Path(fallback) if fallback else None
        kwargs["env_file"] = resolved_env_file
        super().__init__(**kwargs)

    def get_by_name(self, name: str):
        """
        Return the field info object for the given model.

        Args:
            name: Name of the configuration field.

        Returns:
            Field info object if found, None otherwise.

        """
        return self.model_fields.get(name, None)

    def set_by_name(self, name: str, value: Any):
        """
        Set setting's value in the env file for current instance.

        Args:
            name: Name of the configuration setting.
            value: Value to set for the setting.

        Raises:
            ValueError: If the setting name is not found.

        """
        setting = self.get_by_name(name)
        if setting is None:
            raise ValueError(f"Setting {name} not found")

        if not self.env_file.is_file():
            logger.info("Env file does not exist. Creating one to save setting.")
            self.env_file.touch()

        set_key(self.env_file, name, str(value))

    def save_config(self, values: Optional[list[str]] = None):
        """
        Save the current env configuration.

        If values are provided, it will only encode the ones listed.
        Otherwise, will save all of them.

        Args:
            values: Optional list of setting names to save. If None, saves all settings.

        """
        if values is None:
            values_dict = self.model_dump(exclude=set(self._ignore_in_set))
        else:
            values_dict = self.model_dump(include=set(values))
        logger.debug(f"setting the following variables in env: {values_dict}")
        for key, val in values_dict.items():
            self.set_by_name(name=key, value=val)

    def check_routing_dependencies(self) -> "BaseConfig":
        """
        Ensure required URL (backend or database) is configured for routing option.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If required URLs are not configured for the current routing option.

        """
        if self.ROUTE_TO_BACKEND and not self.BACKEND_URL:
            raise ValueError("BACKEND_URL must be set if ROUTE_TO_BACKEND is True")
        if not self.ROUTE_TO_BACKEND and not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set if ROUTE_TO_BACKEND is False")
        return self

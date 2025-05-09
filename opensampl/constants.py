"""Constants for accessing environment configurations"""

import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel


class EnvVar(BaseModel):
    """Defines an environment variable and its properties"""

    name: str
    description: str
    type: type = str
    default: Optional[Any] = None

    def get_value(self):
        """Get value of var in environment"""
        default = self.resolve_default()
        if self.type is bool:
            return os.getenv(self.name, default).lower() == "true"
        if self.type is Path:
            return Path(os.getenv(self.name, default))
        return os.getenv(self.name, default)

    def resolve_default(self):
        """Resolve default value for env var based on type"""
        if self.type is bool:
            return self.default or "false"
        if self.type is Path and self.default is not None:
            return Path(self.default).resolve()
        return self.default


class ENV_VARS:  # noqa: N801
    """Variables referenced by openSAMPL"""

    ROUTE_TO_BACKEND = EnvVar(
        name="ROUTE_TO_BACKEND",
        description=(
            "Route all database operations through BACKEND_URL rather than applying directly using DATABASE_URL"
        ),
        type=bool,
    )
    BACKEND_URL = EnvVar(
        name="BACKEND_URL",
        description="URL of the backend service when routing is enabled",
    )
    DATABASE_URL = EnvVar(
        name="DATABASE_URL",
        description="URL for direct database connections",
    )
    ARCHIVE_PATH = EnvVar(
        name="ARCHIVE_PATH",
        description="Default path that files are moved to after they have been processed",
        type=Path,
        default="archive",
    )
    LOG_LEVEL = EnvVar(
        name="LOG_LEVEL",
        description="Log level for opensampl cli",
        default="INFO",
    )
    API_KEY = EnvVar(
        name="API_KEY",
        description="Access key for interacting with the backend",
    )

    @classmethod
    def __iter__(cls) -> iter:
        """Get all EnvVar objects as iterable"""
        yield from (value for key, value in cls.__dict__.items() if isinstance(value, EnvVar))

    @classmethod
    def get(cls, name: str) -> Optional[Any]:
        """Get EnvVar object by name"""
        var = getattr(cls, name, None)
        if isinstance(var, EnvVar):
            return var.get_value()
        return os.getenv(name)

    @classmethod
    def all(cls) -> list[EnvVar]:
        """Get all EnvVar objects as list"""
        return [value for key, value in cls.__dict__.items() if isinstance(value, EnvVar)]

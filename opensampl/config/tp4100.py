"""
Pydantic BaseSettings Management for the Microchip TP4100 connections.

Managed through environment in order to keep password as secure as possible.
"""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TP4100Config(BaseSettings):
    """
    Configuration settings for the Microchip TP4100 Connections

    Handles grabbing the details from the environment (or .env file), all prefixed with TP4100__
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="TP4100__")

    # TP4100 device connection settings
    HOST: str = Field(..., description="IP address or hostname of the TP4100 device")
    PORT: int = Field(443, description="HTTPS port for TP4100 web interface")
    USERNAME: str = Field(
        "admin", description=("Username for TP4100 login; Default is factory default according to user manual")
    )
    PASSWORD: str = Field(
        "Microchip", description=("Password for TP4100 login; Default is factory default according to user manual")
    )

    url: str = Field(default="", init=False)

    @model_validator(mode="after")
    def create_url(self):
        """Create https url for TP4100 Configuration"""
        self.url = f"https://{self.HOST}:{self.PORT}"
        return self

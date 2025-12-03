"""
Context reader for Microchip TWST ATS6502 modems.

This module provides functionality to read context information from ATS6502 modems,
including local and remote station information.
"""

import re
import textwrap
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional

import yaml
from loguru import logger

from opensampl.collect.modem import ModemReader, require_conn
from opensampl.collect.microchip.twst.context import ModemContextReader as TWSTModemContextReader

class ModemContextReader(TWSTModemContextReader):
    """
    Reader for ATS6580A modem context information.

    Provides methods to connect to an ATS6580A modem and retrieve context information
    """

    def __init__(self, host: str, prompt: str = "ATS-6580A-A2G1R>", port: int = 1700):
        """
        Initialize ModemContextReader.

        Args:
            host: IP address or hostname of the ATS6580A modem.
            prompt: Command prompt string expected from the modem.
            port: what port to connect to for commands (default 1700).

        """
        super().__init__(host=host, prompt=prompt, port=port)


    async def get_context(self):
        """
        Retrieve context information from the modem.

        Connects to the modem and retrieves local station information
        and remote station tracking data.
        """
        async with self.connect():
            self.result.timestamp = datetime.now(tz=timezone.utc).isoformat() + "Z"
            self.result.position = SimpleNamespace()

            show_result = await self.send_cmd("show")

            self.result.ip = show_result.get("network").get("static").get("ip")
            self.result.position.lat = (
                show_result.get("status").get("gps").get("position").get("lat")
            )
            self.result.position.lon = (
                show_result.get("status").get("gps").get("position").get("lon")
            )
            self.result.position.alt = (
                show_result.get("status").get("gps").get("position").get("alt")
            )
            self.result.serial_number = show_result.get("status").get("unit").get("serial_number")
            self.result.model = show_result.get("status").get("unit").get("model")
            self.result.start = show_result.get("status").get("unit").get("start")


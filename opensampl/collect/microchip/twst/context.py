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


class ModemContextReader(ModemReader):
    """
    Reader for ATS6502 modem context information.

    Provides methods to connect to an ATS6502 modem and retrieve context information
    including local station details and remote station tracking data.
    """

    def __init__(self, host: str, prompt: str = "ATS 6502>"):
        """
        Initialize ModemContextReader.

        Args:
            host: IP address or hostname of the ATS6502 modem.
            prompt: Command prompt string expected from the modem.

        """
        self.result = SimpleNamespace()
        self.prompt = prompt
        super().__init__(host=host, port=1700)

    @staticmethod
    def finished_ok(line: str) -> bool:
        """
        Check if a command completed successfully.

        Args:
            line: Response line from the modem.

        Returns:
            True if the line indicates successful completion.

        """
        return re.match(r"^\[OK\]", line) is not None

    @staticmethod
    def finished_error(line: str) -> tuple[bool, Optional[str]]:
        """
        Check if a command completed with an error.

        Args:
            line: Response line from the modem.

        Returns:
            Tuple of (is_error, error_message).

        """
        error = re.match(r"^\[ERROR\]", line) is not None
        if error:
            return error, line
        return error, None

    def bracket_to_dict(self, raw_text: str):
        """
        Convert bracketed text format to dictionary.

        Args:
            raw_text: Raw text with [SECTION] headers.

        Returns:
            Dictionary representation of the structured data.

        """
        yaml_unbrack = re.sub(
            r"^\s*\[(\w+)\]",
            lambda m: m.group(0).replace(f"[{m.group(1)}]", f"{m.group(1)}:"),
            raw_text,
            flags=re.MULTILINE,
        )
        yaml_ready = textwrap.dedent(yaml_unbrack)
        return yaml.safe_load(yaml_ready)

    @require_conn
    async def send_cmd(self, cmd: str):
        """
        Send a command to the modem and return parsed response.

        Args:
            cmd: Command string to send.

        Returns:
            Dictionary containing the parsed response.

        """
        logger.debug(f"Sending command {cmd=}")

        self.writer.write(cmd + "\n")
        await self.writer.drain()
        response = await self.read_until_exit()

        return self.bracket_to_dict(response)

    @require_conn
    async def read_until_exit(self):
        """
        Read response lines until completion or error.

        Returns:
            Accumulated response text.

        Raises:
            RuntimeError: If an error response is received.

        """
        buffer = ""
        while True:
            chunk = await self.reader.readline()  # read one line at a time
            logger.trace(chunk)  # live print

            if self.finished_ok(chunk):
                break
            err, msg = self.finished_error(chunk)
            if err:
                raise RuntimeError(msg)
            if self.prompt not in chunk:
                buffer += chunk

        return buffer

    async def get_context(self):
        """
        Retrieve context information from the modem.

        Connects to the modem and retrieves local station information
        and remote station tracking data.
        """
        async with self.connect():
            self.result.timestamp = datetime.now(tz=timezone.utc).isoformat() + "Z"
            self.result.local = SimpleNamespace()
            self.result.remotes = {}

            show_result = await self.send_cmd("show")

            self.result.local.sid = show_result.get("settings").get("modem").get("sid")
            self.result.local.prn = show_result.get("status").get("modem").get("tx").get("prn")
            self.result.local.ip = show_result.get("network").get("static").get("ip")
            self.result.local.lat = (
                show_result.get("status").get("modem").get("position").get("station").get("latitude")
            )
            self.result.local.lon = (
                show_result.get("status").get("modem").get("position").get("station").get("longitude")
            )

            rx_status = show_result.get("status").get("modem").get("rx").get("chan")
            for chan_num, block in rx_status.items():
                sid = block.get("remote").get("sid")
                prn = block.get("tracking").get("prn")
                lat = block.get("remote").get("position").get("station").get("latitude")
                lon = block.get("remote").get("position").get("station").get("longitude")

                if not sid:
                    continue

                self.result.remotes[chan_num] = {"rx_channel": chan_num, "sid": sid, "prn": prn, "lat": lat, "lon": lon}

    def get_result_as_yaml_comment(self):
        """
        Get results formatted as YAML comments.

        Returns:
            String containing results formatted as commented YAML.

        """
        yaml_text = yaml.dump(self.result_dict(), sort_keys=False)
        return textwrap.indent(yaml_text, prefix="# ")

    def result_dict(self):
        """
        Convert result SimpleNamespace to dictionary.

        Returns:
            Dictionary representation of the results.

        """

        def namespace_to_dict(ns: Any) -> Any:
            if isinstance(ns, SimpleNamespace):
                return {key: namespace_to_dict(value) for key, value in vars(ns).items()}
            if isinstance(ns, list):
                return [namespace_to_dict(item) for item in ns]
            if isinstance(ns, dict):
                return {key: namespace_to_dict(value) for key, value in ns.items()}
            return ns

        return namespace_to_dict(self.result)

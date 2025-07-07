"""
Base modem connection functionality

This module provides the base ModemReader class and connection management
for interfacing with modems via telnet.
"""

from contextlib import asynccontextmanager
from functools import wraps
from typing import Callable, Optional

from loguru import logger

try:
    import telnetlib3
except ImportError:
    import sys

    logger.warning("Collect extra must be installed in order to use Modem data collection functionality.")
    sys.exit(1)


def require_conn(method: Callable):
    """
    Ensure telnet connection is active before method execution.

    Args:
        method: Method to wrap with connection requirement.

    Returns:
        Wrapped method that checks for active connection.

    Raises:
        RuntimeError: If no active telnet connection exists.

    """

    @wraps(method)
    async def wrapper(self: "ModemReader", *args: list, **kwargs: dict) -> Optional[Callable]:
        if not getattr(self, "open", False):
            raise RuntimeError(
                "Telnet connection not active: reader/writer cannot be used outside of 'async with connect()'"
            )
        return await method(self, *args, **kwargs)

    return wrapper


class ModemReader:
    """
    Base class for reading from modems via telnet.

    Provides connection management and basic telnet functionality for
    communicating with modems.
    """

    def __init__(
        self,
        host: str,
        port: int,
        encoding: str = "utf8",
    ):
        """
        Initialize ModemReader.

        Args:
            host: IP address or hostname of the modem.
            port: Port number for telnet connection.
            encoding: Character encoding for the connection.

        """
        self.host = host
        self.port = port
        self.encoding = encoding
        self.reader: Optional[telnetlib3.TelnetReader] = None
        self.writer: Optional[telnetlib3.TelnetWriter] = None
        self.open: bool = False

    @asynccontextmanager
    async def connect(self):
        """
        Async context manager for telnet connection.

        Establishes telnet connection and ensures proper cleanup.

        Yields:
            Self with active connection.

        """
        reader, writer = await telnetlib3.open_connection(self.host, self.port, encoding=self.encoding)
        logger.debug(f"Connected at {self.host}:{self.port}")
        self.open = True
        self.reader = reader
        self.writer = writer
        try:
            yield self
        finally:
            self.writer.close()
            self.writer = None
            self.reader = None
            self.open = False

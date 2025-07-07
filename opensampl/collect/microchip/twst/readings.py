"""
Status and readings collector for Microchip TWST ATS6502 modems.

This module provides functionality to collect status readings and measurements
from ATS6502 modems over time.
"""

import asyncio
from typing import Optional

from opensampl.collect.modem import ModemReader, require_conn


class ModemStatusReader(ModemReader):
    """
    Reader for collecting status readings from ATS6502 modems.

    Provides functionality to connect to an ATS6502 modem and collect
    status readings over a specified duration.
    """

    def __init__(self, host: str, duration: int = 60, keys: Optional[list[str]] = None):
        """
        Initialize ModemStatusReader.

        Args:
            host: IP address or hostname of the ATS6502 modem.
            duration: Duration in seconds to collect readings.
            keys: List of key suffixes to filter readings (default: ["meas:offset"]).

        """
        self.duration = duration
        self.keys = keys or ["meas:offset"]
        self.queue = asyncio.Queue()
        self.readings = []
        super().__init__(host=host, port=1900)

    @require_conn
    async def reader_task(self):
        """
        Task to continuously read lines from the modem.

        Reads lines from the telnet connection and queues them for processing.
        """
        while True:
            line = await self.reader.readline()
            if line:
                await self.queue.put(line)

    def parse_line(self, line: str):
        """
        Parse a line of modem output.

        Args:
            line: Raw line from modem output.

        Returns:
            Tuple of (timestamp, definition, value) if parsing succeeds, None otherwise.

        """
        try:
            timestamp, reading = line.strip().split(" ", 1)
            definition, value = reading.split("=")
        except ValueError:
            return None
        else:
            return timestamp, definition, value

    def should_keep(self, definition: str) -> bool:
        """
        Determine if a reading should be kept based on its definition.

        Args:
            definition: Reading definition string.

        Returns:
            True if the reading matches any of the configured key suffixes.

        """
        return any(definition.endswith(suffix) for suffix in self.keys)

    async def processor_task(self):
        """
        Task to process queued lines and filter readings.

        Processes lines from the queue, parses them, and stores relevant readings.
        """
        while True:
            line = await self.queue.get()
            parsed = self.parse_line(line)
            if parsed:
                timestamp, definition, value = parsed
                if self.should_keep(definition):
                    self.readings.append(parsed)

    async def collect_readings(self):
        """
        Collect readings from the modem for the specified duration.

        Starts reader and processor tasks, collects data for the configured
        duration, then cancels the tasks.
        """
        async with self.connect():
            read_coroutine = asyncio.create_task(self.reader_task())
            process_coroutine = asyncio.create_task(self.processor_task())

            try:
                await asyncio.sleep(self.duration)
            finally:
                read_coroutine.cancel()
                process_coroutine.cancel()

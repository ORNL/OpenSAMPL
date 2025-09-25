"""
Status and readings collector for Microchip TWST ATS6502 modems.

This module provides functionality to collect status readings and measurements
from ATS6502 modems over time.
"""

import asyncio
from typing import Optional

from loguru import logger

from opensampl.collect.modem import ModemReader, require_conn

SENTINEL = b"--openSAMPL stop reading--"  # type: ignore[assignment]


class ModemStatusReader(ModemReader):
    """
    Reader for collecting status readings from ATS6502 modems.

    Provides functionality to connect to an ATS6502 modem and collect
    status readings over a specified duration.
    """

    def __init__(self, host: str, duration: int = 60, keys: Optional[list[str]] = None, port: int = 1900):
        """
        Initialize ModemStatusReader.

        Args:
            host: IP address or hostname of the ATS6502 modem.
            duration: Duration in seconds to collect readings.
            keys: List of key suffixes to filter readings (default: None for all readings).
            port: what port to connect to for status readings (default 1900).

        """
        self.duration = duration
        self.keys = keys
        self.queue = asyncio.Queue()
        self.readings = []
        self.continue_reading = False
        super().__init__(host=host, port=port)

    @require_conn
    async def reader_task(self):
        """
        Task to continuously read lines from the modem.

        Reads lines from the telnet connection and queues them for processing.
        """
        try:
            while self.continue_reading:
                line = await asyncio.wait_for(self.reader.readline(), timeout=5.0)
                if not line:
                    break  # EOF
                await self.queue.put(line)
        except asyncio.TimeoutError:
            logger.debug(f"Timeout waiting for data from {self.host}:{self.port}")
        finally:
            await self.queue.put(SENTINEL)

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
            True if the reading matches any of the configured key suffixes

        """
        if self.keys is None:
            return True  # Collect all readings when no keys specified
        return any(definition.endswith(suffix) for suffix in self.keys)

    async def processor_task(self):
        """
        Task to process queued lines and filter readings.

        Processes lines from the queue, parses them, and stores relevant readings.
        """
        while True:
            line = await self.queue.get()
            try:
                if line == SENTINEL:
                    break
                parsed = self.parse_line(line)
                if parsed:
                    timestamp, definition, value = parsed
                    if self.should_keep(definition):
                        self.readings.append(parsed)
            finally:
                self.queue.task_done()

    async def collect_readings(self):
        """
        Collect readings from the modem for the specified duration.

        Starts reader and processor tasks, collects data for the configured
        duration, then cancels the tasks.
        """
        async with self.connect():
            self.continue_reading = True
            read_coroutine = asyncio.create_task(self.reader_task())
            process_coroutine = asyncio.create_task(self.processor_task())

            try:
                await asyncio.sleep(self.duration)
                self.continue_reading = False
                await self.queue.join()

            finally:
                # Cancel tasks and wait for them to complete
                read_coroutine.cancel()
                process_coroutine.cancel()

                # Wait for tasks to handle cancellation
                await asyncio.gather(read_coroutine, process_coroutine, return_exceptions=True)

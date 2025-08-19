"""
Microchip TWST modem data collection and CSV generation library.

This module provides functionality to collect measurements from Microchip TWST modems
and save them to timestamped CSV files. It provides a programmatic interface for
flexible data collection with configurable intervals and durations.

The tool connects to TWST modems via IP address to collect measurement data including
offset and EBNO tracking values, along with contextual information. Data is saved to
CSV files with YAML metadata headers for comprehensive data logging.

Example:
    Import and use programmatically:
        from opensampl.collect.microchip.twst.generate_twst_files import collect_files
        collect_files(host="192.168.1.100", dump_interval=600, total_duration=3600)

    Use via CLI (recommended):
        $ opensampl-collect microchip twst --ip 192.168.1.100
        $ opensampl-collect microchip twst --ip 192.168.1.100 --dump-interval 600 --total-duration 3600

"""

import asyncio
import csv
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from opensampl.collect.microchip.twst.context import ModemContextReader
from opensampl.collect.microchip.twst.readings import ModemStatusReader


async def collect_data(status_reader: ModemStatusReader, context_reader: ModemContextReader):
    """
    Collect modem status readings and context data concurrently.

    Args:
        status_reader: ModemStatusReader instance for collecting measurements.
        context_reader: ModemContextReader instance for collecting context data.

    Raises:
        Exception: Re-raises any exception from the collection process.

    """
    try:
        await asyncio.gather(status_reader.collect_readings(), context_reader.get_context())
    except Exception as e:
        logger.error(f"Error during data collection: {e}")
        raise


def collect_files(
    host: str,
    control_port: int = 1700,
    status_port: int = 1900,
    output_dir: str = "./output",
    dump_interval: int = 300,
    total_duration: Optional[int] = None,
):
    """
    Continuously collect blocks of modem measurements and save to timestamped CSV files.

    Args:
        host: IP address or hostname of the modem.
        control_port: Control port for modem (default: 1700)
        status_port: Status port for modem (default: 1900)
        output_dir: Directory path where CSV files will be saved.
        dump_interval: Duration in seconds between each data collection cycle.
        total_duration: Optional total runtime in seconds. If None, runs indefinitely.

    The function creates timestamped CSV files containing modem measurements
    including offset and EBNO tracking data, along with context information
    as YAML comments.

    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    consecutive_failures = 0
    max_consecutive_failures = 5
    base_retry_delay = 30  # seconds
    max_retry_delay = 300  # 5 minutes

    logger.info(f"Starting data collection from {host}, saving to {output_path}")

    while True:
        if total_duration and (time.time() - start_time) >= total_duration:
            logger.info("Total duration reached, stopping collection")
            break

        status_reader = None
        context_reader = None

        try:
            status_reader = ModemStatusReader(host=host, duration=dump_interval, port=status_port)
            context_reader = ModemContextReader(host=host, prompt="TWModem-32>", port=control_port)

            logger.debug(f"Starting data collection cycle for {host}")
            asyncio.run(collect_data(status_reader, context_reader))

            # Write to CSV file
            timestamp_str = context_reader.result.timestamp
            output_file = output_path / f"{host}_6502-Modem_{timestamp_str}.csv"

            with output_file.open("w", newline="") as f:
                f.write(context_reader.get_result_as_yaml_comment())
                f.write("\n")

                writer = csv.writer(f)
                writer.writerow(["timestamp", "reading", "value"])
                writer.writerows(status_reader.readings)

            logger.info(f"Wrote {len(status_reader.readings)} readings to {output_file}")

            # Reset failure counter on successful collection
            consecutive_failures = 0

        except Exception as e:
            consecutive_failures += 1
            logger.error(f"Collection failed (attempt {consecutive_failures}): {e}")

            if consecutive_failures >= max_consecutive_failures:
                logger.critical(
                    f"Maximum consecutive failures ({max_consecutive_failures}) reached. Stopping collection."
                )
                break

            # Calculate exponential backoff delay
            retry_delay = min(base_retry_delay * (2 ** (consecutive_failures - 1)), max_retry_delay)
            logger.warning(f"Retrying in {retry_delay} seconds...")

            try:
                time.sleep(retry_delay)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, stopping collection")
                break

        finally:
            # Ensure connections are always closed
            if (
                status_reader
                and hasattr(status_reader, "open")
                and status_reader.open
                and hasattr(status_reader, "writer")
                and status_reader.writer
            ):
                status_reader.writer.close()
            if (
                context_reader
                and hasattr(context_reader, "open")
                and context_reader.open
                and hasattr(context_reader, "writer")
                and context_reader.writer
            ):
                context_reader.writer.close()


def main(
    ip_address: str, control_port: int, status_port: int, dump_interval: int, total_duration: int, output_dir: str
):
    """
    Start modem data collection.

    Args:
        ip_address: IP address of the modem.
        control_port: Control port for modem (default: 1700)
        status_port: Status port for modem (default: 1900)
        dump_interval: Duration between file dumps in seconds.
        total_duration: Total duration to run in seconds, or None for indefinite.
        output_dir: Output directory for CSV files.

    """
    collect_files(
        host=ip_address,
        control_port=control_port,
        status_port=status_port,
        dump_interval=dump_interval,
        total_duration=total_duration,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    import sys

    logger.error("This module is now used as a library. Use 'opensampl-collect microchip twst' for CLI access.")
    sys.exit(1)

"""
Microchip TWST modem data collection and CSV generation tool.

This module provides functionality to collect measurements from Microchip TWST modems
and save them to timestamped CSV files. It includes both programmatic and command-line
interfaces for flexible data collection with configurable intervals and durations.

The tool connects to TWST modems via IP address to collect measurement data including
offset and EBNO tracking values, along with contextual information. Data is saved to
CSV files with YAML metadata headers for comprehensive data logging.

Example:
    Run from command line with required IP address:
        $ python generate_twst_files.py --ip 192.168.1.100

    Run with custom intervals and duration:
        $ python generate_twst_files.py --ip 192.168.1.100 --dump-interval 600 --total-duration 3600

"""

import asyncio
import csv
import time
from pathlib import Path
from typing import Optional

import click

from opensampl.collect.microchip.twst.context import ModemContextReader
from opensampl.collect.microchip.twst.readings import ModemStatusReader


async def collect_data(status_reader: ModemStatusReader, context_reader: ModemContextReader):
    """
    Collect modem status readings and context data concurrently.

    Args:
        status_reader: ModemStatusReader instance for collecting measurements.
        context_reader: ModemContextReader instance for collecting context data.

    """
    await asyncio.gather(status_reader.collect_readings(), context_reader.get_context())


def collect_files(host: str, output_dir: str, dump_interval: int, total_duration: Optional[int] = None):
    """
    Continuously collect blocks of modem measurements and save to timestamped CSV files.

    Args:
        host: IP address or hostname of the modem.
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

    while True:
        if total_duration and (time.time() - start_time) >= total_duration:
            break

        status_reader = ModemStatusReader(host=host, duration=dump_interval, keys=["meas:offset", "tracking:ebno"])
        context_reader = ModemContextReader(host=host, prompt="TWModem-32>")

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


def main(ip_address: str, dump_interval: int, total_duration: int, output_dir: str):
    """
    Start modem data collection.

    Args:
        ip_address: IP address of the modem.
        dump_interval: Duration between file dumps in seconds.
        total_duration: Total duration to run in seconds, or None for indefinite.
        output_dir: Output directory for CSV files.

    """
    collect_files(host=ip_address, dump_interval=dump_interval, total_duration=total_duration, output_dir=output_dir)


@click.command()
@click.option("--ip", required=True, help="IP address of the modem")
@click.option("--dump-interval", default=300, help="Duration between file dumps in seconds (default: 300 = 5 minutes)")
@click.option(
    "--total-duration", default=None, type=int, help="Total duration to run in seconds (default: run indefinitely)"
)
@click.option("--output-dir", default="./output", help="Output directory for CSV files (default: ./output)")
def main_click(ip: str, dump_interval: int, total_duration: int, output_dir: str):
    """
    Click command-line interface for modem data collection.

    Args:
        ip: IP address of the modem (required).
        dump_interval: Duration between file dumps in seconds (default: 300).
        total_duration: Total duration to run in seconds (default: None for indefinite).
        output_dir: Output directory for CSV files (default: './output').

    This function serves as the entry point for the click CLI, collecting
    modem measurements and saving them to timestamped CSV files.

    """
    collect_files(host=ip, dump_interval=dump_interval, total_duration=total_duration, output_dir=output_dir)


if __name__ == "__main__":
    main_click()

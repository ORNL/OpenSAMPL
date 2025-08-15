"""Consolidated CLI entry point for opensampl.collect tools."""

import sys
from typing import Literal, Optional

import click
from loguru import logger

from opensampl.collect.microchip.tp4100.collect_4100 import main as collect_tp4100_files
from opensampl.collect.microchip.twst.generate_twst_files import collect_files as collect_twst_files


@click.group()
def cli():
    """OpenSAMPL data collection tools."""
    pass


@cli.group()
def microchip():
    """Microchip device collection tools."""
    pass


@microchip.command()
@click.option("--ip", required=True, help="IP address of the modem")
@click.option("--control-port", required=False, default=1700, help="Control port of the modem (default: 1700)")
@click.option("--status-port", required=False, default=1900, help="Status port of the modem (default: 1900)")
@click.option("--dump-interval", default=300, help="Duration between file dumps in seconds (default: 300 = 5 minutes)")
@click.option(
    "--total-duration", default=None, type=int, help="Total duration to run in seconds (default: run indefinitely)"
)
@click.option("--output-dir", default="./output", help="Output directory for CSV files (default: ./output)")
def twst(ip: str, control_port: int, status_port: int, dump_interval: int, total_duration: int, output_dir: str):
    """
    Collect data from Microchip TWST modems.

    This command connects to TWST modems via IP address to collect measurement data including
    offset and EBNO tracking values, along with contextual information. Data is saved to
    CSV files with YAML metadata headers for comprehensive data logging.

    Examples:
        opensampl-collect microchip twst --ip 192.168.1.100
        opensampl-collect microchip twst --ip 192.168.1.100 --dump-interval 600 --total-duration 3600

    """
    collect_twst_files(
        host=ip,
        control_port=control_port,
        status_port=status_port,
        dump_interval=dump_interval,
        total_duration=total_duration,
        output_dir=output_dir,
    )


@microchip.command()
@click.option("--host", "-h", required=True, help="IP address or hostname of the TP4100 device")
@click.option("--port", "-p", default=443, type=int, help="Port number for HTTPS connection (default: 443)")
@click.option(
    "--output-dir",
    "-o",
    default="./output",
    help="Directory path where collected data will be saved (default: ./output)",
)
@click.option("--duration", "-d", default=600, type=int, help="Duration in seconds for data collection (default: 600)")
@click.option(
    "--channels", "-c", multiple=True, help="Specific channels to collect data from (can be specified multiple times)"
)
@click.option("--metrics", "-m", multiple=True, help="Specific metrics to collect (can be specified multiple times)")
@click.option(
    "--method",
    type=click.Choice(["chart_data", "download_file"]),
    default="chart_data",
    help=(
        'Collection method: "chart_data" for chart data for last (duration) seconds or "download_file" '
        "for previous 24h files (default: chart_data)"
    ),
)
@click.option("--save-full-status", is_flag=True, help="Save full status information to json")
@click.option("--verbose", "-v", is_flag=True, help="Verbose, keeps debug logs")
def tp4100(
    host: str,
    port: int,
    output_dir: str,
    duration: int,
    channels: Optional[list[str]],
    metrics: Optional[list[str]],
    method: Literal["chart_data", "download_file"],
    save_full_status: bool,
    verbose: bool,
):
    """
    Collect time data from Microchip TimeProvider 4100 devices.

    This tool connects to TP4100 devices via their web interface and collects
    performance metrics and time data.
    """
    if not verbose:
        logger.remove()  # Remove default handler
        logger.add(sys.stderr, level="INFO")

    # Convert tuples to lists or None
    channels_list = list(channels) if channels else None
    metrics_list = list(metrics) if metrics else None

    collect_tp4100_files(
        host=host,
        port=port,
        output_dir=output_dir,
        duration=duration,
        channels=channels_list,
        metrics=metrics_list,
        method=method,
        save_full_status=save_full_status,
    )


if __name__ == "__main__":
    cli()
